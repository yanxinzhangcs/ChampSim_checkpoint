#include "mockingjay.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>

#include "cache.h"
#include "champsim.h"

mockingjay::mockingjay(CACHE* cache)
    : replacement(cache), NUM_SET(cache->NUM_SET), NUM_WAY(cache->NUM_WAY), LOG2_LLC_SET(static_cast<int>(champsim::lg2(NUM_SET))),
      LOG2_LLC_SIZE(LOG2_LLC_SET + static_cast<int>(champsim::lg2(NUM_WAY)) + LOG2_BLOCK_SIZE), LOG2_SAMPLED_SETS(std::max(0, LOG2_LLC_SIZE - 16)),
      SAMPLED_CACHE_TAG_BITS(std::max(1, 31 - LOG2_LLC_SIZE)), PC_SIGNATURE_BITS(std::max(1, LOG2_LLC_SIZE - 10)),
      INF_RD(static_cast<int>(NUM_WAY * HISTORY - 1)), INF_ETR(static_cast<int>((NUM_WAY * HISTORY) / GRANULARITY) - 1), MAX_RD(INF_RD - 22),
      TEMP_DIFFERENCE(1.0 / 16.0), FLEXMIN_PENALTY(2.0 - std::log2(static_cast<double>(NUM_CPUS)) / 4.0),
      etr(static_cast<std::size_t>(NUM_SET * NUM_WAY), 0), etr_clock(static_cast<std::size_t>(NUM_SET), GRANULARITY),
      current_timestamp(static_cast<std::size_t>(NUM_SET), 0)
{
}

void mockingjay::initialize_replacement()
{
  std::fill(std::begin(etr), std::end(etr), 0);
  std::fill(std::begin(etr_clock), std::end(etr_clock), GRANULARITY);
  std::fill(std::begin(current_timestamp), std::end(current_timestamp), 0);
  rdp.clear();
  sampled_cache.clear();

  const uint32_t modifier = LOG2_LLC_SET > 0 ? static_cast<uint32_t>(1u << LOG2_LLC_SET) : 0;
  const uint32_t limit = LOG2_SAMPLED_SETS > 0 ? static_cast<uint32_t>(1u << LOG2_SAMPLED_SETS) : 1u;

  for (uint32_t set = 0; set < static_cast<uint32_t>(NUM_SET); ++set) {
    if (!is_sampled_set(set))
      continue;

    for (uint32_t i = 0; i < limit; ++i) {
      uint32_t idx = set + modifier * i;
      sampled_cache[idx] = std::vector<SampledCacheLine>(SAMPLED_CACHE_WAYS);
    }
  }
}

bool mockingjay::is_sampled_set(uint32_t set) const
{
  if (LOG2_SAMPLED_SETS <= 0 || LOG2_LLC_SET <= LOG2_SAMPLED_SETS)
    return false;

  int mask_length = LOG2_LLC_SET - LOG2_SAMPLED_SETS;
  uint32_t mask = (1u << mask_length) - 1u;
  return (set & mask) == ((set >> (LOG2_LLC_SET - mask_length)) & mask);
}

uint64_t mockingjay::crc_hash(uint64_t block_address) const
{
  static constexpr uint64_t crcPolynomial = 3988292384ULL;
  uint64_t value = block_address;
  for (int i = 0; i < 3; i++) {
    value = ((value & 1u) == 1u) ? ((value >> 1) ^ crcPolynomial) : (value >> 1);
  }
  return value;
}

uint64_t mockingjay::get_pc_signature(uint64_t pc, bool hit, bool prefetch, uint32_t core) const
{
  if (NUM_CPUS == 1) {
    pc = (pc << 1) | (hit ? 1ull : 0ull);
    pc = (pc << 1) | (prefetch ? 1ull : 0ull);
    pc = crc_hash(pc);
    pc = (pc << (64 - PC_SIGNATURE_BITS)) >> (64 - PC_SIGNATURE_BITS);
  } else {
    pc = (pc << 1) | (prefetch ? 1ull : 0ull);
    pc = (pc << 2) | (core & 0x3u);
    pc = crc_hash(pc);
    pc = (pc << (64 - PC_SIGNATURE_BITS)) >> (64 - PC_SIGNATURE_BITS);
  }
  return pc;
}

