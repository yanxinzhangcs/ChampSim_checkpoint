/*
 * Daniel A. Jimenez 
 *
 * mpp.h
 *
 * Multiperspective Perceptron Predictor
 *
 * The multiperspective perceptron predictor (MPP) is a hashed perceptron
 * predictor that uses several different kinds of control-flow history
 * information to form hashes into tables, read out weights, sum them, and
 * threshold the sum to make a prediction. It is updated by incrementing or
 * decrementing 6-bit saturating weights based on whether the branch is taken
 * or not taken, respectively. The paper describes the features in detail.
 * Training is done for mispredicted branches as well as for branches where
 * the magnitude of the perceptron sum fails to exceed a training threshold,
 * theta, thats set using a simplified version of Seznec's training algorithm
 * from O-GEHL.
 * 
 * MPP_inside uses a transfer function to improve accuracy by boosting values of
 * more confident weights. The features and the transfer function were roughly
 * tuned using a combination of a genetic algorithm, then fine-tuned by making
 * small random tweaks and hill-climbing.
 * 
 * The CBP 2025 simulator may make several predictions before doing an update, so
 * speculative update of histories is highly recommended. To ease the burden on
 * competitors, the organizers have provided a hook to speculatively update
 * histories using ground truth taken/not taken information, so rollback to
 * non-speculative history is never needed. They have also allowed an unlimited
 * number of speculative history update entries to support this functionality.
 * 
 * MPP_inside also speculatively updates the history tables and training threshold
 * (theta). HOWEVER this other speculative update is done using the combined
 * MPP/TAGE-SC-L prediction, NOT the ground truth taken/not-taken. To be clear,
 * predictor tables are updated speculatively but only using predictions,
 * not using the actual branch outcomes.
 * 
 * Because this speculative update uses predictions, the tables and theta
 * may be updated with wrong information. When this happens, the training
 * process will undo the update when a speculatively updated but mispredicted
 * branch is resolved, i.e. it will train the tables and theta in the right
 * direction, twice: once to correct the wrong update, and once to do the right
 * update. This correction is only done once the branch resolves. The combiner
 * class, which has the more accurate aggregate prediction used to control
 * this speculative update, monitors when there are too many low-confidence
 * branches in flight and puts MPP_inside into a non-speculative update mode until
 * some low-confidence branches commit.
 * 
*/

#ifndef _MPP_INSIDE_H_
#define _MPP_INSIDE_H_

#include <ctype.h>
#include <stdint.h>
#include <list>
#include <map>
using namespace std;
#include "hash.h"
#include "branch.h"
#include "eval.h"

namespace mppspace {
// one perceptron weight. kept as a struct to try out adding other things like
// tags, bits to keep track of aliasing, sign/magnitude representation, etc. none
// of which worked.

struct Weight {
	char val;
};

// this variable is set by combine.h when there are too many low confidence
// branches in flight. MPP_inside throttles speculative update when it's true


// define maximum sizes of structures (actual sizes defined in variables later)

#define MAX_PATHHIST	512	// maximum path history
#define MAX_GHIST	512	// maximum global history
#define MAX_LG_TABLE_SIZE	13	// log base 2 of maximum weight table size
#define MAX_TABLE_SIZE	(1<<MAX_LG_TABLE_SIZE) // maximum table size
#define MAX_LOCAL_HISTORIES	2048	// maximum number of per-branch histories
#define MAX_ACYCLIC	20	// maximum number of acyclic histories
#define MAX_MOD		10	// maximum number of modulo histories
#define MAX_BLURRY	16	// maximum number of blurry histories
#define MAX_BLURRY2	16	// maximum number of words per blurry history
#define MAX_ASSOC	256	// maximum associativity of the recency stack history

// speculative state carried along with the branch instruction

class mpp_update : public mpp_branch_update {
public:
	// PC of the instruction to be predicted
	unsigned int pc;

	// two hashes of the PC used for recording path histories
	unsigned short int hpc, pc2;

	// the perceptron output
	int yout;

	// indices into the weights tables used to make this prediction
	int indices[MAX_TABLES];

	// set to true if this prediction has updated the weights table
	bool updated;

	// overall prediction from the higher level predictor
	bool overall_prediction;

	mpp_update (void) { }
};

// lookup table table for the transfer function. maps a 6-bit signed integer to genetically evolved function. 

static int default_xfer[] = { -255,-217,-192,-171,-155,-142,-130,-120,-110,-102,-94,-87,-81,-74,-68,-62,-56,-50,-46,-41,-37,-34,-30,-27,-24,-20,-17,-14,-11,-8,-5,2,5,8,11,14,17,20,24,27,30,34,37,41,46,50,56,62,68,74,81,87,94,102,110,120,130,142,155,171,192,217,255, }; // tuned 4/27/2025 for CBP

// MPP_inside histories all in one place

struct mpp_histories {

	// innermost loop iteration counters; 4 versions (we really only use 1)

	unsigned int imli_counter1, imli_counter2, imli_counter3, imli_counter4; 

	// global taken/not-taken history kept as a vector of 64-bit words

	uint64_t global_hist[1 + MAX_GHIST/sizeof(uint64_t)];

	// global history of only backward branches

	uint64_t backglobal_hist[1 + MAX_GHIST/sizeof(uint64_t)];

	// path history of backward branches

	unsigned int back_path[MAX_PATHHIST];

	// acyclic histories; indexed by PC modulo a number, contains the last branch outcome for that pC

	bool acyclic_histories[MAX_ACYCLIC][32];

	// per-branch histories up to 256 wide

	uint64_t local_histories[MAX_LOCAL_HISTORIES][4]; // table of per-branch (local) histories

