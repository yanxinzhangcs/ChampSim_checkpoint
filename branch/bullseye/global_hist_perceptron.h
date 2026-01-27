#ifndef _GLOBAL_HIST_H_
#define _GLOBAL_HIST_H_
// By Emet Behrendt
// This file contains a global history perceptron

#include <array>
#include <deque>
#include <unordered_map>
#include <unordered_set>
#include "saturating_counter.h"

// --- Configuration ---
#define G_PERCEP_HIST_LEN 128
#define G_PERCEP_WEIGHT_BITS 12
//#define G_PERCEP_WINDOW_SIZE 4
#define G_PERCEP_BIAS_BITS 10
#define G_PERCEP_LOG2_BIAS_ENTRIES 4
#define G_PERCEP_THETA_BITS 14
#define G_PERCEP_TC_BITS 7

#define G_PERCEP_THETA_INC 8
#define G_PERCEP_WEIGHT_THRESH 2

#define G_PERCEP_NUM_ENTRIES 16
#define G_PERCEP_QUEUE_SIZE 64

#define G_PERCEP_BASELINE_COMP_BITS 6
#define G_PERCEP_STABLE_CNT_BITS 8

#define G_PERCEP_GRACE_PERIOD_BITS 9
#define G_PERCEP_GRACE_PERIOD (1 << G_PERCEP_GRACE_PERIOD_BITS) - 1

#define G_PERCEP_TIME_ALIVE_BITS 16

// --- Memory Calculation ---
// Single perceptron memory size
#define G_PERCEP_ENTRY_BITS (62 \
                             + G_PERCEP_HIST_LEN * G_PERCEP_WEIGHT_BITS \
                             + G_PERCEP_BIAS_BITS * (1 << G_PERCEP_LOG2_BIAS_ENTRIES) \
                             + G_PERCEP_THETA_BITS \
                             + G_PERCEP_TC_BITS \
                             + G_PERCEP_BASELINE_COMP_BITS \
                             + G_PERCEP_STABLE_CNT_BITS \
							 + G_PERCEP_GRACE_PERIOD_BITS \
							 + G_PERCEP_TIME_ALIVE_BITS)

// Single perceptron memory size
#define G_PERCEP_MEM_BITS (G_PERCEP_HIST_LEN \
                           + G_PERCEP_ENTRY_BITS * G_PERCEP_NUM_ENTRIES \
                           + 62 * G_PERCEP_QUEUE_SIZE)


struct GHist_Percep_Pred_Info {
	int32_t pred;
	bool high_confidence;
	bool med_confidence;
	bool low_confidence;
};


class GHist_Perceptron {
private:
	
	// Stores the global history
	// Uses G_PERCEP_HIST_LEN bits of memory
	// TODO: don't double count the global history in both TAGE and GHist Perceptron
	std::deque<bool> global_hist;

	// Store weights for a perceptron
	// Uses G_PERCEP_HIST_LEN * G_PERCEP_WEIGHT_BITS bits of memory
	//std::array<std::array<SignedSatCounter<G_PERCEP_WEIGHT_BITS>, 1 << G_PERCEP_WINDOW_SIZE>, G_PERCEP_HIST_LEN - G_PERCEP_WINDOW_SIZE> weights;

	class Entry {
	public:
		// PC of the entry
		// 62 bits
		uint64_t PC;

		// Uses G_PERCEP_HIST_LEN * G_PERCEP_WEIGHT_BITS bits of memory
		std::array<SignedSatCounter<G_PERCEP_WEIGHT_BITS>, G_PERCEP_HIST_LEN> weights2;

		// Stores prediction bias
		// Uses G_PERCEP_BIAS_BITS bits of memory
		std::array<SignedSatCounter<G_PERCEP_BIAS_BITS>, 1 << G_PERCEP_LOG2_BIAS_ENTRIES> bias;

		// Treshold for weight update
		// Uses G_PERCEP_THETA_BITS bits of memory
		UnsignedSatCounter<G_PERCEP_THETA_BITS> theta;

		// Counter for dynamic updates of threshold theta
		// Uses G_PERCEP_TC_BITS
		SignedSatCounter<G_PERCEP_TC_BITS> TC;

		// Saturating counter to compare with competing predictors
		// confidence is higher when most significant bit is 1
		UnsignedSatCounter<G_PERCEP_BASELINE_COMP_BITS> baseline_comp;

		// Counter to keep track of how stable baseline_comp is
		UnsignedSatCounter<G_PERCEP_STABLE_CNT_BITS> stable_cnt;

		// Stores old histories mapped to via unique instruction id
		// Does not count towards memory limit
		std::unordered_map<uint64_t, std::deque<bool>> old_histories;

		// Counter to keep track of how long the entry has existed in the H2P table
		// This is used to allow for the perceptron to be trained on a branch before it gets used or evaluated for eviction
		UnsignedSatCounter<G_PERCEP_GRACE_PERIOD_BITS> grace_period;

