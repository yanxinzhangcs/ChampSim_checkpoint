#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <map>
#include <sstream>
#include <unordered_set>
#include <vector>

#include "cache.h"
#include "PACIPV.h"

/** 
namespace PACIPV_Policy
{
        enum class cache_type
        {
                UNDEFINED,
                L1I,
                L1D,
                L2C,
                LLC
        };

        class PACIPV_Helper
        {
                //private:
                        //uint32_t                    num_ways;        // Number of ways in this set
                        //const std::vector<uint32_t> demand_vector;   // Demand IPV
                        //const std::vector<uint32_t> prefetch_vector; // Prefetch IPV
                        //std::vector<uint32_t>       rrpvs;           // Current RRPV of all the ways

                public:
                        PACIPV(uint32_t ways, decltype(demand_vector)& dv, decltype(prefetch_vector)& pv): num_ways(ways), demand_vector(dv), prefetch_vector(pv)
                        {
                                // Initialize the RRPVs of all the ways
                                uint32_t max_valid_rrpv = demand_vector.size() - 1;
                                rrpvs.resize(num_ways, max_valid_rrpv);
                        }

                        void demand_insert(uint32_t way)
                        {
                                // Sanity check
                                assert(way < num_ways);

                                // Update the RRPV to the insertion RRPV
                                rrpvs.at(way) = demand_vector.at(demand_vector.size() - 1);
                        }

                        void demand_promote(uint32_t way)
                        {
                                // Sanity check
                                assert(way < num_ways);

                                // Update RRPV
                                uint32_t old_rrpv = rrpvs.at(way);
                                uint32_t new_rrpv = demand_vector.at(old_rrpv - 1);
                                rrpvs.at(way)     = new_rrpv;
                        }

                        void prefetch_insert(uint32_t way)
                        {
                                // Sanity check
                                assert(way < num_ways);

                                // Update the RRPV to the insertion RRPV
                                rrpvs.at(way) = prefetch_vector.at(prefetch_vector.size() - 1);
                        }

                        void prefetch_promote(uint32_t way)
                        {
                                // Sanity check
                                assert(way < num_ways);

                                // Update RRPV
                                uint32_t old_rrpv = rrpvs.at(way);
                                uint32_t new_rrpv = prefetch_vector.at(old_rrpv - 1);
                                rrpvs.at(way)     = new_rrpv;
                        }

                        uint32_t find_victim()
                        {
                                // Find the maximum valid RRPV
                                uint32_t max_valid_rrpv = demand_vector.size() - 1;

                                // Increment all RRPVs for all ways until at least one way is assigned the maximum valid RRPV
                                uint32_t max_rrpv = *std::max_element(rrpvs.cbegin(), rrpvs.cend());
                                while(max_valid_rrpv != max_rrpv)
                                {
                                        std::transform(rrpvs.cbegin(),
                                                       rrpvs.cend(),
                                                       rrpvs.begin(),
                                                       [](uint32_t rrpv)
                                                       {
                                                               return rrpv + 1;
                                                       });
                                        max_rrpv = *std::max_element(rrpvs.cbegin(), rrpvs.cend());
                                }

                                // Create a set of all the ways which have the maximum RRPV
                                std::unordered_set<std::size_t> victims;
                                for(decltype(rrpvs)::const_iterator it = rrpvs.cbegin(); it != rrpvs.cend(); it++)
                                {
                                        if(*it == max_rrpv)
                                                victims.insert(std::distance(rrpvs.cbegin(), it));
                                }

                                // Run sanity check
                                assert(victims.size() > 0 && victims.size() <= num_ways);

                                // Randomly pick one of the ways in the victims set
                                std::size_t                       idx = rand() % victims.size();
                                decltype(victims)::const_iterator it  = victims.cbegin();
                                std::advance(it, idx);
                                return static_cast<uint32_t>(*it);
                        }
        };

        std::map<CACHE*, std::vector<PACIPV>> policies;
} // namespace PACIPV_Policy
**/

PACIPV::PACIPV(CACHE* cache) : PACIPV(cache, cache->NAME, cache->NUM_SET, cache->NUM_WAY) {}

//PACIPV(CACHE* cache, uint32_t ways, decltype(demand_vector)& dv, decltype(prefetch_vector)& pv): num_ways(ways), demand_vector(dv), prefetch_vector(pv)
PACIPV::PACIPV(CACHE* cache, std::string name, long sets, long ways)
    : replacement(cache), cache_name(name), num_sets(sets), num_ways(ways) {}