 	// modulo pattern history

	bool mod_histories[MAX_MOD][MAX_GHIST];

	// modulo path history
	unsigned short int modpath_histories[MAX_MOD][MAX_PATHHIST]; 

	// recency stack of recenctly visited PCs (hashed)
	unsigned short int recency_stack[MAX_ASSOC]; 

	// history of recent PCs (hashed)
	unsigned short int path_history[MAX_PATHHIST]; 

	// "page" history; history of recent regions of program visited
	unsigned int blurrypath_histories[MAX_BLURRY][MAX_BLURRY2]; 
};

// feature types
enum history_type {
        ACYCLIC = 1,            // "acylic history" - put the most recent history of pc into array[pc%parameter] and use this array as a feature
        MODHIST = 2,            // "modulo history" - shift history bit in if PC%modulus==0
        BIAS = 3,               // bias of this branch
        RECENCY = 4,            // hash of a recency stack of PCs
        IMLI = 5,               // inner most loop iteration counter(s)
        PATH = 6,               // path history
        LOCAL = 7,              // local history (pshare)
        MODPATH = 8,            // like modhist but with path history
        GHISTPATH = 9,		// (path history << 1) | global history
        GHISTMODPATH = 10,	// (mod path history << 1) | global history
        BLURRYPATH = 11,        // "page" history sort of
        RECENCYPOS = 12,        // position of this PC in the recency stack
	BACKPATH = 13,		// hashed history of backward branches
	BACKGHISTPATH = 14,	// combines backpath and backghist
	TAGE = 15,		// confidence, LSUM, and prediction from TAGE-SC-L
        MAXTYPE = 16
};


// flags in features to tell which hash function to use to hash the index. don't ask me why these values.

#define XOR_HASH1	8
#define XOR_HASH2	16
#define XOR_HASH3	32

// this struct represents one feature that is an input to the hashed perceptron predictor

struct history_spec {
	// the type of the feature
	enum history_type type;

	// up to six parameters for this feature (we really only use four)
	int p1, p2, p3, p4, p5, p6;

	// whether to use one of 3 different hash functions
	unsigned int xorflags;
};

class mpp_inside : public mpp_branch_predictor {
public:

 int* speculatively_update_tables;
	// for simplicity we keep stuff in large arrays and then only use
	// the part of them needed for the predictor. these defines give the
	// maximum sizes of the arrays. they are very large to allow for flexible
	// search of the design space, but the actual tuned values are represented
	// in variables passed as parameters to the constructor and fit within the
	// given hardware budget

	// STATE THAT COUNTS AGAINST THE HARDWARE BUDGET. these variables
	// are the part of the predictor that contain mutable state that
	// persists from one prediction to the next. the parts of these variables
	// that are actually used by the predictor count against the hardware budget.
	// we'll also count one instance of the speculative histories

	// tables of weight magnitudes

	Weight tables[MAX_TABLES][MAX_TABLE_SIZE];

	// the different histories

	mpp_histories mu;

	// information needed to update the predictor, kept to facilitate speculative update

	mpp_update u;

	// RUN-TIME CONSTANTS THAT DO NOT COUNT AGAINST HARDWARE BUDGET

	int 
		// minimum, maximum, and initial values for theta

		min_theta, 
		max_theta, 
		original_theta;

	int

		// many different moduli could be used for building
		// modulo history. these arrays keep track of which moduli
		// are actually used in the features for this predictor
		// so only the relevant tables are updated for performance
		// reasons. in a real implementation, only those tables would
		// be implemented.

		modhist_indices[MAX_MOD],
		modpath_indices[MAX_MOD],	
		modpath_lengths[MAX_MOD], 
		modhist_lengths[MAX_MOD];

	int 
		// maximum global history required by any feature

		ghist_length, 

		// maximum modulo history required by any feature

		modghist_length, 

		// maximum path length required by any feature

		path_length,

		// total bits used by the predictor (for sanity check)

		totalbits,

		// total number of bits used for histories

		historybits,

		// associativity of the recency stack, derived from the maximum depth any RECENCY feature hashes

		assoc;

		// number of modulo histories and modulo path histories

		int nmodhist_histories, nmodpath_histories;

		// threshold for adaptive theta adjusting

		int theta;

	// return the total number of bits allocated to histories so the higher level predictor can account for them
	int history_bits (void) {
		return historybits;
	}

	// shift a bool into a multi-word history
	void update_hist (uint64_t *hist, bool taken) {
		for (int i=(ghist_length/64)+1; i > 0; i--) {
			hist[i] = (hist[i] << 1) | (hist[i-1] >> 63);
		}
		hist[0] = (hist[0] << 1);
		hist[0] |= taken;
		return;
	}

	// update the global history with an outcome
	void update_global_hist (bool taken) { update_hist (mu.global_hist, taken); }

	// update the backward-only global history with an outcome
	void update_backglobal_hist (bool taken) { update_hist (mu.backglobal_hist, taken); }

	// extract bits from a vector of words from bit a to bit b
	uint64_t idx (uint64_t *v, int a, int b) {
		if (a == b) return 0; 
		if (b == 0) return 0;

		int i = a / 64;
		if (i != (b - 1) / 64) {
			int c0 = (a | 63) + 1;
			if (c0 >= b) return idx(v, a, b);
			uint64_t w1 = idx(v, a, c0);
			uint64_t w2 = idx(v, c0, b);
			return (w2 << (c0 - a)) | w1;
		} else {
			uint64_t w = v[i];
			int bits = b - a;
			int s = a & 63;
			uint64_t mask = (bits >= 64) ? ~0ull : (1ull << bits) - 1; 
			w = (w >> s) & mask;
			return w;
		}
	}

