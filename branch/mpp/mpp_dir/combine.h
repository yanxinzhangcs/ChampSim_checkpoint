/*
 * Daniel A. Jimenez 
 *
 * combine.h
 *
 * Combines the predictions of two predictors, intended to be TAGE-SC-L and MPP
 *
 * The main idea is to compute a sum that is a linear combination of the
 * perceptron confidence and the SC confidence. The slope and bias for the linear
 * combination is tuned per combination of:
 * 
 * 	1. TAGE-SC-L prediction (0 or 1), 
 * 	2. MPP prediction (0 or 1), 
 * 	3. TAGE(only) prediction (0 or 1), and
 * 	4. TAGE confidence(0, 1, or 2). 
 *
 * There are 2 * 2 * 2 * 3 = 24 possible combinations. I tuned most of
 * them individually but some of them come up very infrequently and weren't
 * worth the computation so I tuned their slope and bias together.
 *
 *
 * Another bias is added to the sum, then thresholded to make a prediction. This
 * bias is determined to minimize the recent number of misses. The bias is
 * trained per combination so we keep track of 24 different biases ranging over
 * 64 possible values of the bias. For each combination, I keep track of the
 * number of misses each of the 64 possible bias values would have produced by
 * counting up each time a value would have resulted in a miss and then halving
 * all the counters when one of them saturates at 7. So each counter requires 3 bits.
 *
 * The combiner also provides filtering of trivial branches through two Bloom
 * filters: one for taken branches and another for not taken branches. MPP will
 * only train when a branch appears in both Bloom filters; otherwise, the single
 * observed behavior will be used to predict the branch. The first time a branch
 * is encountered, it's predicted taken if the last 5 ghist bits are true, not
 * taken otherwise. Some of the MPP histories are updated even for trivial
 * branches based on a mask tuned per feature.
 *
 * The Bloom filters add significant overhead (24KB) to the hardware budget. This
 * would be unnecessary if the organizers of CBP 2025 would have provided access
 * to a BTB. It is very common in front-end design for the BTB to do this kind of
 * filtering: A BTB entry can have a bit that records whether a branch has been
 * observed not to be taken. A BTB entry is only allocated when a branch is
 * taken. So, a branch can be filtered from updating predictor state unless it
 * both hits in the BTB and has its "observed not taken" bit set. With an
 * 8K-entry BTB, this would have reduced the overhead to that single extra bit,
 * 1KB. It is unfortunate the organizers did not see fit to include this feature
 * which makes the championship unrealistic. In fairness, some aspects of my
 * predictor are a bit unrealistic too.
 */

#ifndef _COMBINE_H_
#define _COMBINE_H_

#include <math.h>
#include "hash.h"

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "mpp_inside.h"
namespace mppspace {

// provide a Bloom filter implementation for keeping track of branch facts

struct bloom_filter {
	// array of arrays of bool
	bool **v;

	// n tables of length m each

	int n, m;

	// number to use as a factor in the hash function, should be different for different Bloom filters
	int base;

	// hash a key by combinging two hash functions using the Kirsch-Mitzenmache trick
	unsigned int hash (unsigned int key, unsigned int i) {
		return dan_hash::hash2 (key) * i + dan_hash::hash1 (key);
	}

	// constructor
	bloom_filter (int _n = 1, int _m = 1024, int _base=0) : n(_n), m(_m), base(_base) {
		v = new bool*[n];
		for (int i=0; i<n; i++) v[i] = new bool[m];
		reset ();
	}

	// insert an int into the filter
	void insert (unsigned int x) {
		for (int i=0; i<n; i++) v[i][hash (x, base+i) % m] = true;
	}

	// check to see if an int is in the filter (could produce false positive but never false negative)
	bool probe (unsigned int x) {
		for (int i=0; i<n; i++) if (v[i][hash (x, base+i) % m] == false) return false;
		return true;
	}

	// initialize the Bloom filter 
	void reset (void) {
		for (int i=0; i<n; i++) memset (v[i], 0, m);
	}

