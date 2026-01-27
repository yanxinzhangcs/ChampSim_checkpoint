#ifndef _LOCAL_HIST_H_
#define _LOCAL_HIST_H_

// This file contains a local history perceptron

#include <array>
#include <cstdlib>
#include <deque>
#include <queue>
#include <unordered_map>
#include <unordered_set>
#include "saturating_counter.h"

// Perceptron configuration
#define L_PERCEP_LOG2_TABLE_SIZE 8
#define L_PERCEP_HASH_ITERATIONS 2

#define L_PERCEP_WEIGHT_BITS 10
#define L_PERCEP_BIAS_BITS 12
#define L_PERCEP_LOG2_BIAS_ENTRIES 1 /* value of 4 seems to reduce performance */
#define L_PERCEP_THETA_BITS 10
#define L_PERCEP_TC_BITS 7

#define L_PERCEP_THETA_INC 8
#define L_PERCEP_WEIGHT_THRESH 2

#define L_PERCEP_NUM_ENTRIES 32
#define L_PERCEP_QUEUE_SIZE 64

#define L_PERCEP_BASELINE_COMP_BITS 6
#define L_PERCEP_STABLE_CNT_BITS 8

#define L_PERCEP_GRACE_PERIOD_BITS 9
#define L_PERCEP_GRACE_PERIOD_THRES (1 << L_PERCEP_GRACE_PERIOD_BITS) - 1

#define L_PERCEP_TIME_ALIVE_BITS 16

// Number of weight tables
constexpr uint16_t L_PERCEP_NUM_TABLES = 64;

// Returns the stride size after table x
constexpr uint16_t STRIDE_SIZE(uint16_t x) {
	if (x <= 10) {
		return 0;
	} else {
		return 1 + 3.0/L_PERCEP_NUM_TABLES * x;
	}
}

// Returns the window size in of history for table x
constexpr uint16_t WINDOW_SIZE(uint16_t x) {
	if (x <= 10) {
		return x + 1;
	} else {
		return 8 + 4.0/L_PERCEP_NUM_TABLES * x;
	}
}

// Function to calculate history length at compile time
template <uint16_t N>
constexpr uint16_t sum_funcs() {
    if constexpr (N == 0) return STRIDE_SIZE(0);
    else return STRIDE_SIZE(N) + sum_funcs<N - 1>();
}

constexpr uint16_t L_PERCEP_HIST_LEN = sum_funcs<L_PERCEP_NUM_TABLES - 2>() + WINDOW_SIZE(L_PERCEP_NUM_TABLES-1);



// --- Memory Calculations ---
#define L_PERCEP_ENTRY_BITS (62 /* PC */ \
                             + L_PERCEP_HIST_LEN /* Local history shift register */ \
                             + L_PERCEP_BIAS_BITS * (1 << L_PERCEP_LOG2_BIAS_ENTRIES) /* bias table */ \
                             + L_PERCEP_THETA_BITS /* training theshold theta */ \
                             + L_PERCEP_TC_BITS /* TC coutner to update theta */ \
                             + L_PERCEP_BASELINE_COMP_BITS \
                             + L_PERCEP_STABLE_CNT_BITS \
							 + L_PERCEP_GRACE_PERIOD_BITS \
							 + L_PERCEP_TIME_ALIVE_BITS )

// Single perceptron memory size
#define L_PERCEP_MEM_BITS (L_PERCEP_ENTRY_BITS * L_PERCEP_NUM_ENTRIES \
                           + 62 * L_PERCEP_QUEUE_SIZE \
                           + L_PERCEP_WEIGHT_BITS * L_PERCEP_NUM_TABLES * (1 << L_PERCEP_LOG2_TABLE_SIZE))


// Data type to return on prediction
struct LHist_Percep_Pred_Info {
	int32_t pred;
	bool high_confidence;
	bool med_confidence;
	bool low_confidence;
};


class LHist_Perceptron {
private:
	
	// Many tables to store weights for all perceptrons
	// Uses L_PERCEP_WEIGHT_BITS * L_PERCEP_NUM_TABLES * (1 << L_PERCEP_LOG2_TABLE_SIZE) bits
	std::array<std::array<SignedSatCounter<L_PERCEP_WEIGHT_BITS>, 1 << L_PERCEP_LOG2_TABLE_SIZE>, L_PERCEP_NUM_TABLES> weights;

	class Entry {
	public:
		// PC of the entry
		// 62 bits
		uint64_t PC;

