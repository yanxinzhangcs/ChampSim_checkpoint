
#ifndef _BULLSEYE_CORE_H_
#define _BULLSEYE_CORE_H_

#include <limits.h>
#include <stdlib.h>
#include <algorithm>
#include <iostream>
#include "H2P_identification.h"
#include "cbp2016_tage_sc_l.h"
#include "local_hist_perceptron.h"
#include "global_hist_perceptron.h"



// Stores past state information
struct PredInfo {
    bool final_pred;            // Prediction that was used
    bool tage_pred;             // Prediction from base (TAGE-SC-L) predictor
    LHist_Percep_Pred_Info lhist_percep_pred;  // Prediction from local history perceptron
    GHist_Percep_Pred_Info ghist_percep_pred;  // Prediction from global history perceptron
};


class SampleCondPredictor {
public:
// Get unique instruction id
uint64_t get_unique_inst_id(uint64_t seq_no, uint8_t piece) {
    assert(piece < 16);
    return (seq_no << 4) | (piece & 0x000F);
}

    PredInfo active_hist;
    std::unordered_map<uint64_t, PredInfo> pred_time_histories;

    H2P_ID_Table h2p_id_table;

    CBP2016_TAGE_SC_L tage_sc_l;
    LHist_Perceptron lhist_perceptron;
    GHist_Perceptron ghist_perceptron;

    // --- Debug Performance Tracking Variables ---
    // Does not count to memory

    // Counts the number of filtered updates
    uint64_t filtered_updates = 0;

    // Number of H2P branches predicted by TAGE vs H2P Predictor
    uint64_t h2p_with_tage = 0;
    uint64_t h2p_with_lhist_percep = 0;
    uint64_t h2p_with_ghist_percep = 0;
    
    uint64_t lhist_percep_evictions = 0;
    uint64_t ghist_percep_evictions = 0;
    uint64_t lhist_percep_stale_evictions = 0;
    uint64_t ghist_percep_stale_evictions = 0;

    // Number of H2P branches that have been inserted
    uint64_t h2p_insert_cnt = 0;

    SampleCondPredictor () {};

    void setup() {
        tage_sc_l.setup();
    }

    void terminate() {
        // === Output Predictor Memory Usage ===
        printf("======== Predictor Memory ========\n");
        uint64_t tage_bits = tage_sc_l.predictorsize();

        printf("TAGE-SC-L (bits) = %ld\n", tage_bits);
        printf("TAGE-SC-L (KBytes) = %lf\n", tage_bits / 8192.0);

        printf("H2P_ID_MEM_BITS = %d\n", H2P_ID_MEM_BITS);
        printf("H2P_ID_MEM (KBytes) = %lf\n", H2P_ID_MEM_BITS / 8192.0);

        printf("L_PERCEP_MEM_BITS = %d\n", L_PERCEP_MEM_BITS);
        printf("L_PERCEP_MEM (KBytes) = %lf\n", L_PERCEP_MEM_BITS / 8192.0);

        printf("G_PERCEP_MEM_BITS = %d\n", G_PERCEP_MEM_BITS);
        printf("G_PERCEP_MEM (KBytes) = %lf\n", G_PERCEP_MEM_BITS / 8192.0);

        uint64_t total_bits = H2P_ID_MEM_BITS + L_PERCEP_MEM_BITS + G_PERCEP_MEM_BITS + tage_bits;
        printf("Total Memory (bits) = %ld\n", total_bits);
        printf("Total Memory (KBytes) = %lf\n", total_bits / 8192.0);

        // === Print Runtime Statistics ===
        printf("======== Runtime Statistics ========\n");
        printf("COL h2p_insert_cnt = %ld\n", h2p_insert_cnt);
        printf("COL h2p_with_tage = %ld\n", h2p_with_tage);
        printf("COL h2p_with_lhist_percep = %ld\n", h2p_with_lhist_percep);
        printf("COL h2p_with_ghist_percep = %ld\n", h2p_with_ghist_percep);
        printf("COL filtered_updates = %ld\n", filtered_updates);
        printf("COL lhist_percep_evictions = %ld\n", lhist_percep_evictions);
        printf("COL ghist_percep_evictions = %ld\n", ghist_percep_evictions);
        printf("COL lhist_percep_stale_evictions = %ld\n", lhist_percep_stale_evictions);
        printf("COL ghist_percep_stale_evictions = %ld\n", ghist_percep_stale_evictions);
        printf("======== End of Statistics ========\n");

        tage_sc_l.terminate();
    }

