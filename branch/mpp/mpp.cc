
#include "mpp.h"

void mpp::initialize_branch_predictor() {
    cbp2016_tage_sc_l.setup();
    predictor.setup();
}

bool mpp::predict_branch(uint64_t ip)
{
    // conditional branch discrimination
    const bool tage_sc_l_pred = cbp2016_tage_sc_l.predict(ip, 0, ip);
    // there is no sequence number or piece number from champsim so we're using ip and 0.
    return predictor.predict(ip, 0, ip, tage_sc_l_pred);
}

void mpp::last_branch_result(uint64_t ip,
                        uint64_t branch_target,
                        uint8_t taken,
                        uint8_t branch_type)
{
    // there is no sequence number or piece number from champsim so we're using ip and 0
    // there is not predicted_direction so we have put 000 for now.
    cbp2016_tage_sc_l.update(ip, 0, ip, taken, 000, branch_target);
    predictor.update(ip, 0, ip, taken, 000, branch_target);
}