	// fold a vector of words with repeated addition
	uint64_t fold_hist (uint64_t *hist, int start, int end, int bits) {
		if (start > end) return 0;
		if (start < 0) return 0;
		if (end < 0) return 0;
		int a = start;
		int b = end + 1;
		uint64_t x = 0;
		if (b-a < bits) return idx (hist, a, b);
		int j;
		int j2 = b - bits;
		for (j=a; j<j2; j+=bits) x += idx (hist, j, j+bits);
		if (j < b) x += idx (hist, j, b);
		return x;
	}

	// optional stuff to do when the predictor stops
	void ending (int x) { }

	// insert an item into an array without duplication. used for
	// building the _indices arrays

	int insert (int *v, int *n, int x) {
		for (int i=0; i<*n; i++) if (v[i] == x) return i;
		v[(*n)] = x;
		return (*n)++;
	}

	// analyze the specification of the features to see what the
	// various maximum history lengths are, how much space is taken by
	// various history structures, and how much space is left over in
	// the hardware budget for tables

	void analyze_spec (int* nentriestotal, bool print_mpp_sizes) {
		history_spec specers[MAX_TABLES];

		int nspecers = 0;
		for (int i=0; i<num_tables; i++)
			specers[nspecers++] = specv[i];

		bool 
			// true if at least one feature requires the recency stack

			doing_recency = false, 

			// true if at least one feature uses local history

			doing_local = false;

	
		int 
			// how many bits are allocated to the IMLI counters

			imli_counter_bits[4];

		// accounting for bits for the blurry path history

		int blurrypath_bits[MAX_BLURRY][MAX_BLURRY2];

		// accouting for the bits for the acyclic path history

		bool acyclic_bits[MAX_ACYCLIC][32][2];

		// set these accounting arrays to 0 initially

		memset (blurrypath_bits, 0, sizeof (blurrypath_bits));
		memset (imli_counter_bits, 0, sizeof (imli_counter_bits));
		memset (acyclic_bits, 0, sizeof (acyclic_bits));

		// initially assume very short histories, later find out
		// what the maximum values are from the features

		ghist_length = 1;
		modghist_length = 1;
		nmodhist_histories = 0;
		path_length = 1;
		assoc = 0;

		// go through each feature in the specification finding the requirements

		for (int i=0; i<nspecers; i++) {
			// find the maximum associativity of the recency stack required

			if (specers[i].type == RECENCY || specers[i].type == RECENCYPOS) {
				if (assoc < specers[i].p1) assoc = specers[i].p1;
			}

			// find out how much and what kind of history is needed for acyclic feature

			if (specers[i].type == ACYCLIC) {
				for (int j=0; j<specers[i].p1+2; j++) {
					acyclic_bits[specers[i].p1][j][!specers[i].p3] = true;
				}
			}

			// do we need local history?

			if (specers[i].type == LOCAL) doing_local = true;

			// how many IMLI counter bits do we need for different versions of IMLI

			if (specers[i].type == IMLI) imli_counter_bits[specers[i].p1-1] = 32;

			// do we require a recency stack?

			if (specers[i].type == RECENCY || specers[i].type == RECENCYPOS) doing_recency = true;

			// count blurry path bits (assuming full 32-bit addresses less shifted bits)

			if (specers[i].type == BLURRYPATH) for (int j=0; j<specers[i].p2; j++) blurrypath_bits[specers[i].p1][j] = 32 - specers[i].p1;

			// if we are doing modulo history, figure out which and how much history we need

			if (specers[i].type == GHISTPATH || specers[i].type == BACKGHISTPATH) {
				if (ghist_length < specers[i].p2) ghist_length = specers[i].p2 + 1;
			}
			if (specers[i].type == MODHIST || specers[i].type == GHISTMODPATH) {
				int j = insert (modhist_indices, &nmodhist_histories, specers[i].p1);
				if (modhist_lengths[j] < specers[i].p2+1) modhist_lengths[j] = specers[i].p2 + 1;
				if (specers[i].p2 >= modghist_length) modghist_length = specers[i].p2+1;
			}
		}

		// figure out how much history we need for modulo path, modulo+global path, and regular path

		nmodpath_histories = 0;
		for (int i=0; i<nspecers; i++) {
			if (specers[i].type == MODPATH || specers[i].type == GHISTMODPATH) {
				int j = insert (modpath_indices, &nmodpath_histories, specers[i].p1);
				if (modpath_lengths[j] < specers[i].p2+1) modpath_lengths[j] = specers[i].p2 + 1;
				if (path_length <= specers[i].p2) path_length = specers[i].p2 + 1;
			}
		}
		local_history_length = 0;

		// how much global history and global path history do we need

		for (int i=0; i<nspecers; i++) {
			switch (specers[i].type) {
			case LOCAL:
			if (local_history_length < specers[i].p2) local_history_length = specers[i].p2;
			break;
			default: ;
			}
		}

		// sanity check

		assert (ghist_length <= MAX_GHIST);
		assert (modghist_length <= MAX_GHIST);

		// account for IMLI counters (we only use one)

		int last = 0;
		totalbits += 32;

		if (print_mpp_sizes) printf ("%d IMLI counter bits\n", totalbits - last); last = totalbits;

		// account for global path bits (represented as an array of 16 bit integers)

		totalbits += path_length * 16;
		if (print_mpp_sizes) printf ("%d x 16 = %d global path bits\n", path_length, totalbits - last); last = totalbits;
		
		// account for modulo history bits

		for (int i=0; i<nmodhist_histories; i++) totalbits += modhist_lengths[i];
		if (print_mpp_sizes) printf ("%d total modulo history bits\n", totalbits - last); last = totalbits;

		// account for modulo path bits

		for (int i=0; i<nmodpath_histories; i++) totalbits += 16 * modpath_lengths[i];
		if (print_mpp_sizes) printf ("%d total modulo path bits\n", totalbits - last); last = totalbits;

		// account for local histories

		// here, we decide how many local histories to have! whatever it is, local histories should take ~6KB

		nlocal_histories = 49152 / local_history_length;

		// but we don't want to have too many; limit it to 1280

		if (nlocal_histories > 1280) nlocal_histories = 1280;
		if (doing_local) totalbits += local_history_length * nlocal_histories;
		if (print_mpp_sizes) printf ("%d x %d = %d total local history bits\n", local_history_length, nlocal_histories, totalbits - last); last = totalbits;

		// account for recency stack

		if (doing_recency) totalbits += assoc * 16;
		if (print_mpp_sizes) printf ("%d x 16 = %d total recency bits\n", assoc, totalbits - last); last = totalbits;

		// account for blurry path bits

		for (int i=0; i<MAX_BLURRY; i++) for (int j=0; j<MAX_BLURRY2; j++) totalbits += blurrypath_bits[i][j];
		if (print_mpp_sizes) printf ("%d total blurry path bits\n", totalbits - last); last = totalbits;

		// account for acyclic bits

		for (int i=0; i<MAX_ACYCLIC; i++) for (int j=0; j<32; j++) for (int k=0; k<2; k++) totalbits += acyclic_bits[i][j][k];
		if (print_mpp_sizes) printf ("%d total acyclic bits\n", totalbits - last); last = totalbits;

		// thetas are 8 bits for theta

		totalbits += 8;
		if (print_mpp_sizes) printf ("%d bits for theta\n", totalbits - last); last = totalbits;

		historybits = totalbits;

		// how many bits are left for the tables?

		// whatever is left, we divide among the rest of the tables

		// this is the total number of perceptron weights we can afford
		// we get it from the higher level predictor, but start
		// with an estimate the first time the branch predictor
		// is constructed

		if (*nentriestotal == -1) *nentriestotal = 131072; // dummy number filled after first call to MPP's constructor

		// this little algorithm figures out, for the total number
		// of entries, how to divide them into power-of-two sized
		// tables adding up to no more than that number of entries
		// it does an exhaustive search to find a sequence of table sizes
		// with 2^i or 2^{i+1} sized tables for some i that maximizes usage
		// of the number of entries

		bool ok = false;

		// find the sequence of table sizes that minimizes *nentriestotal minus the sum of the table sizes

		long mindiff = 1<<30;
		int minsizes[MAX_TABLES], actualnentries = 0;

		// try powers of two from 2^6 to 2^20

		int lg_table_sizes[MAX_TABLES];
		for (int i=6; i<20; i++) {

			// we'll divide the tables up into tables of 2^i and 2^{i+1}
			int ts1 = 1<<i;
			int ts2 = 1<<(i+1);

			// we'll have anywhere from 0 to num_tables tables of the first sizeo
			for (int t=0; t<num_tables; t++) {
				for (int j=0; j<t; j++) {
					table_sizes[j] = ts1;
					lg_table_sizes[j] = t;
				}
				for (int j=t; j<num_tables; j++) {
					table_sizes[j] = ts2;
					lg_table_sizes[j] = i+1;
				}
				int sum = 0;
				for (int j=0; j<num_tables; j++) sum += table_sizes[j];
				long diff = *nentriestotal - sum;
				if (sum <= *nentriestotal) {
					if (diff < mindiff) {
						mindiff = diff;
						memcpy (minsizes, table_sizes, sizeof (minsizes));
						actualnentries = sum;
						ok = true;
					}
				}
			}
		}
		if (print_mpp_sizes) printf ("leaving %d entries on the table\n", *nentriestotal - actualnentries);
		done: ;
		if (!ok) {
			printf ("no feasible tables?\n");
			assert (0);
		}
		memcpy (table_sizes, minsizes, sizeof (table_sizes));
		if (print_mpp_sizes) {
			map<int,int> m;
			for (int i=0; i<num_tables; i++) m[table_sizes[i]]++;
			for (auto p=m.begin(); p!=m.end(); p++) printf ("%d table%s of %d 6-bit entries\n", (*p).second, (*p).second > 1 ? "s" : "", (*p).first);
			fflush (stdout);
		}
	}