uint32_t mockingjay::get_sampled_cache_index(uint64_t full_addr) const
{
  full_addr >>= LOG2_BLOCK_SIZE;
  const int bits = LOG2_SAMPLED_CACHE_SETS + LOG2_LLC_SET;
  if (bits >= 64)
    return static_cast<uint32_t>(full_addr);

  full_addr = (full_addr << (64 - bits)) >> (64 - bits);
  return static_cast<uint32_t>(full_addr);
}

uint64_t mockingjay::get_sampled_cache_tag(uint64_t full_addr) const
{
  full_addr >>= (LOG2_LLC_SET + LOG2_BLOCK_SIZE + LOG2_SAMPLED_CACHE_SETS);
  full_addr = (full_addr << (64 - SAMPLED_CACHE_TAG_BITS)) >> (64 - SAMPLED_CACHE_TAG_BITS);
  return full_addr;
}

int mockingjay::search_sampled_cache(uint64_t block_address, uint32_t set) const
{
  auto it = sampled_cache.find(set);
  if (it == sampled_cache.end())
    return -1;

  const auto& sampled_set = it->second;
  for (int way = 0; way < SAMPLED_CACHE_WAYS; way++) {
    if (sampled_set[way].valid && sampled_set[way].tag == block_address)
      return way;
  }
  return -1;
}

void mockingjay::detrain(uint32_t set, int way)
{
  auto it = sampled_cache.find(set);
  if (it == sampled_cache.end() || way < 0 || way >= SAMPLED_CACHE_WAYS)
    return;

  auto& sampled_set = it->second;
  SampledCacheLine temp = sampled_set[way];
  if (!temp.valid)
    return;

  auto sig = static_cast<uint32_t>(temp.signature);
  auto rdp_it = rdp.find(sig);
  if (rdp_it != rdp.end()) {
    rdp_it->second = std::min(rdp_it->second + 1, INF_RD);
  } else {
    rdp[sig] = INF_RD;
  }
  sampled_set[way].valid = false;
}

int mockingjay::temporal_difference(int init, int sample) const
{
  if (sample > init) {
    int diff = sample - init;
    diff = static_cast<int>(diff * TEMP_DIFFERENCE);
    diff = std::min(1, diff);
    return std::min(init + diff, INF_RD);
  }
  if (sample < init) {
    int diff = init - sample;
    diff = static_cast<int>(diff * TEMP_DIFFERENCE);
    diff = std::min(1, diff);
    return std::max(init - diff, 0);
  }
  return init;
}

int mockingjay::increment_timestamp(int input) const
{
  input++;
  input = input % (1 << TIMESTAMP_BITS);
  return input;
}

int mockingjay::time_elapsed(int global, int local) const
{
  if (global >= local) {
    return global - local;
  }
  global = global + (1 << TIMESTAMP_BITS);
  return global - local;
}

int& mockingjay::etr_at(long set, long way) { return etr.at(static_cast<std::size_t>(set * NUM_WAY + way)); }

const int& mockingjay::etr_at(long set, long way) const { return etr.at(static_cast<std::size_t>(set * NUM_WAY + way)); }

long mockingjay::find_victim(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
                             champsim::address full_addr, access_type type)
{
  for (long way = 0; way < NUM_WAY; way++) {
    if (!current_set[way].valid) {
      return way;
    }
  }

  int max_etr = 0;
  long victim_way = 0;
  for (long way = 0; way < NUM_WAY; way++) {
    int val = std::abs(etr_at(set, way));
    if (val > max_etr || (val == max_etr && etr_at(set, way) < 0)) {
      max_etr = val;
      victim_way = way;
    }
  }

  auto pc_signature = get_pc_signature(ip.to<uint64_t>(), false, type == access_type::PREFETCH, triggering_cpu);
  if (type != access_type::WRITE) {
    auto it = rdp.find(static_cast<uint32_t>(pc_signature));
    if (it != rdp.end()) {
      if (it->second > MAX_RD || (it->second / GRANULARITY) > max_etr) {
        // Original code attempted to bypass; we conservatively fall back to chosen victim.
      }
    }
  }

  return victim_way;
}

