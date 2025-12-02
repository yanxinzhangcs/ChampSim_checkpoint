#ifndef PACIPV_H
#define PACIPV_H

#include <cstdint>
#include <optional>
#include <vector>
#include <string>

#include "address.h"
#include "champsim.h"
#include "modules.h"
#include "msl/lru_table.h"
#include "cache.h"



class PACIPV_Entry {
	private:
		long                        num_ways;        // Number of ways in this set
		const std::vector<uint32_t> demand_vector;   // Demand IPV
		const std::vector<uint32_t> prefetch_vector; // Prefetch IPV
		std::vector<uint32_t>       rrpvs;           // Current RRPV of all the ways

	public:
		PACIPV_Entry(long ways, decltype(demand_vector)& dv, decltype(prefetch_vector)& pv); 

		void demand_insert(long way);
		void demand_promote(long way);
		void prefetch_insert(long way);
		void prefetch_promote(long way);
		long find_victim();
		friend class PACIPV;
};

class PACIPV : public champsim::modules::replacement
{
	long                   		num_ways;  	 // Number of ways in this set
	long 				   		num_sets;
	std::string			 		cache_name;
	//const std::vector<uint32_t> demand_vector; // Demand IPV
	//const std::vector<uint32_t> prefetch_vector; // Prefetch IPV
	//std::vector<uint32_t>       rrpvs; // Current RRPV of all the ways
	std::map<PACIPV*, std::vector<PACIPV_Entry>> policies;

	enum class cache_type
	{
		UNDEFINED,
		L1I,
		L1D,
		L2C,
		LLC
	};
  
  public:
	explicit PACIPV(CACHE* cache);
  	PACIPV(CACHE* cache, std::string name, long sets, long ways); //: num_ways(ways), demand_vector(dv), prefetch_vector(pv);
  
	// void initialize_replacement();
	//void demand_insert(long way);
	//void demand_promote(long way);
	//void prefetch_insert(long way);
	//void prefetch_promote(long way);
	void initialize_replacement();
	long find_victim(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
					 champsim::address full_addr, access_type type);
	//void replacement_cache_fill(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, champsim::address victim_addr,
	//							access_type type);
	void update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, champsim::address victim_addr,
								  access_type type, uint8_t hit);
	void replacement_final_stats();
  };

  //std::map<CACHE*, std::vector<PACIPV>> policies;

#endif
