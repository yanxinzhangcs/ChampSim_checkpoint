#ifndef _H2P_ID_H_
#define _H2P_ID_H_
// By Emet Behrendt
// This file contains a method to track hard-to-predict branches

#include <unordered_map>
#include "saturating_counter.h"

// Configuration
#define H2P_LIST_SIZE 32

#define HASHED_PC_BITS 16//31

#define H2P_ID_TABLE_WAYS 8
#define LOG2_H2P_ID_TABLE_SETS 6
#define H2P_ID_TABLE_SETS (1 << LOG2_H2P_ID_TABLE_SETS)

#define H2P_ID_LOOSE_DEF_THRESH 200000
#define H2P_ID_LOOSE_DEF_SLOPE 0.000005
#define H2P_ID_EXE_CNT_BITS 32

// Memory Size
#define H2P_ID_ENTRY_BITS (HASHED_PC_BITS - LOG2_H2P_ID_TABLE_SETS + 16 + 12)

#define H2P_ID_MEM_BITS H2P_ID_ENTRY_BITS * H2P_ID_TABLE_SETS * H2P_ID_TABLE_WAYS





// Entry in H2P branch identification table
class H2P_ID_Entry {
public:

// Function to hash PC to a smaller value for tagging
// Hash 62 bit -> 31 bit
// Hash output size stored at HASHED_PC_BITS
uint64_t hash_pc(uint64_t PC) {
    // return ((PC >> 2) ^ (PC >> 33)) & 0x7FFFFFFF;
    return (((PC >> 2) ^ (PC >> 33)) & ((1u << HASHED_PC_BITS) - 1));
}

    uint64_t PC_tag;               // HASHED_PC_BITS - LOG2_H2P_ID_TABLE_SETS bits used
    uint16_t correct_pred_cnt;     // 16 bits used
    uint16_t incorrect_pred_cnt;   // 12 bits used

    H2P_ID_Entry() {};

    H2P_ID_Entry(uint64_t PC) : 
        correct_pred_cnt(0),
        incorrect_pred_cnt(0) {

        PC_tag = hash_pc(PC) >> LOG2_H2P_ID_TABLE_SETS;
    };

    // Returns if the branch is considered hard-to-predict
    // Strictness parameter affect how strick the definition should be
    bool is_h2p(uint16_t h2p_count, const float strictness) const {
        uint32_t total = correct_pred_cnt + incorrect_pred_cnt;

        // Total number of tracked executions to be considered H2P
        uint16_t execution_thresh = (2048 + (h2p_count << 4)) * strictness;

        // Total number of tracked mispredictions to be considered H2P
        uint16_t mispred_thresh = 256 * strictness;

        // Accuracy below which H2P must exhibit
        float accuracy_thresh;
        if (h2p_count <= H2P_LIST_SIZE) {
            accuracy_thresh = 1 - (0.01f/H2P_LIST_SIZE) * h2p_count;
        } else {
            accuracy_thresh = 0.95f - (0.01f * (h2p_count - H2P_LIST_SIZE));

            accuracy_thresh = std::max(accuracy_thresh, 0.6f);
        }

        accuracy_thresh = 1 - (1 - accuracy_thresh) * strictness;

        if (total >= execution_thresh && incorrect_pred_cnt >= mispred_thresh
            && correct_pred_cnt < accuracy_thresh * total) {

            return true;
        }
        return false;
    };

    // Updates statistics based on previous prediction result
    void update(bool is_correct) {
        if (is_correct) {
            ++correct_pred_cnt;

            if (correct_pred_cnt == 0xFFFF) {
                correct_pred_cnt >>= 1;
                incorrect_pred_cnt >>= 1;
            }
        } else {
            ++incorrect_pred_cnt;

            if (incorrect_pred_cnt == 0x0FFF) {
                correct_pred_cnt >>= 1;
                incorrect_pred_cnt >>= 1;
            }
        }
    }

    // Reset entry
    void reset() {
        correct_pred_cnt = 0;
        incorrect_pred_cnt = 0;
        PC_tag = 0;
    }
};



// Hard to predict branch identification table
class H2P_ID_Table {
private:
    // This variable uses H2P_ID_ENTRY_BITS * H2P_ID_TABLE_SETS * H2P_ID_TABLE_WAYS bits
    // It may seem like more memory is required to encode a NULL entry, however such entries
    // could simply be encoded as having all counters equal to zero
    std::unordered_map<uint64_t, H2P_ID_Entry> table[H2P_ID_TABLE_SETS];    // Maps PC to entry

    // Counts the number of H2P bits
    UnsignedSatCounter<10> h2p_count;

    // Counts the number of executions since last H2P found
    UnsignedSatCounter<H2P_ID_EXE_CNT_BITS> exe_counter;

public:
// Function to hash PC to a smaller value for tagging
// Hash 62 bit -> 31 bit
// Hash output size stored at HASHED_PC_BITS
uint64_t hash_pc(uint64_t PC) {
    // return ((PC >> 2) ^ (PC >> 33)) & 0x7FFFFFFF;
    return (((PC >> 2) ^ (PC >> 33)) & ((1u << HASHED_PC_BITS) - 1));
}

    H2P_ID_Table() {};

    // Update H2P identification statistics
    // Should not be called for branches that are already H2P
    // Returns whether an H2P branch was found
    bool update(uint64_t PC, bool is_correct) {
        
        uint64_t hashed_pc = hash_pc(PC);
        bool is_h2p = false;

        int set = hashed_pc % H2P_ID_TABLE_SETS; // Hash with PC alignment

        exe_counter += 1;

        // Update existing data if PC exists in table
        if (table[set].count(hashed_pc)) {
            table[set][hashed_pc].update(is_correct);

            float strictness = 1;

            if (exe_counter.get() > H2P_ID_LOOSE_DEF_THRESH && h2p_count.get() <= H2P_LIST_SIZE) {
                strictness = std::max(0.5, 1 - (exe_counter.get() - H2P_ID_LOOSE_DEF_THRESH) * H2P_ID_LOOSE_DEF_SLOPE);
            }

            // Check for new H2P
            if (table[set][hashed_pc].is_h2p(h2p_count.get(), strictness)) {
                // Store H2P and remove from tracking
                table[set].erase(hashed_pc);

                exe_counter.reset();
                is_h2p = true;
                h2p_count += 1;
            }
        
        // Allocate space to track PC data
        } else if (!is_correct) {

            // Evict an entry if set is full
            if (table[set].size() == H2P_ID_TABLE_WAYS) {
                uint64_t evicted_PC;
                uint32_t min_sum = 0xFFFFFFFF;

                for (const auto& pair : table[set]) {
                    int sum = pair.second.correct_pred_cnt + (pair.second.incorrect_pred_cnt << 3);

                    if (sum < min_sum) {
                        evicted_PC = pair.first;
                        min_sum = sum;
                    }
                }

                assert(min_sum != 0xFFFFFFFF);

                table[set].erase(evicted_PC);
            }

            // Write new value to set
            table[set][hashed_pc] = H2P_ID_Entry(PC);
            table[set][hashed_pc].update(is_correct);
        }

        return is_h2p;
    }

    // Called when a branch is no longer H2P
    void evict_h2p(uint64_t evicted_PC) {
        h2p_count -= 1;
        // TODO: consider blacklist
    }
};

#endif //_H2P_ID_H_