	// return the number of kilobytes consumed by this Bloom filter
	double kb (void) {
		return n * m / 8192.0;
	}
};

// speculative history stuff needed to update the combining branch predictor

class combine_update : public mpp_branch_update {
public:
	// the branch address
	unsigned int pc;

	// speculative state pointers from the two branch predictors

	mpp_branch_update *tage_sc_l_u, *mpp_u;

	// the whole thing of the MPP state we can stick in a map

	mpp_update mu;

	double sum; // the sum

	combine_update (void) { }
};

class combine : public mpp_branch_predictor {
public:

    int* speculatively_update_tables;
	// as per the contest rules, we keep as many copies as we like of the
	// histories to support speculative update.

	map<uint64_t, combine_update> speculative_updates;

	// the combined prediction is the result of thresholding a linear
	// combination of MPP confidence and LSUM, the perceptron sum from
	// TAGE-SC-L. the combined value has a bias added to it that keeps track
	// of which bias would have resulted in the fewest mispredictions for
	// recent branches. the biases are kept as a 5 dimensional array of
	// 8-bit decaying counters that count misses per a given combination
	// of TAGE-SC-L prediction, MPP prediction, TAGE(only) prediction,
	// TAGE confidence.

#define MAX_MISS_INDEX_BITS	6
#define N_MISS		(1<<MAX_MISS_INDEX_BITS)

	int miss_counters[2][2][2][3][N_MISS];
	int train_miss, bias_index_bits, n_miss;

	// pointers to structs that keep state for TAGE-SC-L and MPP

	mpp_branch_predictor *tage_sc_l_p, *mpp_p;

	// the number of in-flight low confidence branches to throttle
	// speculative update of prediction tables and theta

	int num_lc;

	// threshold for a sum representing a low confidence branch

	int lc_conf_threshold;

	// number of in-flight branches that need to be low confidence to throttle speculative update

	int lc_count_threshold;

	// receive pointers to the branch predictor objects for TAGE-SC-L and MPP

	void attach (mpp_branch_predictor *_tage_sc_l_p, mpp_branch_predictor *_mpp_p) {
		tage_sc_l_p = _tage_sc_l_p;
		mpp_p = _mpp_p;
	}

	// Bloom filters for "ever taken" and "ever not taken" branch PCs

	bloom_filter *et, *ent;

	combine_update u;

	// a global history that helps make static predictions; 5 bits

	unsigned long ghist;

	// slopes and biases for computing sum

	double slopes[2][2][2][3], biases[2][2][2][3];

	~combine (void) {
	}

	// constructor; takes the number of MPP history bits as a parameter