PACIPV_Entry::PACIPV_Entry(long ways, decltype(demand_vector)& dv, decltype(prefetch_vector)& pv): num_ways(ways), demand_vector(dv), prefetch_vector(pv)
{
        // Initialize the RRPVs of all the ways
        uint32_t max_valid_rrpv = demand_vector.size() - 1;
        rrpvs.resize(num_ways, max_valid_rrpv);
}

void PACIPV_Entry::demand_insert(long way)
{
        // Sanity check
        assert(way < num_ways);

        // Update the RRPV to the insertion RRPV
        rrpvs.at(way) = demand_vector.at(demand_vector.size() - 1);
}

void PACIPV_Entry::demand_promote(long way)
{
        // Sanity check
        assert(way < num_ways);

        // Update RRPV
        uint32_t old_rrpv = rrpvs.at(way);
        uint32_t new_rrpv = demand_vector.at(old_rrpv);
        rrpvs.at(way)     = new_rrpv;
}

void PACIPV_Entry::prefetch_insert(long way)
{
        // Sanity check
        assert(way < num_ways);

        // Update the RRPV to the insertion RRPV
        rrpvs.at(way) = prefetch_vector.at(prefetch_vector.size() - 1);
}

void PACIPV_Entry::prefetch_promote(long way)
{
        // Sanity check
        assert(way < num_ways);

        // Update RRPV
        uint32_t old_rrpv = rrpvs.at(way);
        uint32_t new_rrpv = prefetch_vector.at(old_rrpv);
        rrpvs.at(way)     = new_rrpv;
}

long PACIPV_Entry::find_victim() {

        // Find the maximum valid RRPV
        uint32_t max_valid_rrpv = demand_vector.size() - 1;

        // Increment all RRPVs for all ways until at least one way is assigned the maximum valid RRPV
        uint32_t max_rrpv = *std::max_element(rrpvs.cbegin(), rrpvs.cend());
        while(max_valid_rrpv != max_rrpv)
        {
                std::transform(rrpvs.cbegin(),
                        rrpvs.cend(),
                        rrpvs.begin(),
                        [](uint32_t rrpv)
                        {
                                return rrpv + 1;
                });
                max_rrpv = *std::max_element(rrpvs.cbegin(), rrpvs.cend());
        }

        // Create a set of all the ways which have the maximum RRPV
        std::unordered_set<std::size_t> victims;
        for(decltype(rrpvs)::const_iterator it = rrpvs.cbegin(); it != rrpvs.cend(); it++)
        {
                if(*it == max_rrpv)
                        victims.insert(std::distance(rrpvs.cbegin(), it));
        }

        // Run sanity check
        assert(victims.size() > 0 && victims.size() <= num_ways);

        // Randomly pick one of the ways in the victims set
        std::size_t                       idx = rand() % victims.size();
        decltype(victims)::const_iterator it  = victims.cbegin();
        std::advance(it, idx);
        return static_cast<long>(*it);
}