		// Store the branch's local history. Initialized to all untaken.
		// Uses L_PERCEP_HIST_LEN bits of memory
		std::deque<bool> local_hist;

		// Stores prediction bias
		// Uses L_PERCEP_BIAS_BITS * (1 << L_PERCEP_LOG2_BIAS_ENTRIES) bits of memory
		std::array<SignedSatCounter<L_PERCEP_BIAS_BITS>, (1 << L_PERCEP_LOG2_BIAS_ENTRIES)> bias;

		// Threshold for weight update
		// Uses L_PERCEP_THETA_BITS bits of memory
		UnsignedSatCounter<L_PERCEP_THETA_BITS> theta;

		// Counter for dynamic updates of threshold theta
		// Uses L_PERCEP_TC_BITS
		SignedSatCounter<L_PERCEP_TC_BITS> TC;

		// Saturating counter to compare with competing predictors
		// confidence is higher when most significant bit is 1
		UnsignedSatCounter<L_PERCEP_BASELINE_COMP_BITS> baseline_comp;

		// Counter to keep track of how stable baseline_comp is
		UnsignedSatCounter<L_PERCEP_STABLE_CNT_BITS> stable_cnt;

		// Counter to keep track of how many times the entry has been used in the H2P table
		// This allows for the perceptron to be trained on a branch before it gets used or evaluated for eviction
		UnsignedSatCounter<L_PERCEP_GRACE_PERIOD_BITS> grace_period;

		// Counter to keep track of how long the entry has existed in the H2P table
		// If it isn't used for a while, it will be evicted
		UnsignedSatCounter<L_PERCEP_TIME_ALIVE_BITS> time_alive;

		// Stores old histories mapped to via unique instruction id
		// Does not count towards memory limit
		std::unordered_map<uint64_t, std::deque<bool>> old_histories;

		Entry() {}

		Entry(uint64_t _PC) :
			local_hist(L_PERCEP_HIST_LEN, false), PC(_PC) {

			theta.set(1.93 * L_PERCEP_NUM_TABLES * L_PERCEP_HASH_ITERATIONS + 14);
			assert(local_hist.size() == L_PERCEP_HIST_LEN);
		}

		~Entry() {
			// Ensure local hist size remains correct
			assert(local_hist.size() == L_PERCEP_HIST_LEN);

			int maxBias = 0;
			for (auto& b : bias) {
				maxBias = std::max(std::abs(b.get()), maxBias);
			}
			printf("L_PERCEP PC=0x%08lX", PC);
			printf(", theta=%4d", theta.get());
			printf(", max bias=%4d", maxBias);
			printf(", baseline_comp=%3d, stable_cnt=%3d", baseline_comp.get(), stable_cnt.get());
			printf(", grace_period=%3d", grace_period.get());
			printf(", time_alive=%3d\n", time_alive.get());
		}
	};

	// List of branches to predict
	// Maps PC to entry
	// Uses L_PERCEP_ENTRY_BITS * L_PERCEP_NUM_ENTRIES of memory
	std::unordered_map<uint64_t, Entry> pc_list;

	// Queued branches
	// Uses 62 * L_PERCEP_QUEUE_SIZE bits of memory
	std::queue<uint64_t> entry_queue;
	std::unordered_set<uint64_t> entry_queue_lookup;

	// Hash to size of L_PERCEP_LOG2_TABLE_SIZE
	uint32_t hash_idx(uint64_t PC, uint64_t window, uint64_t iteration) const {
		uint64_t h = (PC ^ (PC >> 16));
		h ^= window + 0x9e3779b97f4a7c15ULL + (h<<6) + (h>>2);
		h ^= iteration + 0x7f4a7c15e3779b97ULL + (h<<6) + (h>>2);

		h ^= h >> 33;
		h *= 0xff51afd7ed558ccdULL;
		h ^= h >> 33;
		h *= 0xc4ceb9fe1a85ec53ULL;
		h ^= h >> 33;

		return uint32_t(h & ((1ULL << L_PERCEP_LOG2_TABLE_SIZE) - 1));
	}


public:
	LHist_Perceptron() {}
	~LHist_Perceptron() {}