		// Counter to keep track of how long the entry has existed in the H2P table
		// If it isn't used for a while, it will be evicted
		UnsignedSatCounter<G_PERCEP_TIME_ALIVE_BITS> time_alive;

		Entry() {}

		Entry(uint64_t _PC) : PC(_PC) {
			theta.set(2.5 * G_PERCEP_HIST_LEN);
		}

		~Entry() {
			int maxBias = 0;
			for (auto& b : bias) {
				maxBias = std::max(std::abs(b.get()), maxBias);
			}
			printf("G_PERCEP PC=0x%08lX", PC);
			printf(", theta=%4d", theta.get());
			printf(", max bias=%4d", maxBias);
			printf(", baseline_comp=%3d, stable_cnt=%3d", baseline_comp.get(), stable_cnt.get());
			printf(", grace_period=%3d", grace_period.get());
			printf(", time_alive=%3d\n", time_alive.get());
		}
	};

	// List of branches to predict
	// Maps PC to entry
	// Uses G_PERCEP_ENTRY_BITS * G_PERCEP_NUM_ENTRIES of memory
	std::unordered_map<uint64_t, Entry> pc_list;

	// Queued branches
	// Uses 62 * G_PERCEP_QUEUE_SIZE bits of memory
	std::queue<uint64_t> entry_queue;
	std::unordered_set<uint64_t> entry_queue_lookup;


public:
	GHist_Perceptron() : global_hist(G_PERCEP_HIST_LEN, false) {
		// for (auto& set : weights) {
		// 	set.fill(SignedSatCounter<G_PERCEP_WEIGHT_BITS>(0));
		// }

		assert(global_hist.size() == G_PERCEP_HIST_LEN);
	}

	~GHist_Perceptron() {
		assert(global_hist.size() == G_PERCEP_HIST_LEN);
	}

	// Predict this branch
	GHist_Percep_Pred_Info predict(uint64_t PC) const {
		// Assert that the PC exists in perceptron
		assert(pc_list.count(PC));

		auto& bias = pc_list.at(PC).bias;
		auto& theta = pc_list.at(PC).theta;

		uint16_t bias_idx = 0;
		for (int i=0; i<G_PERCEP_LOG2_BIAS_ENTRIES; ++i) {
			bias_idx <<= 1;
			bias_idx |= global_hist.at(i) ? 1 : 0;
		}

		int32_t sum = (bias.at(bias_idx).get() << 3);

		int64_t idx = 0;

		// for (int i=0; i<G_PERCEP_WINDOW_SIZE-1; ++i) {
		// 	idx <<= 1;
		// 	idx |= global_hist[i];
		// }

		// for (int i=0; i<G_PERCEP_HIST_LEN - G_PERCEP_WINDOW_SIZE; ++i) {
		// 	// Shift bit into register
		// 	idx <<= 1;
		// 	idx |= global_hist.at(i + G_PERCEP_WINDOW_SIZE);
		// 	idx &= (1 << G_PERCEP_WINDOW_SIZE) - 1;

		// 	if (abs(weights[i][idx].get()) >= G_PERCEP_WEIGHT_THRESH) {
		// 		sum += weights[i][idx].get();
		// 	}
		// }

		auto& weights2 = pc_list.at(PC).weights2;
		for (int i=0; i<G_PERCEP_HIST_LEN; ++i) {
			if (abs(weights2[i].get()) >= G_PERCEP_WEIGHT_THRESH) {
				sum += (global_hist.at(i) ? weights2.at(i).get() : -weights2.at(i).get());
			}
		}

		GHist_Percep_Pred_Info ret;
		ret.pred = sum;
		ret.high_confidence = (abs(sum) > theta.get()) && pc_list.at(PC).baseline_comp.MSB();
		ret.med_confidence = !ret.high_confidence && pc_list.at(PC).baseline_comp.MSB();
		ret.low_confidence = !ret.high_confidence && !ret.med_confidence;

		return ret;
	}

	// Update the state speculatively when a branch is 
	void history_update(uint64_t PC, uint64_t id, bool predDir) {
		if (pc_list.count(PC)) {
			// Make a copy of the current state
			std::deque<bool> copied_hist(global_hist);
			pc_list[PC].old_histories.emplace(id, copied_hist);
		}

		// Update the current state
		global_hist.pop_back();
		global_hist.push_front(predDir);
	};