	// the features

	history_spec *specv;

	// these variables set from parameters

	int 
		num_tables,		// real number of tables that the features are folded into
		nlocal_histories, 	// number of local histories
		local_history_length; 	// local history length

	double 
		alpha;			// learning rate for training weak but correct predictions

	int 
		*xfer,			// transfer function for 6-bit weights (5-bit magnitudes)
		pcbit,			// bit from the PC to use for hashing global history
		htbit,			// used to hash the outcome bit for a more uniform ghist
		block_size;		// number of ghist bits in a "block"; this is the width of an initial hash of ghist

	bool 
		hash_taken;		// should we hash the taken/not taken value with a PC bit?

	int 
		table_sizes[MAX_TABLES];// size of each table

	unsigned int 
		record_mask;		// which histories are updated with filtered branch outcomes

	int xflag, xn;

	// initialize various structures

	void beginning (void) {

		// zero out all the histories

		mu.imli_counter1 = 0;
		mu.imli_counter2 = 0;
		mu.imli_counter3 = 0;
		mu.imli_counter4 = 0;
		memset (mu.global_hist, 0, sizeof (mu.global_hist));
		memset (mu.backglobal_hist, 0, sizeof (mu.backglobal_hist));
		memset (mu.back_path, 0, sizeof (mu.back_path));
		memset (mu.acyclic_histories, 0, sizeof (mu.acyclic_histories));
		memset (mu.local_histories, 0, sizeof (mu.local_histories));
		memset (mu.mod_histories, 0, sizeof (mu.mod_histories));
		memset (mu.modpath_histories, 0, sizeof (mu.modpath_histories));
		memset (mu.recency_stack, 0, sizeof (mu.recency_stack));
		memset (mu.path_history, 0, sizeof (mu.path_history));
		memset (mu.blurrypath_histories, 0, sizeof (mu.blurrypath_histories));

		// threshold counter for adaptive theta training

		theta = original_theta;

		// initialize tables to -32, which will mean uninitialized
		// because actual trained weights range from -31..31

		for (int i=0; i<num_tables; i++) for (int j=0; j<table_sizes[i]; j++) tables[i][j].val = -32;
	}

