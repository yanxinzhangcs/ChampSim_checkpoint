/*
 *    Copyright 2023 The ChampSim Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <algorithm>
#include <fstream>
#include <numeric>
#include <string>
#include <string_view>
#include <vector>
#include <CLI/CLI.hpp>
#include <fmt/core.h>
#include <fmt/format.h>

#include "cache.h" // for CACHE
#include "champsim.h"
#ifndef CHAMPSIM_TEST_BUILD
#include "core_inst.inc"
#endif
#include "defaults.hpp"
#include "environment.h"
#include "ooo_cpu.h" // for O3_CPU
#include "phase_info.h"
#include "stats_printer.h"
#include "tracereader.h"
#include "vmem.h"

namespace champsim
{
std::vector<phase_stats> main(environment& env, std::vector<phase_info>& phases, std::vector<tracereader>& traces);
}

#ifndef CHAMPSIM_TEST_BUILD
using configured_environment = champsim::configured::generated_environment<CHAMPSIM_BUILD>;

const std::size_t NUM_CPUS = configured_environment::num_cpus;

const unsigned BLOCK_SIZE = configured_environment::block_size;
const unsigned PAGE_SIZE = configured_environment::page_size;
#endif
const unsigned LOG2_BLOCK_SIZE = champsim::lg2(BLOCK_SIZE);
const unsigned LOG2_PAGE_SIZE = champsim::lg2(PAGE_SIZE);

#ifndef CHAMPSIM_TEST_BUILD
int main(int argc, char** argv) // NOLINT(bugprone-exception-escape)
{
  configured_environment gen_environment{};

  CLI::App app{"A microarchitecture simulator for research and education"};

  bool knob_cloudsuite{false};
  bool knob_verbose{false};
  long long warmup_instructions = 0;
  long long simulation_instructions = std::numeric_limits<long long>::max();
  long subtrace_count = 1;
  std::string json_file_name;
  std::string checkpoint_path;
  std::string commit_trace_prefix;
  bool commit_trace_warmup = false;
  long long skip_instructions = 0;
  std::vector<std::string> trace_names;

  auto set_heartbeat_callback = [&](auto) {
    for (O3_CPU& cpu : gen_environment.cpu_view()) {
      cpu.show_heartbeat = false;
    }
  };

  app.add_flag("-c,--cloudsuite", knob_cloudsuite, "Read all traces using the cloudsuite format");
  app.add_flag("--verbose", knob_verbose, "Enable detailed console output");
  app.add_flag("--hide-heartbeat", set_heartbeat_callback, "Hide the heartbeat output");
  auto* warmup_instr_option = app.add_option("-w,--warmup-instructions", warmup_instructions, "The number of instructions in the warmup phase");
  auto* deprec_warmup_instr_option =
      app.add_option("--warmup_instructions", warmup_instructions, "[deprecated] use --warmup-instructions instead")->excludes(warmup_instr_option);
  auto* sim_instr_option = app.add_option("-i,--simulation-instructions", simulation_instructions,
                                          "The number of instructions in the detailed phase. If not specified, run to the end of the trace.");
  auto* deprec_sim_instr_option =
      app.add_option("--simulation_instructions", simulation_instructions, "[deprecated] use --simulation-instructions instead")->excludes(sim_instr_option);

  auto* json_option =
      app.add_option("--json", json_file_name, "The name of the file to receive JSON output. If no name is specified, stdout will be used")->expected(0, 1);
  app.add_option("--subtrace-count", subtrace_count, "Number of simulation subtraces to run sequentially after warmup")->check(CLI::PositiveNumber);
  app.add_option("--cache-checkpoint", checkpoint_path, "Path to cache checkpoint log file used to persist cache contents between phases")
      ->expected(0, 1);
  auto* commit_trace_option =
      app.add_option("--commit-trace", commit_trace_prefix,
                     "Write per-CPU commit traces as CSV. If no argument is given, defaults to 'commit_trace'.")
          ->expected(0, 1);
  app.add_flag("--commit-trace-warmup", commit_trace_warmup, "Also dump warmup-phase commits to the commit trace CSV");
  app.add_option("--skip-instructions", skip_instructions, "Number of instructions to fast-forward before warmup")
      ->check(CLI::NonNegativeNumber);

  app.add_option("traces", trace_names, "The paths to the traces")->required()->expected(NUM_CPUS)->check(CLI::ExistingFile);

  CLI11_PARSE(app, argc, argv);

  const bool warmup_given = (warmup_instr_option->count() > 0) || (deprec_warmup_instr_option->count() > 0);
  const bool simulation_given = (sim_instr_option->count() > 0) || (deprec_sim_instr_option->count() > 0);

  if (!knob_verbose) {
    set_heartbeat_callback(0);
  }
  gen_environment.dram_view().set_verbose(knob_verbose);

  if (deprec_warmup_instr_option->count() > 0) {
    fmt::print("WARNING: option --warmup_instructions is deprecated. Use --warmup-instructions instead.\n");
  }

  if (deprec_sim_instr_option->count() > 0) {
    fmt::print("WARNING: option --simulation_instructions is deprecated. Use --simulation-instructions instead.\n");
  }

  if (simulation_given && !warmup_given) {
    // Warmup is 20% by default
    // NOLINTNEXTLINE(cppcoreguidelines-avoid-magic-numbers,readability-magic-numbers)
    warmup_instructions = simulation_instructions / 5;
  }

  if (subtrace_count <= 0) {
    fmt::print("ERROR: --subtrace-count must be at least 1.\n");
    return 1;
  }

  if (subtrace_count > 1 && !simulation_given) {
    fmt::print("ERROR: --subtrace-count greater than 1 requires --simulation-instructions to be specified.\n");
    return 1;
  }

  std::vector<champsim::tracereader> traces;
  std::transform(
      std::begin(trace_names), std::end(trace_names), std::back_inserter(traces),
      [knob_cloudsuite, repeat = simulation_given, i = uint8_t(0)](auto name) mutable { return get_tracereader(name, i++, knob_cloudsuite, repeat); });

  if (skip_instructions > 0) {
    for (auto& trace : traces) {
      for (long long skipped = 0; skipped < skip_instructions && !trace.eof(); ++skipped) {
        static_cast<void>(trace());
      }
    }
  }

  if (commit_trace_option->count() > 0) {
    if (commit_trace_prefix.empty()) {
      commit_trace_prefix = "commit_trace";
    }

    const auto make_trace_name = [&](const std::string& base, std::size_t cpu) -> std::string {
      constexpr std::string_view ext{".csv"};
      const bool has_csv_ext = (base.size() >= ext.size()) && (base.compare(base.size() - ext.size(), ext.size(), ext) == 0);
      const auto stem = has_csv_ext ? base.substr(0, base.size() - ext.size()) : base;

      if (NUM_CPUS == 1) {
        return has_csv_ext ? base : (stem + std::string(ext));
      }
      return stem + ".cpu" + std::to_string(cpu) + std::string(ext);
    };

    for (O3_CPU& cpu : gen_environment.cpu_view()) {
      try {
        cpu.open_commit_trace(make_trace_name(commit_trace_prefix, cpu.cpu), commit_trace_warmup);
      } catch (const std::exception& e) {
        fmt::print("ERROR: failed to open commit trace: {}\n", e.what());
        return 1;
      }
    }
  }

  std::vector<std::size_t> default_trace_index(std::size(trace_names));
  std::iota(std::begin(default_trace_index), std::end(default_trace_index), 0);

  std::vector<champsim::phase_info> phases;
  phases.reserve(static_cast<std::size_t>(subtrace_count) + 1);

  auto make_phase = [&](std::string name, bool is_warmup_phase, long long length) {
    champsim::phase_info phase;
    phase.name = std::move(name);
    phase.is_warmup = is_warmup_phase;
    phase.length = length;
    phase.trace_index = default_trace_index;
    phase.trace_names = trace_names;
    return phase;
  };

  auto warm_phase = make_phase("Warmup", true, warmup_instructions);
  warm_phase.verbose = knob_verbose;
  if (!checkpoint_path.empty() && warmup_instructions > 0) {
    warm_phase.cache_checkpoint_out = checkpoint_path;
  }
  phases.push_back(std::move(warm_phase));

  for (long idx = 0; idx < subtrace_count; ++idx) {
    auto name = (idx == 0) ? std::string{"Simulation"} : fmt::format("Simulation-{}", idx);
    auto sim_phase = make_phase(name, false, simulation_instructions);
    if (!checkpoint_path.empty()) {
      sim_phase.cache_checkpoint_in = checkpoint_path;
      sim_phase.cache_checkpoint_out = checkpoint_path;
    }
    sim_phase.verbose = knob_verbose;
    phases.push_back(std::move(sim_phase));
  }

  if (knob_verbose) {
    fmt::print(
        "\n*** ChampSim Multicore Out-of-Order Simulator ***\nWarmup Instructions: {}\nSimulation Instructions: {}\nSimulation Subtraces: {}\nNumber of CPUs: "
        "{}\nPage size: {}\n\n",
        phases.at(0).length, phases.at(1).length, subtrace_count, std::size(gen_environment.cpu_view()), PAGE_SIZE);
  }

  auto phase_stats = champsim::main(gen_environment, phases, traces);

  if (knob_verbose) {
    fmt::print("\nChampSim completed all CPUs\n\n");
  }

  std::vector<long long> total_instrs(std::size(gen_environment.cpu_view()), 0);
  std::vector<long long> total_cycles(std::size(gen_environment.cpu_view()), 0);

  for (const auto& phase_stat : phase_stats) {
    for (std::size_t cpu = 0; cpu < std::size(phase_stat.sim_cpu_stats); ++cpu) {
      const auto instrs = phase_stat.sim_cpu_stats.at(cpu).instrs();
      const auto cycles = phase_stat.sim_cpu_stats.at(cpu).cycles();
      total_instrs.at(cpu) += instrs;
      total_cycles.at(cpu) += cycles;
    }
  }

  for (std::size_t cpu = 0; cpu < std::size(total_instrs); ++cpu) {
    const auto cycles = total_cycles.at(cpu);
    const double ipc = (cycles > 0) ? static_cast<double>(total_instrs.at(cpu)) / static_cast<double>(cycles) : 0.0;
    fmt::print("CPU {} IPC: {:.6f}\n", cpu, ipc);
  }

  for (CACHE& cache : gen_environment.cache_view()) {
    cache.impl_prefetcher_final_stats();
  }

  for (CACHE& cache : gen_environment.cache_view()) {
    cache.impl_replacement_final_stats();
  }

  if (json_option->count() > 0) {
    if (json_file_name.empty()) {
      champsim::json_printer{std::cout}.print(phase_stats);
    } else {
      std::ofstream json_file{json_file_name};
      champsim::json_printer{json_file}.print(phase_stats);
    }
  }

  return 0;
}
#endif
