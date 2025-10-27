#ifndef CACHE_CHECKPOINT_H
#define CACHE_CHECKPOINT_H

#include <filesystem>

namespace champsim
{
class environment;

void save_cache_checkpoint(environment& env, const std::filesystem::path& file_path);
void load_cache_checkpoint(environment& env, const std::filesystem::path& file_path);

} // namespace champsim

#endif