	// constructor; parameters described above 

	mpp_inside (
		history_spec *_specv,
		int _num_tables,
		int _theta, 
		double _alpha, 
		int *_xfer, 
		int _pcbit, 
		int _htbit,
		int _block_size, 
		bool _hash_taken,
		unsigned int _record_mask, 
		unsigned int _xflag, 
		unsigned int _xn,
        int* _spec_update_tables,
        int* nentriestotal,
        bool print_mpp_sizes) :
			specv(_specv), num_tables(_num_tables), 
			alpha(_alpha), xfer(_xfer), pcbit(_pcbit), htbit(_htbit), block_size(_block_size), 
			hash_taken(_hash_taken), record_mask(_record_mask),
			xflag(_xflag), xn(_xn), speculatively_update_tables(_spec_update_tables) {
		assert (specv);

		// min, max, and initial value of theta

		min_theta = 10;
		max_theta = 216;
		if (_theta < min_theta) _theta = min_theta;
		original_theta = _theta;

		// we will count the number of bits MPP_inside uses

		// no bits used so far

		totalbits = 0;

		// zero out history lengths for modpath and modghist; they will be initialized in analyze_spec()

		memset (modpath_lengths, 0, sizeof (modpath_lengths)); 
		memset (modhist_lengths, 0, sizeof (modhist_lengths)); 

		// analyze the specification to figure out how many bits are allocated to what

		analyze_spec (nentriestotal, print_mpp_sizes);

		// initialize stuff

		beginning ();
	}

	// insert a (shifted) PC into the recency stack with LRU replacement

	void insert_recency (unsigned int pc) {
		int i = 0;
		for (i=0; i<assoc; i++) {
			if (mu.recency_stack[i] == pc) break;
		}
		if (i == assoc) {
			i = assoc-1;
			mu.recency_stack[i] = pc;
		}
		int j;
		unsigned int b = mu.recency_stack[i];
		for (j=i; j>=1; j--) mu.recency_stack[j] = mu.recency_stack[j-1];
		mu.recency_stack[0] = b;
	}

	// hash a PC

	uint64_t hash_pc (unsigned int pc) {
		return hash (pc, 10);
	}

	// hash for indexing the table of local histories

	uint64_t hash_local (void) {
		return hash (u.pc, 31);
	}

	// hash path history

	uint64_t hash_path (int depth, int shift) {
		uint64_t x = 0;
		for (int i=0; i<depth; i++) {
			x <<= shift;
			x += mu.path_history[i];
		}
		return x;
	}

	// hash global history from position a to position b

	uint64_t hash_ghist (int a, int b, int bits) {
		return fold_hist (mu.global_hist, a, b, bits);
	}

	// hash the backward ghist

	uint64_t hash_backghist (int a, int b, int bits) {
		return fold_hist (mu.backglobal_hist, a, b, bits);
	}

	// hash combined path and ghist histories

	uint64_t hash_ghistpath (int a, int b, int c, int d, int bits) {
		uint64_t x = hash_path (c, d);
		uint64_t y = hash_ghist (a, b, bits);
		return x + y;
	}

	// hash the backward path history

	uint64_t hash_backpath (int depth, int shift) {
		uint64_t x = 0;
		for (int i=0; i<depth; i++) {
			x <<= shift;
			x += mu.back_path[i];
		}
		return x;
	}

	// hash a combined backward path and backward ghist

	uint64_t hash_backghistpath (int a, int b, int c, int d, int bits) {
		uint64_t x = hash_backpath (c, (d == -1) ? 3 : d);
		uint64_t y = hash_backghist (a, b, bits);
		return x + y;
	}

	// hash the items in the recency stack to a given depth, shifting
	// by a certain amount each iteration

	uint64_t hash_recency (int depth, int shift) {
		uint64_t x = 0;
		for (int i=0; i<depth; i++) {
			x <<= shift;
			x += mu.recency_stack[i];
		}
		return x;
	}

	// hash the "blurry" path history of a given scale to a given
	// depth and given shifting parameter

	uint64_t hash_blurry (int scale, int depth, int shiftdelta) {
		if (shiftdelta == -1) shiftdelta = 0;
		int sdint = shiftdelta >> 2;
		int sdfrac = shiftdelta & 3;
		uint64_t x = 0;
		int shift = 0;
		int count = 0;
		for (int i=0; i<depth; i++) {
			x += mu.blurrypath_histories[scale][i] >> shift;
			count++;
			if (count == sdfrac) {
				shift += sdint;
				count = 0;
			}
		}
		return x;
	}

	// hash acyclic histories with a given modulus and shift

	uint64_t hash_acyclic (int a, int bits) {
		uint64_t x = 0;
		unsigned int k = 0;
		for (int i=0; i<a+2; i++) {
			x ^= mu.acyclic_histories[a][i] << k;
			k++;
			k %= bits;
		}
		return x;
	}

