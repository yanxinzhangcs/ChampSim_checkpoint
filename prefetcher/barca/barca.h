#ifndef BARCA_H
#define BARCA_H

#include "address.h"
#include "champsim.h"
#include "modules.h"

struct barca : public champsim::modules::prefetcher {
  using champsim::modules::prefetcher::prefetcher;

  void prefetcher_initialize();
  uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool useful_prefetch, access_type type,
                                    uint32_t metadata_in);
  uint32_t prefetcher_cache_fill(champsim::address addr, long set, long way, bool prefetch, champsim::address evicted_addr, uint32_t metadata_in);
  void prefetcher_cycle_operate();
  void prefetcher_final_stats();
  void prefetcher_branch_operate(champsim::address ip, uint8_t branch_type, champsim::address branch_target);
};

#endif