    bool predict (uint64_t seq_no, uint8_t piece, uint64_t PC) {
        // Compute all applicable predictions
        active_hist.tage_pred = tage_sc_l.predict(seq_no, piece, PC);

        if (lhist_perceptron.contains(PC)) {
            active_hist.lhist_percep_pred = lhist_perceptron.predict(PC);
        }

        if (ghist_perceptron.contains(PC)) {
            active_hist.ghist_percep_pred = ghist_perceptron.predict(PC);
        }

        // --- Choose predictor based on Confidence ---
        bool sc_confident = tage_sc_l.is_SC_confident();

        if (lhist_perceptron.contains(PC) && (active_hist.lhist_percep_pred.high_confidence || lhist_perceptron.is_superior(PC))) {
            active_hist.final_pred = (active_hist.lhist_percep_pred.pred >= 0);
            h2p_with_lhist_percep += 1;

        } else if (ghist_perceptron.contains(PC) && (active_hist.ghist_percep_pred.high_confidence || ghist_perceptron.is_superior(PC))) {
            active_hist.final_pred = (active_hist.ghist_percep_pred.pred >= 0);
            h2p_with_ghist_percep += 1;

        } else if (tage_sc_l.HighConf || sc_confident) {//(tage_sc_l.HighConf && (LSUM >= 0) == active_hist.tage_pred) {
            active_hist.final_pred = active_hist.tage_pred;
            h2p_with_tage += 1;

        } else if (lhist_perceptron.contains(PC) && active_hist.lhist_percep_pred.med_confidence) {
            active_hist.final_pred = (active_hist.lhist_percep_pred.pred >= 0);
            h2p_with_lhist_percep += 1;

        } else if (ghist_perceptron.contains(PC) && active_hist.ghist_percep_pred.med_confidence) {
            active_hist.final_pred = (active_hist.ghist_percep_pred.pred >= 0);
            h2p_with_ghist_percep += 1;

        } else if (lhist_perceptron.contains(PC) || ghist_perceptron.contains(PC)) {
            active_hist.final_pred = active_hist.tage_pred;
            h2p_with_tage += 1;

        } else {
            active_hist.final_pred = active_hist.tage_pred;
        }

        return active_hist.final_pred;
    }

    // Update internal state after a conditional branch prediction
    void history_update(uint64_t seq_no, uint8_t piece, uint64_t PC, int brtype, bool pred_dir, bool resolve_dir, uint64_t nextPC) {
        pred_time_histories.emplace(get_unique_inst_id(seq_no, piece), active_hist);
        
        lhist_perceptron.history_update(PC, get_unique_inst_id(seq_no, piece), active_hist.final_pred);
        ghist_perceptron.history_update(PC, get_unique_inst_id(seq_no, piece), active_hist.final_pred);
        
        tage_sc_l.history_update(seq_no, piece, PC, brtype, pred_dir, resolve_dir, nextPC);
    }

    // Update internal state after a non-conditional branch prediction
    void TrackOtherInst(uint64_t PC, int brtype, bool pred_dir, bool resolve_dir, uint64_t nextPC) {
        tage_sc_l.TrackOtherInst(PC, brtype, pred_dir, resolve_dir, nextPC);
    }

    // Called when a load is resolved
    void update_load(uint64_t loadAddr, uint8_t loadSize, uint64_t loadData) {}

    // Called when a conditional branch is resolved
    void update(uint64_t seq_no, uint8_t piece, uint64_t PC, bool resolveDir, bool predDir, uint64_t nextPC) {
        const auto pred_id = get_unique_inst_id(seq_no, piece);
        const auto& pred_time_history = pred_time_histories.at(pred_id);

        // TODO: compute best competitor properly

        if (lhist_perceptron.contains(PC)) {
            lhist_perceptron.update(PC, pred_id, resolveDir, predDir, pred_time_history.lhist_percep_pred.pred, pred_time_history.tage_pred);
        }

        if (ghist_perceptron.contains(PC)) {
            ghist_perceptron.update(PC, pred_id, resolveDir, predDir, pred_time_history.ghist_percep_pred.pred, pred_time_history.tage_pred);
        } else {
            ghist_perceptron.refine_ghist(resolveDir, predDir);
        }

        // Check for poor performance evictions
        bool evicted_L = lhist_perceptron.check_eviction(PC);
        bool evicted_G = ghist_perceptron.check_eviction(PC);
        if(evicted_L) {
            h2p_id_table.evict_h2p(PC);
            lhist_percep_evictions += 1;
        }
        if(evicted_G) {
            h2p_id_table.evict_h2p(PC);
            ghist_percep_evictions += 1;
        }

        // Check for stale data evictions
        bool evicted_stale_L = lhist_perceptron.check_stale_eviction();
        bool evicted_stale_G = ghist_perceptron.check_stale_eviction();
        if(evicted_stale_L) {
            h2p_id_table.evict_h2p(PC);
            lhist_percep_stale_evictions += 1;
        }
        if(evicted_stale_G) {
            h2p_id_table.evict_h2p(PC);
            ghist_percep_stale_evictions += 1;
        }
        
        // Check for new H2P branches
        if (!lhist_perceptron.contains_or_queued(PC) && !ghist_perceptron.contains_or_queued(PC)) {
            bool is_h2p = h2p_id_table.update(PC, predDir == resolveDir);

            if (is_h2p) {
                h2p_insert_cnt += 1;
                lhist_perceptron.insert(PC);
                ghist_perceptron.insert(PC);
            }
        }

        // Filter updates from tage-sc-l when H2P branch is best predicted by dedicated H2P predictor
        bool filter_tage_update = lhist_perceptron.contains(PC) && lhist_perceptron.is_superior(PC);
        filter_tage_update |= ghist_perceptron.contains(PC) && ghist_perceptron.is_superior(PC);

        if (filter_tage_update) filtered_updates += 1;

        tage_sc_l.update(seq_no, piece, PC, resolveDir, nextPC, filter_tage_update);

        pred_time_histories.erase(pred_id);
    }

};


#endif // _BULLSEYE_CORE_H_

