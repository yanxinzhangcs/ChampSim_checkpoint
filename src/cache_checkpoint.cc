#include "cache_checkpoint.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>
#include <stdexcept>
#include <fmt/core.h>
#include <fmt/ostream.h>

#include "cache.h"
#include "environment.h"

namespace
{
std::string trim_copy(std::string_view text)
{
  auto begin = text.begin();
  auto end = text.end();

  const auto is_space = [](unsigned char ch) { return std::isspace(ch) != 0; };

  while (begin != end && is_space(static_cast<unsigned char>(*begin))) {
    ++begin;
  }

  while (begin != end && is_space(static_cast<unsigned char>(*(end - 1)))) {
    --end;
  }

  return std::string(begin, end);
}

champsim::address parse_address_token(const std::string& token)
{
  std::size_t consumed = 0;
  unsigned long long value = 0;

  try {
    value = std::stoull(token, &consumed, 0);
  } catch (const std::exception& ex) {
    throw std::runtime_error(fmt::format("Failed to parse address token '{}' ({})", token, ex.what()));
  }

  if (consumed != token.size()) {
    throw std::runtime_error(fmt::format("Failed to parse address token '{}' ({} characters consumed)", token, consumed));
  }

  return champsim::address{value};
}
} // namespace

namespace champsim
{
void save_cache_checkpoint(environment& env, const std::filesystem::path& file_path)
{
  std::ofstream out_file{file_path};
  if (!out_file.is_open()) {
    throw std::runtime_error(fmt::format("Unable to open '{}' for writing cache checkpoint", file_path.string()));
  }

  for (const CACHE& cache : env.cache_view()) {
    fmt::print(out_file, "Cache: {}\n", cache.NAME);
    for (const auto& entry : cache.checkpoint_contents()) {
      fmt::print(out_file, "  Set: {} Way: {} Address: {}\n", entry.set, entry.way, entry.block.address);
    }
    fmt::print(out_file, "EndCache\n");
  }
}

void load_cache_checkpoint(environment& env, const std::filesystem::path& file_path)
{
  std::ifstream in_file{file_path};
  if (!in_file.is_open()) {
    throw std::runtime_error(fmt::format("Unable to open '{}' for reading cache checkpoint", file_path.string()));
  }

  std::unordered_map<std::string, std::vector<CACHE::checkpoint_entry>> checkpoints;
  std::string current_cache;
  std::string line;
  long line_number = 0;

  while (std::getline(in_file, line)) {
    ++line_number;
    auto trimmed_line = trim_copy(line);
    if (trimmed_line.empty()) {
      continue;
    }

    std::istringstream iss(trimmed_line);
    std::string token;
    iss >> token;

    if (token.empty()) {
      continue;
    }

    if (token == "Cache:") {
      std::string remainder;
      std::getline(iss >> std::ws, remainder);
      current_cache = trim_copy(remainder);
      checkpoints[current_cache]; // Ensure entry exists
      continue;
    }

    if (token == "EndCache") {
      current_cache.clear();
      continue;
    }

    if (token == "#") {
      continue;
    }

    if (token == "Set:") {
      if (current_cache.empty()) {
        throw std::runtime_error(fmt::format("Checkpoint parse error on line {}: 'Set' entry without active cache", line_number));
      }

      long set = -1;
      if (!(iss >> set)) {
        throw std::runtime_error(fmt::format("Checkpoint parse error on line {}: missing set value", line_number));
      }

      std::string way_label;
      if (!(iss >> way_label) || way_label != "Way:") {
        throw std::runtime_error(fmt::format("Checkpoint parse error on line {}: expected 'Way:' token", line_number));
      }

      long way = -1;
      if (!(iss >> way)) {
        throw std::runtime_error(fmt::format("Checkpoint parse error on line {}: missing way value", line_number));
      }

      std::string addr_label;
      if (!(iss >> addr_label) || addr_label != "Address:") {
        throw std::runtime_error(fmt::format("Checkpoint parse error on line {}: expected 'Address:' token", line_number));
      }

      std::string addr_token;
      if (!(iss >> addr_token)) {
        throw std::runtime_error(fmt::format("Checkpoint parse error on line {}: missing address token", line_number));
      }

      CACHE::checkpoint_entry entry{};
      entry.set = set;
      entry.way = way;
      entry.block.valid = true;
      entry.block.address = parse_address_token(addr_token);
      entry.block.v_address = entry.block.address;

      checkpoints[current_cache].push_back(entry);
      continue;
    }

    throw std::runtime_error(fmt::format("Checkpoint parse error on line {}: unexpected token '{}'", line_number, token));
  }

  for (CACHE& cache : env.cache_view()) {
    auto it = checkpoints.find(cache.NAME);
    if (it != std::end(checkpoints)) {
      cache.restore_checkpoint(it->second);
    } else {
      cache.restore_checkpoint({});
    }
  }
}
} // namespace champsim
