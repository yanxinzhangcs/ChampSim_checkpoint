
#include "bullseye.h"
#include "bullseye_core.h"

void bullseye::initialize_branch_predictor()  {
    core_.setup();  // core setup
}

bool bullseye::predict_branch(uint64_t ip) 
{
    // conditional branch discrimination
    // no sequence number or piece number from champsim so use ip and 0
    return core_.predict(ip, 0, ip);
}

void bullseye::last_branch_result(uint64_t ip,
                        uint64_t branch_target,
                        uint8_t taken,
                        uint8_t branch_type) 
{
    // no sequence number or piece number from champsim so use ip and 0
    // predicted branch direction not given so use 000
    core_.update(ip, 0, ip, taken, 000, branch_target);
}

