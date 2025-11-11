# RL Controller for ChampSim

This folder provides a minimal harness that

1. builds policy-specific ChampSim binaries on demand,
2. creates a reusable cache checkpoint after warmup,
3. runs fixed-size simulation windows starting from that checkpoint, and
4. records per-window statistics together with the chosen action.

The default action space includes two heads:

| head name        | JSON path          | choices (editable)          |
|------------------|--------------------|-----------------------------|
| `l2c_prefetcher` | `["L2C","prefetcher"]` | `no`, `next_line`, `ip_stride` |
| `llc_replacement`| `["LLC","replacement"]`| `lru`, `srrip`, `random`        |

You can edit `action_space.json` to add or remove discrete options and to
change the warmup policy used for the initial checkpoint.

## Usage

```bash
python -m rl_controller.main \
  --trace /path/to/trace.champsimtrace.xz \
  --warmup 10000000 \
  --window 50000000 \
  --steps 5 \
  --output rl_runs/perlbench \
  --resume-warmup 100 \
  --agent epsilon_greedy \
  --epsilon 0.1
```

The `--resume-warmup` knob controls how many instructions are run before each
measurement window after the checkpoint is restored.  Keeping it small (e.g.
`1` or `100`) avoids deadlocks while leaving the cache contents largely intact.

The script prints one line per step with the chosen action and IPC, and
stores detailed statistics in `rl_runs/.../iter_XXXX_stats.json`.  A
summary of the episode lives in `episode_summary.json`.

### Notes

- The harness reuses a warm checkpoint created once with the base action.
  Each window restores that state before running the measurement phase,
  so you can compare policies under identical cache contents.
- New ChampSim binaries are generated lazily and cached (for example
  `bin/champsim_rl_llc-replacement-srrip_l2c-prefetcher-next_line`).  If
  you change module code, remove the corresponding binary to force a
  rebuild.
- Two policy options exist out of the box: `--agent random` samples uniformly,
  while `--agent epsilon_greedy` (default) keeps running action-value
  averages and explores with probability `--epsilon`.
- The controller keeps track of the trace offset: each step fast-forwards by
  the cumulative `warmup + resume + window` instructions consumed so far, then
  restores the prior cache checkpoint before running the next window.
- Each `RunResult` exposes a feature vector so you can plug in richer RL
  algorithms (contextual bandits, actor-critic, etc.) with minimal wiring.
