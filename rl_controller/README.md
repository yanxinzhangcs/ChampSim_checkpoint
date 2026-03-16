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
  --agent ppo \
  --ppo-rollout-size 32 \
  --ppo-epochs 4 \
  --ppo-minibatch-size 32
```

The `--resume-warmup` knob controls how many instructions are run before each
measurement window after the checkpoint is restored.  Keeping it small (e.g.
`1` or `100`) avoids deadlocks while leaving the cache contents largely intact.

The script prints one line per step with the chosen action and IPC, and
stores detailed statistics in `rl_runs/.../iter_XXXX_stats.json`.  A
summary of the episode lives in `episode_summary.json`.

### Notes

- Step 0 starts from a warm checkpoint created once with the base action.
  Later windows chain from the previous window's checkpoint at the matching
  trace offset, so `main.py` models a continuous policy rollout rather than
  re-evaluating every step from the same cache state.
- `experiments.py` uses the RL rollout's step-start checkpoint for its per-step
  action grid, so each action in that comparison is evaluated from the same
  cache state the rollout saw at that step.
- New ChampSim binaries are generated lazily and cached (for example
  `bin/champsim_rl_llc-replacement-srrip_l2c-prefetcher-next_line`).  If
  you change module code, remove the corresponding binary to force a
  rebuild.
- `--agent ppo` is the default and uses clipped PPO with a linear actor-critic
  model over the discrete action combinations.
- `--agent random` samples uniformly.
- `--agent epsilon_greedy` is kept as a legacy baseline and uses `--epsilon`
  for exploration.
- `--agent hash_table` bins the 7-D state into 128 buckets using `--hash-cutoffs`
  and does per-bucket epsilon-greedy selection. The learned table is saved to
  `<output>/hash_table.json` (override with `--hash-table`).
- The controller keeps track of the trace offset: each step fast-forwards by
  the cumulative `warmup + resume + window` instructions consumed so far, then
  restores the prior cache checkpoint before running the next window.
- Each `RunResult` exposes a feature vector so you can plug in richer RL
  algorithms (contextual bandits, actor-critic, etc.) with minimal wiring.

## Full-trace fixed-policy sweep

If you want to run *every* fixed policy in an action space over the whole trace
(one warmup + one simulation run per policy), use:

```bash
export L2C_IPV="0 1 1 0 3#0 1 0 0 3"  # required when PACIPV is in the action space
python3 -m rl_controller.full_trace_policies \
  --config rl_controller/action_space_perlbench_combo.json \
  --trace traces/600.perlbench_s-210B.champsimtrace.xz \
  --warmup 1000000 \
  --jobs 4 \
  --output rl_results/perlbench_combo_fulltrace
```

Outputs:
- `.../baseline/<policy>/full_trace_stats.json` and `.../baseline/<policy>/full_trace.log`
- `.../experiment_summary.json` (best policy + per-policy IPC)