void mockingjay::update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                                          champsim::address victim_addr, access_type type, bool hit)
{
  (void)victim_addr;

  const uint64_t full_addr_val = full_addr.to<uint64_t>();
  const uint64_t ip_val = ip.to<uint64_t>();

  if (type == access_type::WRITE) {
    if (!hit) {
      etr_at(set, way) = -INF_ETR;
    }
    return;
  }

  auto pc_sig = static_cast<uint32_t>(get_pc_signature(ip_val, hit, type == access_type::PREFETCH, triggering_cpu));

  if (is_sampled_set(static_cast<uint32_t>(set))) {
    uint32_t sampled_cache_index = get_sampled_cache_index(full_addr_val);
    uint64_t sampled_cache_tag = get_sampled_cache_tag(full_addr_val);
    int sampled_cache_way = search_sampled_cache(sampled_cache_tag, sampled_cache_index);

    if (sampled_cache_way > -1) {
      auto it = sampled_cache.find(sampled_cache_index);
      if (it != sampled_cache.end()) {
        uint64_t last_signature = it->second.at(sampled_cache_way).signature;
        int last_timestamp = it->second.at(sampled_cache_way).timestamp;
        int sample = time_elapsed(current_timestamp.at(static_cast<std::size_t>(set)), last_timestamp);

        if (sample <= INF_RD) {
          if (type == access_type::PREFETCH) {
            sample = static_cast<int>(sample * FLEXMIN_PENALTY);
          }
          auto rdp_it = rdp.find(static_cast<uint32_t>(last_signature));
          if (rdp_it != rdp.end()) {
            int init = rdp_it->second;
            rdp_it->second = temporal_difference(init, sample);
          } else {
            rdp[static_cast<uint32_t>(last_signature)] = sample;
          }

          it->second.at(sampled_cache_way).valid = false;
        }
      }
    }

    int lru_way = -1;
    int lru_rd = -1;
    auto sampled_it = sampled_cache.find(sampled_cache_index);
    if (sampled_it != sampled_cache.end()) {
      auto& sampled_set = sampled_it->second;
      for (int w = 0; w < SAMPLED_CACHE_WAYS; w++) {
        if (sampled_set[w].valid == false) {
          lru_way = w;
          lru_rd = INF_RD + 1;
          continue;
        }

        int sample = time_elapsed(current_timestamp.at(static_cast<std::size_t>(set)), sampled_set[w].timestamp);
        if (sample > INF_RD) {
          lru_way = w;
          lru_rd = INF_RD + 1;
          detrain(sampled_cache_index, w);
        } else if (sample > lru_rd) {
          lru_way = w;
          lru_rd = sample;
        }
      }

      if (lru_way >= 0) {
        detrain(sampled_cache_index, lru_way);
      }

      for (int w = 0; w < SAMPLED_CACHE_WAYS; w++) {
        if (sampled_set[w].valid == false) {
          sampled_set[w].valid = true;
          sampled_set[w].signature = pc_sig;
          sampled_set[w].tag = sampled_cache_tag;
          sampled_set[w].timestamp = current_timestamp.at(static_cast<std::size_t>(set));
          break;
        }
      }
    }

    current_timestamp.at(static_cast<std::size_t>(set)) = increment_timestamp(current_timestamp.at(static_cast<std::size_t>(set)));
  }

  if (etr_clock.at(static_cast<std::size_t>(set)) == GRANULARITY) {
    for (long w = 0; w < NUM_WAY; w++) {
      if (w != way && std::abs(etr_at(set, w)) < INF_ETR) {
        etr_at(set, w)--;
      }
    }
    etr_clock.at(static_cast<std::size_t>(set)) = 0;
  }
  etr_clock.at(static_cast<std::size_t>(set))++;

  if (way < NUM_WAY) {
    auto it = rdp.find(pc_sig);
    if (it == rdp.end()) {
      etr_at(set, way) = (NUM_CPUS == 1) ? 0 : INF_ETR;
    } else {
      if (it->second > MAX_RD) {
        etr_at(set, way) = INF_ETR;
      } else {
        etr_at(set, way) = it->second / GRANULARITY;
      }
    }
  }
}

void mockingjay::replacement_final_stats() {}