	// Update perceptron state on branch resolve
	void update(uint64_t PC, uint64_t id, bool resolveDir, bool finalPred, int32_t percepPred, bool bestCompetitor) {
		assert(pc_list.count(PC));

		// Catch if this perceptron was created between prediction and resolve
		if (pc_list[PC].old_histories.count(id) == 0) {
			// Do not update the state here. Causes errors in training initial updates
			return;
		}

		auto& old_hist = pc_list[PC].old_histories[id];
		auto& theta = pc_list[PC].theta;
		auto& bias = pc_list[PC].bias;
		auto& TC = pc_list[PC].TC;
		bool percepPredTaken = (percepPred >= 0);

		// increment time alive for all entries
		for (auto& entry : pc_list) {
			entry.second.time_alive += 1;
		}

		// Reset time alive for this entry
		pc_list[PC].time_alive.reset();

		// Update weights and bias if incorrect or less than threshold
		if (resolveDir != percepPredTaken || std::abs(percepPred) <= theta.get()) {
			uint16_t bias_idx = 0;
			for (int i=0; i<G_PERCEP_LOG2_BIAS_ENTRIES; ++i) {
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
			// int64_t idx = 0;

			// for (int i=0; i<G_PERCEP_WINDOW_SIZE-1; ++i) {
			// 	idx <<= 1;
			// 	idx |= old_hist[i];
			// }

			// for (int i=0; i<G_PERCEP_HIST_LEN - G_PERCEP_WINDOW_SIZE; ++i) {
			// 	// Shift bit into register
			// 	idx <<= 1;
			// 	idx |= old_hist.at(i + G_PERCEP_WINDOW_SIZE);
			// 	idx &= (1 << G_PERCEP_WINDOW_SIZE) - 1;

			// 	if (resolveDir) {
			// 		weights[i].at(idx) += 1;
			// 	} else {
			// 		weights[i].at(idx) -= 1;
			// 	}
			// }

			auto& weights2 = pc_list[PC].weights2;
			for (int i=0; i<G_PERCEP_HIST_LEN; ++i) {
				if (old_hist[i] == resolveDir) {
					weights2.at(i) += 1;
				} else {
					weights2.at(i) -= 1;
				}
			}
		}

		// Update dynamic threshold based on O-GEHL method
		if (resolveDir != percepPredTaken) {
			TC += 1;
			if (TC.isMax()) {
				theta += G_PERCEP_THETA_INC;
				TC.reset();
			}
		} else if (std::abs(percepPred) <= theta.get()) {
			TC -= 1;
			if (TC.isMin()) {
				theta -= G_PERCEP_THETA_INC;
				TC.reset();
			}
		}

		refine_ghist(resolveDir, finalPred);

		pc_list[PC].old_histories.erase(id);

		// --- Update Prediction Accuracy Trackers ---

		// Enable/Disable H2P predictor based on performance

		if (pc_list[PC].grace_period.get() < G_PERCEP_GRACE_PERIOD) {
			
			pc_list[PC].grace_period += 1;
		} else {
			
			if (pc_list[PC].baseline_comp.get() == 0 || pc_list[PC].baseline_comp.isMax()) {
				pc_list[PC].stable_cnt += 1;
			} else {
				pc_list[PC].stable_cnt >>= 1;
			}
		}

		if (bestCompetitor == resolveDir && percepPredTaken != resolveDir) {
			pc_list[PC].baseline_comp -= 1;
		} else if (bestCompetitor != resolveDir && percepPredTaken == resolveDir) {
			pc_list[PC].baseline_comp += 1;
		}


		// --- Check for Eviction ---
		// TODO

		// // --- Check for Eviction ---
		// if (pc_list[PC].stable_cnt.isMax() && pc_list[PC].baseline_comp.get() == 0) {
		// 	pc_list.erase(PC);
		// 	if(entry_queue.size() > 0){
		// 		uint64_t new_insert = entry_queue.front();
		// 		pc_list.try_emplace(new_insert, new_insert);
		// 		entry_queue.pop();
		// 		entry_queue_lookup.erase(PC);
		// 	} 
		// }
	}

	bool check_eviction(uint64_t PC) {
		if (pc_list.count(PC)) {
			if (pc_list[PC].stable_cnt.isMax() && pc_list[PC].baseline_comp.get() == 0) {
				assert(pc_list[PC].grace_period.get() >= G_PERCEP_GRACE_PERIOD);
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


	// Refine the speculative updates in the global history from mispredictions
	void refine_ghist(bool resolveDir, bool predDir) {
		if (predDir != resolveDir) {
			assert(global_hist.front() == predDir);
			global_hist.pop_front();
			global_hist.push_front(resolveDir);
		}
	}


	// Insert a PC to be tracked
	void insert(uint64_t PC) {
		// Return on PC=0 to ensure 0 can be used to encode NULL entry
		if (PC == 0) return;

		// Assert we are not inserting something that exists
		assert(!pc_list.count(PC));

		// Case where list is not full
		if (pc_list.size() < G_PERCEP_NUM_ENTRIES) {
		    pc_list.try_emplace(PC, PC);

		// Case where list is full but queue is not
		} else if (entry_queue.size() < G_PERCEP_QUEUE_SIZE) {
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

#endif //_GLOBAL_HIST_H_