	// hash modulo history with a given modulus and length

	uint64_t hash_modhist (int a, int b, int n) {
		uint64_t x = 0;
		unsigned int k = 0;
		for (int i=0; i<b; i++) {
			x ^= mu.mod_histories[a][i] << k;
			k++;
			k %= n;
		}
		return x;
	}

	// hash modulo path history with a given modulus, depth, and shift

	uint64_t hash_modpath (int a, int depth, int shift) {
		uint64_t x = 0;
		for (int i=0; i<depth; i++) {
			x <<= shift;
			x += mu.modpath_histories[a][i];
		}
		return x;
	}

	// hash modulo path history together with modulo (outcome) history

	uint64_t hash_ghistmodpath (int a, int depth, int shift) {
		uint64_t x = 0;
		for (int i=0; i<depth; i++) {
			x <<= shift;
			x += (mu.modpath_histories[a][i] << 1) | mu.mod_histories[a][i];
		}
		return x;
	}

	// hash the recency position where we find this PC

	uint64_t hash_recencypos (unsigned int pc, int l, int t) {
	
		// search for the PC

		for (int i=0; i<l; i++)
			if (mu.recency_stack[i] == pc)
				return i * table_sizes[t] / l;

		// return last index in table on a miss

		return table_sizes[t] - 1;
	}

	// apply the transfer function

	int transfer (int c) {

		// if the weight is uninitalized, it can't know any correlation so return 0

		if (c == -32) return 0;

		// potentially correlating weight; amplify using transfer function lookup table

		assert (c > -32 && c < 32);
		return xfer[c+31];
	}

	// use a history specification to call the corresponding history hash function

	uint64_t get_hash (history_spec *s, unsigned int pc, unsigned int pc2, int t, unsigned int* global_tage_pred, unsigned int* global_tage_conf) {
		uint64_t x = 0;
		switch (s->type) {
		case BACKGHISTPATH:
			x = hash_backghistpath (s->p1, s->p2, s->p3, s->p4, block_size);
			break;
		case GHISTPATH:
			x = hash_ghistpath (s->p1, s->p2, s->p3, s->p4, block_size);
			break;
		case ACYCLIC:
			x = hash_acyclic (s->p1, block_size);
			break;
		case MODHIST:
			x = hash_modhist (s->p1, s->p2, block_size);
			break;
		case GHISTMODPATH:
			x = hash_ghistmodpath (s->p1, s->p2, s->p3);
			break;
		case MODPATH:
			x = hash_modpath (s->p1, s->p2, s->p3);
			break;
		case BIAS:
			x = 0;
			break;
		case RECENCY:
			x = hash_recency (s->p1, s->p2);
			break;
		case IMLI:
			if (s->p1 == 1) x = mu.imli_counter1;
			else if (s->p1 == 2) x = mu.imli_counter2;
			else if (s->p1 == 3) x = mu.imli_counter3;
			else if (s->p1 == 4) x = mu.imli_counter4;
			else assert (0);
			break;
		case PATH:
			x = hash_path (s->p1, s->p2);
			break;
		case TAGE:
			if (s->p1 >= 0) x = *global_tage_pred << s->p1;
			if (s->p2 >= 0) {
				int LowConf = !!(*global_tage_conf & 4);
				int MedConf = !!(*global_tage_conf & 8);
				int HiConf = !!(*global_tage_conf & 16);
				unsigned int c = 0;
				if (LowConf) c = 1;
				if (MedConf) c = 2;
				if (HiConf) c = 3;
				x ^= c << s->p2;
			}
			break;
		case BACKPATH:
			x = hash_backpath (s->p1, s->p2);
			break;
		case LOCAL:
			if (s->p2 <= 63) {
				x = mu.local_histories[hash_local() % nlocal_histories][0] >> s->p1;
				if (s->p1 != -1) x &= ((1ull<<((s->p2)-(s->p1)))-1);
			} else {
				x = fold_hist (mu.local_histories[hash_local() % nlocal_histories], s->p1, s->p2, block_size);
			}
			break;
		case BLURRYPATH:
			x = hash_blurry (s->p1, s->p2, s->p3);
			break;
		case RECENCYPOS:
			x = hash_recencypos (pc2, s->p1, t);
			break;
		default: 
			printf ("unknown feature type? %d\n", (int) s->type);
			assert (0);
		}
		return x;
	}

	// compute the perceptron output as u.yout

	void compute_output (unsigned int* global_tage_pred, unsigned int* global_tage_conf) {
		// initialize sum

		u.yout = 0;

		// for each feature...

		uint64_t indices[MAX_TABLES];
		history_spec *myspecs = specv;
		for (int i=0; i<num_tables; i++) {
			// get the hash to index the table
			uint64_t h = get_hash (&myspecs[i], u.pc, u.pc2, i, global_tage_pred, global_tage_conf);

			// shift the hash from the feature to xor with the hashed PC

			h <<= 9;
			h ^= u.pc2;

			// hash with 4

			static int h0 = 4, h1 = 1, h2 = 2, h3 = 3;
			h = hash (h, h0);

			// selectively hash with other values based on flags set in the feature

			if (myspecs[i].xorflags & XOR_HASH1) h = hash (h, h1);
			if (myspecs[i].xorflags & XOR_HASH2) h = hash (h, h2);
			if (myspecs[i].xorflags & XOR_HASH3) h = hash (h, h3);

			// record this index

			indices[i] = h;
		}


		// compute the perceptron sum

		for (int i=0; i<num_tables; i++) {

			// compute the index

			unsigned int h = indices[i] % table_sizes[i];

			// record it for later use in updating

			u.indices[i] = h;

			// apply the transfer function to the weight and add to yout

			u.yout += transfer (tables[i][h].val);
		}
	}