	// Predict this branch
	LHist_Percep_Pred_Info predict(uint64_t PC) const {
		// Assert that the PC exists in perceptron
		assert(pc_list.count(PC));

		auto& local_hist = pc_list.at(PC).local_hist;
		auto& bias = pc_list.at(PC).bias;
		auto& theta = pc_list.at(PC).theta;

		// Choose a bias with early history bits
		uint16_t bias_idx = 0;
		for (int i=0; i<L_PERCEP_LOG2_BIAS_ENTRIES; ++i) {
			bias_idx <<= 1;
			bias_idx |= local_hist.at(i) ? 1 : 0;
		}

		int32_t sum = (bias.at(bias_idx).get() << 3);

		// Compute sum of weights
		for (int iteration=0; iteration<L_PERCEP_HASH_ITERATIONS; ++iteration) {
			uint64_t pos = 0;
			for (int i=0; i<L_PERCEP_NUM_TABLES; ++i) {

				// Shift history
				uint64_t idx = 0;
				for (int j=0; j<WINDOW_SIZE(i); ++j) {
					idx <<= 1;
					idx |= local_hist.at(pos + j);
				}

				uint64_t hashed_idx = hash_idx(PC, idx, iteration);

				if (abs(weights[i][hashed_idx].get()) >= L_PERCEP_WEIGHT_THRESH) {
					sum += weights[i][hashed_idx].get();
				}

				pos += STRIDE_SIZE(i);
			}
		}

		LHist_Percep_Pred_Info ret;
		ret.pred = sum;
		// Compute how confident the prediction is
		ret.high_confidence = (abs(sum) > theta.get()) && pc_list.at(PC).baseline_comp.MSB();
		ret.med_confidence = !ret.high_confidence && pc_list.at(PC).baseline_comp.MSB();
		ret.low_confidence = !ret.high_confidence && !ret.med_confidence;

		return ret;
	}


	// Update the state speculatively
	void history_update(uint64_t PC, uint64_t id, bool predDir) {
		if (pc_list.count(PC)) {
			// Make a copy of the current state
			std::deque<bool> copied_hist(pc_list[PC].local_hist);
			pc_list[PC].old_histories.emplace(id, copied_hist);

			// Update the current state
			pc_list[PC].local_hist.pop_back();
			pc_list[PC].local_hist.push_front(predDir);
		}
	};


	// Update perceptron state on branch resolve
	// "finalPred" is the prediction that was used
	// "bestCompetitor" indicates the most correct competitor predictor
	void update(uint64_t PC, uint64_t id, bool resolveDir, bool finalPred, int32_t percepPred, bool bestCompetitor) {
		assert(pc_list.count(PC));

		// Catch if this perceptron was created between prediction and resolve
		if (pc_list[PC].old_histories.count(id) == 0) {
			// Do not update the state here. Causes errors in training initial updates
			return;
		}

		auto& old_hist = pc_list[PC].old_histories.at(id);
		auto& theta = pc_list[PC].theta;
		auto& bias = pc_list[PC].bias;
		auto& TC = pc_list[PC].TC;
		bool percepPredTaken = percepPred >= 0;

		// increment time alive for all entries
		for (auto& entry : pc_list) {
			entry.second.time_alive += 1;
		}

		// Reset time alive for this entry
		pc_list[PC].time_alive.reset();

		// Update weights and bias if incorrect or less than threshold
		if (resolveDir != percepPredTaken || std::abs(percepPred) <= theta.get()) {
			uint16_t bias_idx = 0;
			for (int i=0; i<L_PERCEP_LOG2_BIAS_ENTRIES; ++i) {
				bias_idx <<= 1;
				bias_idx |= old_hist.at(i) ? 1 : 0;
			}

			// Update bias
			if (resolveDir) {
				bias.at(bias_idx) += 1;
			} else {
				bias.at(bias_idx) -= 1;
			}

			// Update weights
			for (int iteration=0; iteration<L_PERCEP_HASH_ITERATIONS; ++iteration) {
				uint64_t pos = 0;
				
				for (int i=0; i<L_PERCEP_NUM_TABLES; ++i) {
					// Shift history
					uint64_t idx = 0;
					for (int j=0; j<WINDOW_SIZE(i); ++j) {
						idx <<= 1;
						idx |= old_hist.at(pos + j);
					}

					uint64_t hashed_idx = hash_idx(PC, idx, iteration);

					if (resolveDir) {
						weights[i].at(hashed_idx) += 1;
					} else {
						weights[i].at(hashed_idx) -= 1;
					}

					pos += STRIDE_SIZE(i);
				}
			}
		}

		// Update dynamic threshold based on O-GEHL method
		if (resolveDir != percepPredTaken) {
			TC += 1;
			if (TC.isMax()) {
				theta += L_PERCEP_THETA_INC;
				TC.reset();
			}
		} else if (std::abs(percepPred) <= theta.get()) {
			TC -= 1;
			if (TC.isMin()) {
				theta -= L_PERCEP_THETA_INC;
				TC.reset();
			}
		}

		// Correct speculative update to local history
		if (finalPred != resolveDir) {
			assert(pc_list[PC].local_hist.front() == finalPred);
			pc_list[PC].local_hist.pop_front();
			pc_list[PC].local_hist.push_front(resolveDir);
		}

		pc_list[PC].old_histories.erase(id);

		// --- Update Prediction Accuracy Trackers ---

		// Enable/Disable H2P predictor based on performance
		if (pc_list[PC].grace_period.get() < L_PERCEP_GRACE_PERIOD_THRES) {
			pc_list[PC].grace_period += 1;
		
		} else {
			if (pc_list[PC].baseline_comp.get() == 0 || pc_list[PC].baseline_comp.isMax()) {
				pc_list[PC].stable_cnt += 1;
			} else {
				pc_list[PC].stable_cnt >>= 1;
			}
		}

		// Compare perceptron to competitors
		if (bestCompetitor == resolveDir && percepPredTaken != resolveDir) {
			pc_list[PC].baseline_comp -= 1;
		} else if (bestCompetitor != resolveDir && percepPredTaken == resolveDir) {
			pc_list[PC].baseline_comp += 1;
		}
	}