	combine (int history_bits, int* _speculatively_update_tables, int* nentriestotal) { 

        speculatively_update_tables = _speculatively_update_tables;

		// no low confidence branches seen so far

		num_lc = 0;

		// threshold of linear combination to decide a branch is low confidence

		lc_conf_threshold = 25;

		// number of low confidence branches before we have MPP update the tables and theta non-speculatively

		lc_count_threshold = 7;

		// initialize a ghist used for static prediction

		ghist = 0;

		// 64 miss counters per miss counter table

		bias_index_bits = 6;
		n_miss = (1<<bias_index_bits);
		static int printed = 0;

		// compute the size of the predictor; start with the bits from the MPP history

		int predictor_size = history_bits;
		if (!printed) {
			printf ("MPP history size: %g KB\n", history_bits / 8192.0);
		}

		// add the 64KB of TAGE-SC-L state from provided code

		predictor_size += 65536 * 8; 
		if (!printed) {
			printf ("TAGE-SC-L size: %g KB\n", (predictor_size - history_bits) / 8192.0);
		}

		// best configuration of Bloom filters; 3 tables of 2^15 counters

		et = new bloom_filter (3, 1<<15, 47);
		ent = new bloom_filter (3, 1<<15, 75);
		if (!printed) {
			printf ("Bloom filter size %g KB\n", et->kb() + ent->kb());
			fflush (stdout);
		}
		// add in the size of the Bloom filters

		predictor_size += et->kb() * 8192 + ent->kb() * 8192;

		// initialize slopes and biases to default values

		for (int i=0; i<2; i++) for (int j=0; j<2; j++) for (int k=0; k<2; k++) for (int l=0; l<3; l++) {
			slopes[i][j][k][l] = 0.53;
			biases[i][j][k][l] = -20.0;
		}

		// tuned slopes and biases for some configurations

		slopes[0][0][0][0] = 0.50; biases[0][0][0][0] = -21;
		slopes[0][0][0][1] = 0.40; biases[0][0][0][1] = -30;
		slopes[0][0][0][2] = 0.55; biases[0][0][0][2] = -17;
		slopes[0][0][1][0] = 0.46; biases[0][0][1][0] = 0;
		slopes[0][0][1][1] = 0.70; biases[0][0][1][1] = 35;
		slopes[0][1][0][0] = 0.58; biases[0][1][0][0] = -8;
		slopes[0][1][0][1] = 0.56; biases[0][1][0][1] = -19;
		slopes[0][1][0][2] = 0.58; biases[0][1][0][2] = -15;
		slopes[0][1][1][0] = 0.64; biases[0][1][1][0] = 32;
		slopes[1][0][0][0] = 0.58; biases[1][0][0][0] = -33;
		slopes[1][0][1][0] = 0.52; biases[1][0][1][0] = 6;
		slopes[1][0][1][1] = 0.54; biases[1][0][1][1] = 29;
		slopes[1][0][1][2] = 0.52; biases[1][0][1][2] = 12;
		slopes[1][1][0][0] = 0.38; biases[1][1][0][0] = 14;
		slopes[1][1][0][1] = 0.42; biases[1][1][0][1] = -7;
		slopes[1][1][1][0] = 0.20; biases[1][1][1][0] = 31;
		slopes[1][1][1][1] = 0.80; biases[1][1][1][1] = 30;
		slopes[1][1][1][2] = 0.71; biases[1][1][1][2] = 35;

		// add in the size of the bias tables; 24 tables, 64 entries each, 7 bits per entry

		predictor_size += 24 * (1<<bias_index_bits) * 3;

		// this is the size of tage-sc-l, the histories, the bloom filter, the combiner tables

		// extra state added to TAGE-SC-L: 
		predictor_size += 32;

		// add the size of one copy of the state we carry for speculative update of the combiner and MPP

		predictor_size += 
				// state to speculatively update the combiner:

				32 // branch PC
				+ 64 + 64 // two pointers (probably smaller ints in hardware but what the hell)
				+ 64 // 64 bit double for sum

				// state to speculatively update MPP

				+ 32 // branch PC (redundant but I don't care)
				+ 16 + 16 // hpc and hpc2, different hashes of PC
				+ 32 // yout
				+ 33 * 16 // indices for the 33 MPP tables
				+ 1 // updated bit
				+ 1 // overall prediction bit
				;

		// there are various counters and other small variables here
		// and there. I don't want to go through and analyze every little
		// thing so I'll just add in 900 extra bits which should be more
		// than enough.

		predictor_size += 900;

		// the only thing left to count is the perceptron weights
		// tables. the MPP code takes the global variable '*nentriestotal'
		// and figures out how big to make 33 tables so each is a power
		// of 2 and the whole thing comes in no more than 192KB minus
		// whatever we've counted so far

		if (!printed) {
			printf ("number of bits left is %d bits\n", predictor_size);
			printf ("we can afford ");
		}
		int total_bits = 192 * 1024 * 8; // from CBP2025 rules, 192KB
		total_bits -= predictor_size;

		// each table entry is 6 bits so this is how many table entries we can afford

		*nentriestotal = total_bits / 6;
		if (!printed) {
			printf ("%d entries total\n", *nentriestotal);
			fflush (stdout);
		}

		// initialize miss counters

		memset (miss_counters, 0, sizeof (miss_counters));
		for (int i=0; i<2; i++) for (int j=0; j<2; j++) for (int k=0; k<2; k++) for (int l=0; l<3; l++) {
			miss_counters[i][j][k][l][n_miss/2] = 1;
		}
		printed = 1;
	}