	// hash a key with the i'th hash function using the Kirsch-Mitzenmache
	// trick of linearly combining two hash functions with i as the
	// slope. the value of i can be tuned for various hashes. the tuned
	// values are probably about as scientifically valid as a lucky
	// rabbit's foot but they yield slightly better results than other values

	uint64_t hash (uint64_t key, uint64_t i) {
		return dan_hash::hash2 (key) * i + dan_hash::hash1 (key);
	}

	// make a prediction

	mpp_branch_update *lookup (unsigned int pc, uint64_t dynamic_id, unsigned int* global_tage_pred, unsigned int* global_tage_conf) {
		// get different PC hashes
		u.pc = pc;
		u.pc2 = pc >> 2;
		u.hpc = hash_pc (pc);

		// compute the perceptron output

		compute_output (global_tage_pred, global_tage_conf);

		// predict taken if output exceeds 0

		u.prediction (u.yout >= 0);

		// record the confidence for combining with the higher level predictor

		u.confidence = u.yout;

		// return a pointer to the state for speculative update

		return &u;
	}

	// adaptive theta training, adapted from O-GEHL which is about the
	// last time anyone made an improvement to the perceptron learning
	// algorithm for branch prediction. tagging, weight decay, learning
	// rates, weird narrow floating point formats, etc. etc. none of that
	// other shit works I've tried it all.

	void theta_setting (bool correct, double a) {
		if (!correct) {
			theta++;
		} else if (a < theta) {
			theta--;
		}
		if (theta < min_theta) theta = min_theta;
		if (theta > max_theta) theta = max_theta;
	}

	// saturating increment or decrement 

	int satincdec (int c, bool taken) {
		if (c == -32) {
			// uninitialized weight; pretend it was 0
			if (taken) return 1; else return -1;
		}
		if (taken) {
			if (c < 31) c++;
		} else {
			if (c > -31) c--;
		}
		return c;
	}

	// train the perceptron predictor

	void train (bool taken) {
		// was the prediction correct?

		int y = u.yout;
		if (!taken) y = -y;

		bool correct = y >= 0.0;

		// train if the prediction was incorrect or the magnitude of the output fails to exceed alpha * theta

		double a = fabs (alpha * u.yout);
		bool do_train = !correct || (a <= theta);
		if (!do_train) return;

		// remember that we updated the predictor

		u.updated = true;

		// adaptive theta tuning
	
		theta_setting (correct, a);
	
		// train the weights
	
		for (int i=0; i<num_tables; i++) {
			// increment/decrement if taken/not taken
			
			Weight *w = &tables[i][u.indices[i]];
			w->val = satincdec (w->val, taken);
		}
	}

	// called when we have speculatively updated weights but might have
	// done it based on a wrong prediction

	void retrain (bool taken) {
		// did we train the predictor with the right outcome? yes? then we're done.

		if (u.overall_prediction == taken) return;

		// uh-oh, we trained the wrong way! fix it.

		for (int i=0; i<num_tables; i++) {
			// increment/decrement if taken/not taken
			Weight *w = &tables[i][u.indices[i]];

			// roll back the wrong training
			w->val = satincdec (w->val, taken);

			// do the right training
			w->val = satincdec (w->val, taken);
		}

		// we also messed up theta when we trained speculatively. fix that too.

		double a = fabs (alpha * u.yout);

		// roll back the messed up theta to what it was before

		theta_setting (u.prediction() == taken, a);

		// set theta based on this correct training

		theta_setting (u.prediction() == taken, a);
	}

	~mpp_inside (void) {
	}

	// update the histories with ground truth from the simulator and speculatively update the prediction tables with the prediction

