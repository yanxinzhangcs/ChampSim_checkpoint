# Collecting 9-Policy Instruction-Level Datasets

This branch adds `scripts/collect_9_policy_traces.sh`, a reusable collection script for the nine advanced policy configurations used by the policy-ranking experiments.

## What It Collects

For each trace, the script builds and runs these policy configurations:

- `berti_barca_mock`
- `berti_barca_pacipv`
- `berti_entangle_mock`
- `berti_entangle_pacipv`
- `gaze_barca_mock`
- `gaze_barca_pacipv`
- `gaze_entangle_mock`
- `gaze_entangle_pacipv`
- `stride_stride_lru`

Each policy is built from the existing JSON files under `rl_controller/build_configs/`.

## Single Trace

```bash
cd /home/ubuntu/yanxin/ChampSim_checkpoint

scripts/collect_9_policy_traces.sh \
  /home/ubuntu/yanxin/ChampSim_checkpoint/657.xz_s-56B.champsimtrace.xz \
  /home/ubuntu/yanxin/ChampSim_checkpoint/collect_657_w2m_s100m_policies
```

The output layout is:

```text
collect_657_w2m_s100m_policies/input.npy
collect_657_w2m_s100m_policies/policy_configs.tsv
collect_657_w2m_s100m_policies/berti_barca_mock/output.npy
collect_657_w2m_s100m_policies/berti_barca_pacipv/output.npy
...
collect_657_w2m_s100m_policies/stride_stride_lru/output.npy
```

## 49-Trace Batch

Put all trace files in one directory, then run:

```bash
cd /home/ubuntu/yanxin/ChampSim_checkpoint

scripts/collect_9_policy_traces.sh \
  /home/ubuntu/yanxin/traces \
  /home/ubuntu/yanxin/ChampSim_checkpoint/policy_collect_49apps
```

The output layout is:

```text
policy_collect_49apps/<trace-name>/input.npy
policy_collect_49apps/<trace-name>/berti_barca_mock/output.npy
...
policy_collect_49apps/<trace-name>/stride_stride_lru/output.npy
```

## Important Notes

- The script intentionally does **not** pass `--commit-trace-warmup`, so only the 100M simulation instructions after warmup are written into CSV/NPY.
- The script copies the first generated `input.npy` to the benchmark root so training code can use a shared root input with policy subdirectory outputs.
- Intermediate `commit_trace*.csv` files can be deleted after validating `input.npy` and `output.npy`.

To delete CSVs automatically during collection:

```bash
DELETE_COMMIT_CSV=1 scripts/collect_9_policy_traces.sh TRACE_FILE OUT_ROOT
```

Other useful knobs:

```bash
WARMUP_INSTRUCTIONS=2000000 \
SIMULATION_INSTRUCTIONS=100000000 \
JOBS=32 \
SKIP_EXISTING=1 \
scripts/collect_9_policy_traces.sh TRACE_FILE OUT_ROOT
```
