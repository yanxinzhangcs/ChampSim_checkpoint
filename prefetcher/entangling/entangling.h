#ifndef ENTANGLING_H
#define ENTANGLING_H

#include <cstdint>
#include <optional>

#include "address.h"
#include "champsim.h"
#include "modules.h"
#include "msl/lru_table.h"
#include "cache.h"

class entangling : public champsim::modules::prefetcher
{
	CACHE* parent_cache = nullptr;
public:

	using champsim::modules::prefetcher::prefetcher;

	void bind(CACHE* cache) { parent_cache = cache; }

	uint32_t prefetcher_cache_operate(uint64_t addr, uint64_t ip, uint64_t instr_id, 
			bool cache_hit, bool useful_prefetch, uint8_t type, 
			uint32_t metadata_in);
	uint32_t prefetcher_cache_fill(uint64_t addr, uint32_t set, uint32_t way, 
			  uint8_t prefetch, uint64_t evicted_addr, uint32_t metadata_in);
	void prefetcher_branch_operate(uint64_t ip, uint8_t branch_type, uint64_t branch_target);
  	void prefetcher_cycle_operate();
	void prefetcher_initialize();
	void prefetcher_final_stats();
};


#endif