	void spec_update (mpp_branch_update *p, uint64_t target, bool taken, bool pred, int type, bool filtered, uint64_t id) {
		// speculatively train the predictor USING THE PREDICTION NOT THE GROUND TRUTH

		u.updated = false;
		u.overall_prediction = pred;

		// if the branch wasn't filtered...

		if (!filtered) 

			// and if we're in speculative update mode...

			if (*speculatively_update_tables) 
	
				// then speculatively train the weights tables and theta using the prediction

				train (pred);

		// update the histories using the ground truth

		// mask values for whether or not to record a filtered branch into a history register 

#define RECORD_FILTERED_IMLI	1
#define RECORD_FILTERED_GHIST	2
#define RECORD_FILTERED_PATH	4
#define RECORD_FILTERED_ACYCLIC	8
#define RECORD_FILTERED_MOD	16
#define RECORD_FILTERED_BLURRY	32
#define RECORD_FILTERED_LOCAL	64	// should never record a filtered local branch - duh!
#define RECORD_FILTERED_RECENCY	128

		// four different styles of IMLI

		if (!filtered || (record_mask & RECORD_FILTERED_IMLI)) {
			if (target < u.pc) {
				if (taken)
					mu.imli_counter1++;
				else
					mu.imli_counter1 = 0;
				if (!taken)
					mu.imli_counter2++;
				else
					mu.imli_counter2 = 0;
			} else {
				if (taken)
					mu.imli_counter3++;
				else
					mu.imli_counter3 = 0;
				if (!taken)
					mu.imli_counter4++;
				else
					mu.imli_counter4 = 0;
			}
		}

		// we can hash the branch outcome with a PC bit. doesn't really help.

		bool hashed_taken = hash_taken ? (taken ^ !(u.pc & (1<<htbit))) : taken;
		
		// record into backwards ghist

		if (!filtered || (record_mask & RECORD_FILTERED_GHIST)) {
			if (target < u.pc) {
				update_backglobal_hist (hashed_taken);
			}
		}

		// record into ghist

		if (!filtered || (record_mask & RECORD_FILTERED_GHIST)) {
			update_global_hist (hashed_taken);
		}

		// record into path history

		if (!filtered || (record_mask & RECORD_FILTERED_PATH)) {
			memmove (&mu.path_history[1], &mu.path_history[0], sizeof (unsigned short int) * (path_length-1));
			mu.path_history[0] = u.pc2;
		}

		// backward path history

		if (!filtered || (record_mask & RECORD_FILTERED_PATH)) {
			if (target < u.pc) {
				memmove (&mu.back_path[1], &mu.back_path[0], sizeof (unsigned short int) * (MAX_PATHHIST-1));
				mu.back_path[0] = u.pc2;
			}
		}

		// record into acyclic history

		if (!filtered || (record_mask & RECORD_FILTERED_ACYCLIC)) {
			for (int i=0; i<MAX_ACYCLIC; i++) {
				mu.acyclic_histories[i][u.hpc%(i+2)] = hashed_taken;
			}
		}

		// record into modulo path history

		if (!filtered || (record_mask & RECORD_FILTERED_MOD)) {
			for (int ii=0; ii<nmodpath_histories; ii++) {
				int i = modpath_indices[ii];
				if (u.hpc % (i+2) == 0) {
					memmove (&mu.modpath_histories[i][1], &mu.modpath_histories[i][0], sizeof (unsigned short int) * (modpath_lengths[ii]-1));
					mu.modpath_histories[i][0] = u.pc2;
				}
			}
		}

		// update blurry history

		if (!filtered || (record_mask & RECORD_FILTERED_BLURRY)) {
			for (int i=0; i<MAX_BLURRY; i++) {
				unsigned int z = u.pc >> i;
				if (mu.blurrypath_histories[i][0] != z) {
					memmove (&mu.blurrypath_histories[i][1], &mu.blurrypath_histories[i][0], sizeof (unsigned int) * (MAX_BLURRY2-1));
					mu.blurrypath_histories[i][0] = z;
				}
			}
		}

		// record into modulo pattern history

		if (!filtered || (record_mask & RECORD_FILTERED_MOD)) {
			for (int ii=0; ii<nmodhist_histories; ii++) {
				int i = modhist_indices[ii];
				if (u.hpc % (i+2) == 0) {
					memmove (&mu.mod_histories[i][1], &mu.mod_histories[i][0], modhist_lengths[ii]-1);
					mu.mod_histories[i][0] = hashed_taken;
				}
			}
		}

		// insert this PC into the recency stack

		if (!filtered || (record_mask & RECORD_FILTERED_RECENCY)) {
			insert_recency (u.pc2);
		}

		// record into a local history

		if (!filtered || (record_mask & RECORD_FILTERED_LOCAL)) {
			update_hist (mu.local_histories[hash_local() % nlocal_histories], taken);
		}
	}

	// update the prediction tables non-speculatively maybe

	void update (mpp_branch_update *p, unsigned int target, bool taken, int type, bool do_train, bool filtered, uint64_t dynamic_id) {
		u = * (mpp_update *) p;

		// if we already updated the predictor speculatively...

		if (u.updated) {

			// must not have filtered it if we updated it

#if 0
			assert (!filtered);

			// if we updated the prediction tables after
			// predicting, see if the prediction we used was wrong
			// and correct the training

			retrain (taken);
#endif
			retrain (taken); // FIXME; this is only if the Bloom filter can give false negative
		} else {
			if (!filtered) {
				// if we get here the branch must have been non-trivial (i.e. observed both taken and not taken)
				if (taken != u.overall_prediction || !(*speculatively_update_tables)) {
					// we need to train because we didn't
					// update the predictor, either because
					// the branch just became non-trivial or
					// we're in nonspeculative update mode

					train (taken);
				}
			}
		}
        }

	// shift bits from a non-conditional branch into the global history

	void doshift (unsigned int pc, unsigned int target, unsigned int pcflag, unsigned int targetflag) {
		target >>= pcbit;
		pc >>= pcbit;
		if (xflag & pcflag) for (int i=0; i<xn; i++) { update_global_hist (pc & 1); pc >>= 1; }
		if (xflag & targetflag) for (int i=0; i<xn; i++) { update_global_hist (target & 1); target >>= 1; }
	}

	// update ghist and path history on branches that aren't conditional

	void nonconditional_branch (unsigned int pc, unsigned int target, int type) {
		unsigned short int pc2 = pc >> 2;

		if (!xflag) {
			update_global_hist (!(pc & (1<<pcbit)));
		}
#define X_JMP_PC	1
#define X_JMP_TARGET	2
#define X_RET_PC	4
#define X_RET_TARGET	8
#define X_IND_PC	16
#define X_IND_TARGET	32
#define X_CALL_PC	64
#define X_CALL_TARGET	128

		if (type == OPTYPE_RET_UNCOND) doshift (pc, target, X_RET_PC, X_RET_TARGET);
		if (type == OPTYPE_JMP_DIRECT_UNCOND) doshift (pc, target, X_JMP_PC, X_JMP_TARGET);
		if (type == OPTYPE_CALL_DIRECT_UNCOND) doshift (pc, target, X_CALL_PC, X_CALL_TARGET);
		if (type == OPTYPE_CALL_INDIRECT_UNCOND) doshift (pc, target, X_IND_PC, X_IND_TARGET);
		memmove (&mu.path_history[1], &mu.path_history[0], sizeof (unsigned short int) * (path_length-1));
		mu.path_history[0] = pc2;
	}
};


} // namespace mppspace

#endif // _MPP_INSIDE_H_
