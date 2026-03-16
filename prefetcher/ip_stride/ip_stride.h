#ifndef IP_STRIDE_H
#define IP_STRIDE_H

#include <cstdint>
#include <optional>

#include "address.h"
#include "champsim.h"
#include "modules.h"
#include "msl/lru_table.h"

struct ip_stride : public champsim::modules::prefetcher {
  constexpr static std::size_t TRACKER_SETS = 256;
  constexpr static std::size_t TRACKER_WAYS = 4;
  constexpr static champsim::data::bits TRACKER_INDEX_BITS{champsim::lg2(TRACKER_SETS)};

  struct tracker_entry {
    champsim::address ip{};                                // the IP we're tracking
    champsim::block_number last_cl_addr{};                 // the last address accessed by this IP
    champsim::block_number::difference_type last_stride{}; // the stride between the last two addresses accessed by this IP

    auto index() const
    {
      return ip.slice_lower(TRACKER_INDEX_BITS);
    }
    auto tag() const
    {
      return ip.slice_upper(TRACKER_INDEX_BITS);
    }
  };

  struct lookahead_entry {
    champsim::address address{};
    champsim::address::difference_type stride{};
    int degree = 0; // degree remaining
  };

  constexpr static int PREFETCH_DEGREE = 3;

  std::optional<lookahead_entry> active_lookahead;
  std::optional<champsim::address> branch_context_ip;

  champsim::msl::lru_table<tracker_entry> table{TRACKER_SETS, TRACKER_WAYS};

public:
  using champsim::modules::prefetcher::prefetcher;

  uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool useful_prefetch, access_type type,
                                    uint32_t metadata_in);
  uint32_t prefetcher_cache_fill(champsim::address addr, long set, long way, uint8_t prefetch, champsim::address evicted_addr, uint32_t metadata_in);
  void prefetcher_branch_operate(champsim::address ip, uint8_t branch_type, champsim::address branch_target);
  void prefetcher_cycle_operate();
};

#endif
