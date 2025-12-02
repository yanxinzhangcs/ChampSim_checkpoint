#ifndef MOCKINGJAY_H
#define MOCKINGJAY_H

#include <unordered_map>
#include <vector>

#include "address.h"
#include "champsim.h"
#include "modules.h"

class CACHE;

struct mockingjay : public champsim::modules::replacement {
  using champsim::modules::replacement::replacement;

  mockingjay(CACHE* cache);

  void initialize_replacement();
  long find_victim(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
                   champsim::address full_addr, access_type type);
  void update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                                champsim::address victim_addr, access_type type, bool hit);
  void replacement_final_stats();

private:
  static constexpr int HISTORY = 8;
  static constexpr int GRANULARITY = 8;
  static constexpr int SAMPLED_CACHE_WAYS = 5;
  static constexpr int LOG2_SAMPLED_CACHE_SETS = 4;
  static constexpr int TIMESTAMP_BITS = 8;

  long NUM_SET;
  long NUM_WAY;
  int LOG2_LLC_SET;
  int LOG2_LLC_SIZE;
  int LOG2_SAMPLED_SETS;
  int SAMPLED_CACHE_TAG_BITS;
  int PC_SIGNATURE_BITS;
  int INF_RD;
  int INF_ETR;
  int MAX_RD;
  double TEMP_DIFFERENCE;
  double FLEXMIN_PENALTY;

  std::vector<int> etr;
  std::vector<int> etr_clock;
  std::vector<int> current_timestamp;
  std::unordered_map<uint32_t, int> rdp;

  struct SampledCacheLine {
    bool valid = false;
    uint64_t tag = 0;
    uint64_t signature = 0;
    int timestamp = 0;
  };

  std::unordered_map<uint32_t, std::vector<SampledCacheLine>> sampled_cache;

  [[nodiscard]] bool is_sampled_set(uint32_t set) const;
  [[nodiscard]] uint64_t crc_hash(uint64_t block_address) const;
  [[nodiscard]] uint64_t get_pc_signature(uint64_t pc, bool hit, bool prefetch, uint32_t core) const;
  [[nodiscard]] uint32_t get_sampled_cache_index(uint64_t full_addr) const;
  [[nodiscard]] uint64_t get_sampled_cache_tag(uint64_t full_addr) const;
  [[nodiscard]] int search_sampled_cache(uint64_t block_address, uint32_t set) const;
  void detrain(uint32_t set, int way);
  [[nodiscard]] int temporal_difference(int init, int sample) const;
  [[nodiscard]] int increment_timestamp(int input) const;
  [[nodiscard]] int time_elapsed(int global, int local) const;
  [[nodiscard]] int& etr_at(long set, long way);
  [[nodiscard]] const int& etr_at(long set, long way) const;
};

#endif