void PACIPV::initialize_replacement()
{
        policies[this] = std::vector<PACIPV_Entry>();

        // Get the cache type
        PACIPV::cache_type type_name;
        if(cache_name.find("L1I") != std::string::npos)
                type_name = PACIPV::cache_type::L1I;
        else if(cache_name.find("L1D") != std::string::npos)
                type_name = PACIPV::cache_type::L1D;
        else if(cache_name.find("L2C") != std::string::npos)
                type_name = PACIPV::cache_type::L2C;
        else if(cache_name.find("LLC") != std::string::npos)
                type_name = PACIPV::cache_type::LLC;
        else
                type_name = PACIPV::cache_type::UNDEFINED;

        if(type_name == PACIPV::cache_type::UNDEFINED)
        {
                std::cerr << "[ERROR (" << cache_name << ")] Could not infer cache type from name." << std::endl;
                std::exit(-1);
        }

        // Read the IPV specification from the environment varibles
        const char*           ipv_string;
        std::vector<uint32_t> demand_vector, prefetch_vector;
        switch(type_name)
        {
                case PACIPV::cache_type::L1I:
                        ipv_string = std::getenv("L1I_IPV");
                        break;
                case PACIPV::cache_type::L1D:
                        ipv_string = std::getenv("L1D_IPV");
                        break;
                case PACIPV::cache_type::L2C:
                        ipv_string = std::getenv("L2C_IPV");
                        break;
                case PACIPV::cache_type::LLC:
                        ipv_string = std::getenv("LLC_IPV");
                        break;
                default:
                        std::cerr << "[ERROR (" << cache_name << ")] Unknown cache type" << std::endl;
                        std::exit(-1);
        }

        if(ipv_string == nullptr)
        {
                std::cerr << "[ERROR (" << cache_name << ")] IPV not specified" << std::endl;
                std::exit(-1);
        }

        // Convert to C++ string
        std::string ipv_vals(ipv_string);

        // Split the string into demand and prefetch strings
        std::size_t split_point = ipv_vals.find(std::string("#"));
        if(split_point == std::string::npos)
        {
                std::cerr << "[ERROR (" << cache_name << ")] Illegal IPV specified. Please provide both demand and prefetch IPVs." << std::endl;
                std::exit(-1);
        }
        const std::string demand   = ipv_vals.substr(0, split_point++);
        const std::string prefetch = ipv_vals.substr(split_point);

        // Populate the demand and prefetch vectors based on the IPV strings
        std::istringstream demand_stream(demand);
        std::istringstream prefetch_stream(prefetch);
        uint32_t           val;
        while(demand_stream >> val)
        {
                demand_vector.push_back(val);
                demand_stream.ignore();
        }
        while(prefetch_stream >> val)
        {
                prefetch_vector.push_back(val);
                prefetch_stream.ignore();
        }

        // Check if the provided IPVs are valid
        if(demand_vector.size() != prefetch_vector.size())
        {
                std::cerr << "[ERROR (" << cache_name << ")] Illegal IPV specified. The sizes of demand and prefetch IPVs are not same." << std::endl;
                std::exit(-1);
        }

        const uint32_t max_demand_rrpv   = *std::max_element(demand_vector.cbegin(), demand_vector.cend());
        const uint32_t max_prefetch_rrpv = *std::max_element(prefetch_vector.cbegin(), prefetch_vector.cend());
        if(max_demand_rrpv >= demand_vector.size() || max_prefetch_rrpv >= prefetch_vector.size())
        {
                std::cerr << "[ERROR (" << cache_name << ")] Illegal IPV specified. RRPV values must be within [0, vector_size - 1]." << std::endl;
                std::exit(-1);
        }

        // Print out the parsed IPVS
        std::cout << "[" << cache_name << "] Demand IPV:";
        for(const uint32_t v: demand_vector) std::cout << " " << v;
        std::cout << " Prefetch IPV:";
        for(const uint32_t v: prefetch_vector) std::cout << " " << v;
        std::cout << std::endl;

        // Allocate the policies, one per cache set
        for(size_t idx = 0; idx < num_sets; idx++) policies[this].emplace_back(num_ways, demand_vector, prefetch_vector);
}

long PACIPV::find_victim([[maybe_unused]] uint32_t    triggering_cpu,
                            [[maybe_unused]] uint64_t     instr_id,
                            long                          set,
                            //long                          way,
                            [[maybe_unused]] const champsim::cache_block* current_set,
                            [[maybe_unused]] champsim::address     ip,
                            [[maybe_unused]] champsim::address    full_addr,
                            [[maybe_unused]] access_type     type)
{
        // Run sanity check
        assert(set < policies[this].size());
        
        return policies[this][set].find_victim();

}

void PACIPV::update_replacement_state([[maybe_unused]] uint32_t triggering_cpu,
                                     long                  set,
                                     long                  way,
                                     [[maybe_unused]] champsim::address full_addr,
                                     [[maybe_unused]] champsim::address ip,
                                     [[maybe_unused]] champsim::address victim_addr,
                                     access_type               type,
                                     uint8_t                   hit)
{
        // Run sanity checks
        assert(way < num_ways);
        assert(set < policies[this].size());

        if(type == access_type::PREFETCH) // Handle prefetch access
        {
                if(hit)
                        policies[this].at(set).prefetch_promote(way);
                else
                        policies[this].at(set).prefetch_insert(way);
        }
        else // Handle demand access
        {
                if(hit)
                        policies[this].at(set).demand_promote(way);
                else
                        policies[this].at(set).demand_insert(way);
        }
}

void PACIPV::replacement_final_stats()
{
        // Do nothing
        return;

}