	// Check if an H2P branch should be evicted for poor performance
	// If so, evict the branch and return true
	bool check_eviction(uint64_t PC) {
		if (pc_list.count(PC)) {
			if (pc_list[PC].stable_cnt.isMax() && pc_list[PC].baseline_comp.get() == 0) {
				assert(pc_list[PC].grace_period.get() >= L_PERCEP_GRACE_PERIOD_THRES);
				pc_list.erase(PC);
				if(entry_queue.size() > 0){
					uint64_t new_insert = entry_queue.front();
					pc_list.try_emplace(new_insert, new_insert);
					entry_queue.pop();
					entry_queue_lookup.erase(PC);
				} 
				return true;
			}
		}
		return false;
	}

	// Check if an H2P branch should be evicted because it hasn't been used in a while
	bool check_stale_eviction() {
		for (auto& entry : pc_list) {
			if (entry.second.time_alive.isMax()) {
				uint64_t PC = entry.first;
				pc_list.erase(PC);
				if(entry_queue.size() > 0){
					uint64_t new_insert = entry_queue.front();
					pc_list.try_emplace(new_insert, new_insert);
					entry_queue.pop();
					entry_queue_lookup.erase(PC);
				}
				return true;
			}
		}
		return false;
	}


	// Insert a PC to be tracked
	void insert(uint64_t PC) {
		// Return on PC=0 to ensure 0 can be used to encode NULL entry
		if (PC == 0) return;

		// Assert we are not inserting something that exists
		assert(!pc_list.count(PC));

		// Case where list is not full
		if (pc_list.size() < L_PERCEP_NUM_ENTRIES) {
		    pc_list.try_emplace(PC, PC);

		// Case where list is full but queue is not
		} else if (entry_queue.size() < L_PERCEP_QUEUE_SIZE) {
		    entry_queue.push(PC);
		    entry_queue_lookup.insert(PC);
		
		// Case where queue is full
		} else {
		    entry_queue_lookup.erase(entry_queue.front());
		    entry_queue.pop();
		    entry_queue.push(PC);
		    entry_queue_lookup.insert(PC);
		}
	}

	// Returns if a given PC is an entry
	bool contains(uint64_t PC) const {
	    return pc_list.count(PC);
	}

	// Returns if a given PC is a queued entry
	bool is_queued(uint64_t PC) const {
	    return entry_queue_lookup.count(PC);
	}

	// Returns if a given PC is an entry or queued to be one
	bool contains_or_queued(uint64_t PC) const {
	    return pc_list.count(PC) || entry_queue_lookup.count(PC);
	}

	// Returns the current number of entry branches
	uint16_t count() const {
	    return pc_list.size() + entry_queue.size();
	}

	// Returns if a given PC is trained enough to trust its predictions
	bool is_superior(uint64_t PC) const {
		return pc_list.at(PC).baseline_comp.MSB() && pc_list.at(PC).stable_cnt.isMax();
	}
};

#endif // _LOCAL_HIST_H_
