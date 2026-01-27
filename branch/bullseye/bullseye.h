#ifndef BRANCH_BULLSEYE_H
#define BRANCH_BULLSEYE_H

#include "modules.h"
#include "bullseye_core.h"

struct bullseye : public champsim::modules::branch_predictor
{
    using branch_predictor::branch_predictor;

    SampleCondPredictor core_;

    void initialize_branch_predictor();

    bool predict_branch(uint64_t ip);

    void last_branch_result(uint64_t ip,
                            uint64_t branch_target,
                            uint8_t taken,
                            uint8_t branch_type);
};

#endif // BRANCH_BULLSEYE_H
