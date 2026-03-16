#include <catch.hpp>

#include <map>
#include <utility>
#include <vector>

#include "cache.h"
#include "defaults.hpp"
#include "mocks.hpp"

namespace
{
struct operate_record {
  champsim::address addr;
  champsim::address ip;
  uint64_t instr_id = 0;
  bool wrong_path = false;
  bool cache_hit = false;
  bool useful_prefetch = false;
  access_type type = access_type::LOAD;
};

std::map<CACHE*, int> operate_interface_discerner;
std::map<CACHE*, std::vector<operate_record>> operate_records;
std::map<CACHE*, std::vector<std::pair<champsim::address, uint64_t>>> squash_records;

struct introspective_prefetcher : champsim::modules::prefetcher {
  using prefetcher::prefetcher;

  uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint64_t instr_id, bool wrong_path, bool cache_hit,
                                    bool useful_prefetch, access_type type, uint32_t metadata_in)
  {
    ::operate_interface_discerner[intern_] = 1;
    ::operate_records[intern_].push_back({addr, ip, instr_id, wrong_path, cache_hit, useful_prefetch, type});
    return metadata_in;
  }

  uint32_t prefetcher_cache_operate(champsim::address, champsim::address, bool, bool, access_type, uint32_t metadata_in)
  {
    ::operate_interface_discerner[intern_] = 2;
    return metadata_in;
  }

  void prefetcher_squash(champsim::address ip, uint64_t instr_id) { ::squash_records[intern_].emplace_back(ip, instr_id); }
};
} // namespace

SCENARIO("The prefetcher interface forwards instr_id, wrong_path, and squash hooks")
{
  GIVEN("A single cache with a prefetcher that exposes the extended interface")
  {
    do_nothing_MRC mock_ll;
    to_rq_MRP mock_ul;
    CACHE uut{champsim::cache_builder{champsim::defaults::default_l1i}
                  .name("454-uut")
                  .upper_levels({&mock_ul.queues})
                  .lower_level(&mock_ll.queues)
                  .prefetcher<::introspective_prefetcher>()};

    std::array<champsim::operable*, 3> elements{{&mock_ll, &mock_ul, &uut}};

    for (auto elem : elements) {
      elem->initialize();
      elem->warmup = false;
      elem->begin_phase();
    }

    WHEN("A demand request carries instr_id and wrong_path metadata")
    {
      ::operate_interface_discerner[&uut] = 0;
      ::operate_records[&uut].clear();

      decltype(mock_ul)::request_type test;
      test.address = champsim::address{0xdeadbeef};
      test.v_address = champsim::address{0xdeadbeef};
      test.ip = champsim::address{0xcafebabe};
      test.instr_id = 77;
      test.wrong_path = true;
      test.cpu = 0;
      test.type = access_type::LOAD;
      test.is_translated = true;

      auto issued = mock_ul.issue(test);

      THEN("The request is accepted") { REQUIRE(issued); }

      for (auto i = 0; i < 20; ++i)
        for (auto elem : elements)
          elem->_operate();

      THEN("The extended cache_operate interface is selected")
      {
        REQUIRE(::operate_interface_discerner.at(&uut) == 1);
        REQUIRE_THAT(::operate_records.at(&uut), Catch::Matchers::SizeIs(1));
      }

      THEN("The prefetcher sees the request's instr_id and wrong_path flag")
      {
        REQUIRE_THAT(::operate_records.at(&uut), Catch::Matchers::SizeIs(1));
        CHECK(::operate_records.at(&uut).at(0).addr == test.address);
        CHECK(::operate_records.at(&uut).at(0).ip == test.ip);
        CHECK(::operate_records.at(&uut).at(0).instr_id == test.instr_id);
        CHECK(::operate_records.at(&uut).at(0).wrong_path == test.wrong_path);
        CHECK(::operate_records.at(&uut).at(0).cache_hit == false);
        CHECK(::operate_records.at(&uut).at(0).type == test.type);
      }

      AND_WHEN("The cache invokes the squash hook")
      {
        ::squash_records[&uut].clear();
        uut.impl_prefetcher_squash(test.ip, test.instr_id);

        THEN("The prefetcher receives the squash event")
        {
          REQUIRE_THAT(::squash_records.at(&uut), Catch::Matchers::SizeIs(1));
          CHECK(::squash_records.at(&uut).at(0).first == test.ip);
          CHECK(::squash_records.at(&uut).at(0).second == test.instr_id);
        }
      }
    }
  }
}