	// indexed by TAGE-SC-L pred, MPP pred, TAGE conf, and threshold value

	bool vote (mpp_branch_update *tage_sc_l_u, mpp_branch_update *mpp_u) {
		// this information is packed into the confidence field that we modified in the TAGE-SC-L code

		int pred_taken = !!(tage_sc_l_u->confidence & 1);
		assert (pred_taken == tage_sc_l_u->prediction());
		int pred_inter = !!(tage_sc_l_u->confidence & 2);
		int LowConf = !!(tage_sc_l_u->confidence & 4);
		int MedConf = !!(tage_sc_l_u->confidence & 8);
		int HiConf = !!(tage_sc_l_u->confidence & 16);
		int LSUM = tage_sc_l_u->confidence >> 5;
		int tage_conf = 0;
		if (LowConf) tage_conf = 0;
		else if (MedConf) tage_conf = 1;
		else if (HiConf) tage_conf = 2;
		int tage_pred = tage_sc_l_u->prediction();
		int mpp_pred = mpp_u->prediction();
		int tage_inter = pred_inter;

		// get the slope and bias for this combination of predictor values

		double M = slopes[tage_pred][mpp_pred][tage_inter][tage_conf];
		double B = biases[tage_pred][mpp_pred][tage_inter][tage_conf];

		// compute the sum

		double sum = M * mpp_u->confidence + (1-M) * LSUM + B;
		u.sum = sum;

		// find the bias value that minimizes mispredictions for this config

		int mini = 0;
		int *c = &miss_counters[tage_pred][mpp_pred][tage_inter][tage_conf][0];
		for (int i=0; i<n_miss; i++) if (c[i] < c[mini]) mini = i;
		double b = (mini-n_miss/2);

		// return the prediction

		return u.sum + b >= 0.0;
	}

	// update the miss tables

	void monitor (mpp_branch_update *tage_sc_l_u, mpp_branch_update *mpp_u, bool taken) {
		int tage_pred = tage_sc_l_u->prediction();
		int mpp_pred = mpp_u->prediction();
		int tage_inter = !!(tage_sc_l_u->confidence & 2);
		int LowConf = !!(tage_sc_l_u->confidence & 4);
		int MedConf = !!(tage_sc_l_u->confidence & 8);
		int HiConf = !!(tage_sc_l_u->confidence & 16);
		int tage_conf = 0;
		if (LowConf) tage_conf = 0;
		else if (MedConf) tage_conf = 1;
		else if (HiConf) tage_conf = 2;
		int LSUM = tage_sc_l_u->confidence >> 5;
		double M = slopes[tage_pred][mpp_pred][tage_inter][tage_conf];
		double B = biases[tage_pred][mpp_pred][tage_inter][tage_conf];
		double sum = M * mpp_u->confidence + (1-M) * LSUM + B;

		// train the bias 

		int *c = &miss_counters[tage_pred][mpp_pred][tage_inter][tage_conf][0];
		bool halve = false;

		for (int i=0; i<n_miss; i++) {
			// if we had used this bias to make the prediction, would we have mispredicted?

			double b = (i-n_miss/2);
			bool pred_with_this_bias = (sum + b) >= 0.0;
			c[i] += pred_with_this_bias != taken;
			if (c[i] == 7) halve = true;
		}

		// decay all the counters if one has gotten too big

		if (halve) {
			for (int i=0; i<n_miss; i++) c[i] /= 2;
		}
	}

