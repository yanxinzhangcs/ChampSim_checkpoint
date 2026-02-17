#include <catch.hpp>

#include <sstream>

#include "instruction.h"

SCENARIO("A NeuroScalar-style instruction trace line can be dumped from an instruction")
{
  GIVEN("A load-like instruction with two sources and one destination")
  {
    input_instr i;
    i.ip = 0x1234;
    i.is_branch = false;
    i.branch_taken = false;

    std::fill(std::begin(i.destination_registers), std::end(i.destination_registers), 0);
    std::fill(std::begin(i.source_registers), std::end(i.source_registers), 0);
    i.destination_registers[0] = 10;
    i.source_registers[0] = 1;
    i.source_registers[1] = 2;

    std::fill(std::begin(i.destination_memory), std::end(i.destination_memory), 0);
    std::fill(std::begin(i.source_memory), std::end(i.source_memory), 0);
    i.source_memory[0] = 0xdeadbeef;

    ooo_model_instr instr{0, i};

    THEN("The derived opcode class identifies a load")
    {
      REQUIRE(instr.opcode == 1);
    }

    THEN("The dump format contains 8 comma-separated integer fields")
    {
      std::stringstream ss;
      instr.dump_neuroscalar_csv(ss, /*commit_cycle=*/42, /*delta_cycles=*/1);
      REQUIRE(ss.str() == "4660,3735928559,1,1,2,10,42,1\n");
    }
  }

  GIVEN("A store-like instruction")
  {
    input_instr i;
    i.ip = 1;
    i.is_branch = false;
    i.branch_taken = false;

    std::fill(std::begin(i.destination_registers), std::end(i.destination_registers), 0);
    std::fill(std::begin(i.source_registers), std::end(i.source_registers), 0);
    std::fill(std::begin(i.destination_memory), std::end(i.destination_memory), 0);
    std::fill(std::begin(i.source_memory), std::end(i.source_memory), 0);
    i.destination_memory[0] = 0x1000;

    ooo_model_instr instr{0, i};

    THEN("The derived opcode class identifies a store")
    {
      REQUIRE(instr.opcode == 2);
    }
  }

  GIVEN("A branch-like instruction")
  {
    input_instr i;
    i.ip = 1;
    i.is_branch = true;
    i.branch_taken = true;

    std::fill(std::begin(i.destination_registers), std::end(i.destination_registers), 0);
    std::fill(std::begin(i.source_registers), std::end(i.source_registers), 0);

    // Force it to look like an "other" branch by writing IP.
    i.destination_registers[0] = champsim::REG_INSTRUCTION_POINTER;
    i.source_registers[0] = champsim::REG_INSTRUCTION_POINTER;

    std::fill(std::begin(i.destination_memory), std::end(i.destination_memory), 0);
    std::fill(std::begin(i.source_memory), std::end(i.source_memory), 0);

    ooo_model_instr instr{0, i};

    THEN("The derived opcode class identifies a branch subtype (>= 4)")
    {
      REQUIRE(instr.opcode >= 4);
    }
  }
}

