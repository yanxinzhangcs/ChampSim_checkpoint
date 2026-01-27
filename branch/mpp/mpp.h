#ifndef BRANCH_MPP_H
#define BRANCH_MPP_H

#include "modules.h"
#include "mpp_dir/mpp_core.h"
#include "cbp2016_tage_sc_l.h"

struct mpp : public champsim::modules::branch_predictor
{
    using branch_predictor::branch_predictor;

    mppspace::SampleCondPredictor predictor;
    CBP2016_TAGE_SC_L cbp2016_tage_sc_l;
    // copy cbp2016_tage_sc_l.h into directory if we add the prediction to this one.

    void initialize_branch_predictor();

    bool predict_branch(uint64_t ip);

    void last_branch_result(uint64_t ip,
                            uint64_t branch_target,
                            uint8_t taken,
                            uint8_t branch_type);
};

#endif // BRANCH_MPP_H