	mpp_branch_update *lookup (unsigned int pc, uint64_t dynamic_id, unsigned int* global_tage_pred, unsigned int* global_tage_conf) {
		u.pc = pc;
		u.tage_sc_l_u = tage_sc_l_p->lookup (pc, dynamic_id);
		*global_tage_pred = u.tage_sc_l_u->prediction();
		*global_tage_conf = u.tage_sc_l_u->confidence;
		u.mpp_u = mpp_p->lookup (pc, dynamic_id, global_tage_pred, global_tage_conf);

		// see if the branch has ever been taken or not taken
		bool ever_taken = et->probe (u.pc);
		bool ever_not_taken = ent->probe (u.pc);

		if (!ever_taken && !ever_not_taken) {
			// never seen this branch before; predict statically
			// when the 5 previous branches are taken, the branch tends to be taken, otherwise not

			bool pred = __builtin_popcount (ghist & 31) == 5;
			u.prediction (pred);
			u.tage_sc_l_u->prediction (pred);
			u.mpp_u->prediction (pred);
		} else if (!ever_taken) {

			// we have never seen this branch taken; predict it's not taken

			u.prediction (false);
			u.tage_sc_l_u->prediction (false);
			u.mpp_u->prediction (false);
		} else if (!ever_not_taken) {

			// we have never seen this branch not taken; predict it's taken
			u.prediction (true);
			u.tage_sc_l_u->prediction (true);
			u.mpp_u->prediction (true);
		} else {

			// the branch has shown both behaviors; choose between the two predictors
			u.prediction (vote (u.tage_sc_l_u, u.mpp_u));
		}

		// record the MPP histories in the speculative update structure
		u.mu = * (mpp_update *) u.mpp_u;
		combine_update *r = &speculative_updates[dynamic_id];
		*r = u;
		return r;
	}

	// update MPP histories with ground truth and prediction tables with prediction
	void spec_update (mpp_branch_update *p, uint64_t target, bool taken, bool pred, int type, bool, uint64_t dynamic_id) {

		bool filter = !(et->probe (u.pc) && ent->probe (u.pc));
		mpp_p->spec_update (u.mpp_u, target, taken, pred, type, filter, dynamic_id);

		// need to update the speculative structure with new information about whether we updated the tables

		combine_update *r = &speculative_updates[dynamic_id];
		r->mu.updated = ((mpp_update *) u.mpp_u)->updated;
		r->mu.overall_prediction = ((mpp_update *) u.mpp_u)->overall_prediction;
		if (!filter && fabs (u.sum) < lc_conf_threshold) num_lc++;
		if (num_lc >= lc_count_threshold) *speculatively_update_tables = 0;
	}

	// update branch predictors with ground truth after a branch is resolved

	void update (mpp_branch_update *p, unsigned int target, bool taken, int type, uint64_t dynamic_id) {
		// find the speculative update information for this prediction
		auto z = speculative_updates.find (dynamic_id);
		assert (z != speculative_updates.end());

		// get it into 'u'

		u = (*z).second;

		bool filter = !(et->probe (u.pc) && ent->probe (u.pc));
		if (!filter && fabs (u.sum) < lc_conf_threshold) {
			num_lc--;
			if (num_lc < 0) num_lc = 0;
		}
		if (num_lc < lc_count_threshold) {
			*speculatively_update_tables = 1;
		}
		// get rid of it

		speculative_updates.erase (z);

		// we remember which branches have ever been taken or not taken so the branch predictors can filter them

		if (taken) 
			// if this branch is taken, put it in the "ever taken" Bloom filter
			et->insert (u.pc); 
		else 
			// otherwise, put it in the "ever not taken" Bloom filter
			ent->insert (u.pc);

		// should train only if the branch has been seen both taken and not taken
		bool do_train = et->probe (u.pc) && ent->probe (u.pc);

		// update TAGE-SC-L
		tage_sc_l_p->update (u.tage_sc_l_u, target, taken, type, do_train, !do_train, dynamic_id);

		// update MPP
		mpp_p->update (&u.mu, target, taken, type, do_train, !do_train, dynamic_id);

		// update the miss counters for keeping track of the best bias for the linear combination
		if (do_train) monitor (u.tage_sc_l_u, &u.mu, taken);

		// update global history used for static prediction
		ghist <<= 1;
		ghist |= taken;
	}

	// update ghist and path history on branches that aren't conditional

	void nonconditional_branch (unsigned int pc, unsigned int target, int type) {
		tage_sc_l_p->nonconditional_branch (pc, target, type);
		mpp_p->nonconditional_branch (pc, target, type);
	}
};

} // namespace mppspace

#endif // _COMBINE_H_
