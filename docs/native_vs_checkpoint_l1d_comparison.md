# Native Full-Trace vs Checkpoint L1D Comparison

This report compares:

- checkpoint-based `python3 -m rl_controller.experiments` results from `docs/hash_table_l1d_coverage_accuracy_*.csv`
- native no-checkpoint full-trace results from `docs/native_fulltrace_l1d_coverage_accuracy_*.csv`

Important note: raw `total_ipc` is not directly comparable between the two pipelines.
The checkpoint experiment summary aggregates 100 windows, while native full-trace records a single run IPC.
This comparison therefore focuses on:

- same `trace + policy` coverage deltas
- same `trace + policy` accuracy deltas
- whether the best fixed policy identity changes per trace

Generated files:

- `docs/native_vs_checkpoint_l1d_pairwise.csv`
- `docs/native_vs_checkpoint_l1d_best_policy.csv`
- `docs/native_vs_checkpoint_l1d_policy_summary.csv`

Shared baseline rows: 392
Shared traces: 49

## Headline Numbers

- Mean absolute `L1D coverage` delta across all 392 baseline rows: `0.026571157586`
- Median absolute `L1D coverage` delta across all 392 baseline rows: `0.012408810076`
- Mean absolute `L1D accuracy` delta across all 392 baseline rows: `0.054767020126`
- Median absolute `L1D accuracy` delta across all 392 baseline rows: `0.014284963139`
- Rows with `|coverage delta| > 0.01`: `210/392`
- Rows with `|coverage delta| > 0.05`: `60/392`
- Rows with `|accuracy delta| > 0.05`: `99/392`
- Rows with `|accuracy delta| > 0.10`: `68/392`
- Traces where the `best fixed policy` changes: `41/49`
- Mean absolute delta on the chosen best-policy row: coverage `0.044371803494`, accuracy `0.170824508470`

## Policy-Level Aggregate Delta

| Policy | Rows | Checkpoint Avg Cov | Native Avg Cov | Delta Cov | Checkpoint Avg Acc | Native Avg Acc | Delta Acc | Checkpoint Wins | Native Wins | Delta Wins |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 49 | 0.105893564396 | 0.110589376674 | 0.004695812278 | 0.434084518158 | 0.458691410462 | 0.024606892304 | 8 | 8 | 0 |
| `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-PACIPV` | 49 | 0.105905337908 | 0.110511250937 | 0.004605913028 | 0.434069515339 | 0.458100649077 | 0.024031133738 | 1 | 0 | -1 |
| `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 49 | 0.105878025039 | 0.110243886006 | 0.004365860968 | 0.436304908750 | 0.458825381618 | 0.022520472868 | 9 | 13 | 4 |
| `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 49 | 0.105889584417 | 0.110252081523 | 0.004362497106 | 0.436284931678 | 0.458347896587 | 0.022062964909 | 5 | 5 | 0 |
| `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 49 | 0.044266178916 | 0.059339033017 | 0.015072854101 | 0.033255116477 | 0.037587243392 | 0.004332126915 | 7 | 4 | -3 |
| `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-PACIPV` | 49 | 0.044258867998 | 0.059495453961 | 0.015236585964 | 0.033401461879 | 0.037264420135 | 0.003862958256 | 2 | 2 | 0 |
| `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 49 | 0.044239741657 | 0.059611613547 | 0.015371871890 | 0.033356760357 | 0.036843507942 | 0.003486747585 | 6 | 6 | 0 |
| `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 49 | 0.044248279332 | 0.059411608255 | 0.015163328923 | 0.033244438450 | 0.036673427451 | 0.003428989000 | 11 | 11 | 0 |

## Traces With Largest Average Coverage Delta

| Trace | Mean Abs Coverage Delta Across 8 Policies |
| --- | ---: |
| 638.imagick_s-10316B | 0.164252476565 |
| 654.roms_s-1007B | 0.106218675175 |
| 447.dealII-3B | 0.068206088735 |
| 481.wrf-1170B | 0.063749484082 |
| 641.leela_s-1052B | 0.061742776221 |
| 465.tonto-1914B | 0.059967214265 |
| 482.sphinx3-1100B | 0.053962140105 |
| 444.namd-120B | 0.042797207227 |

## Traces With Largest Average Accuracy Delta

| Trace | Mean Abs Accuracy Delta Across 8 Policies |
| --- | ---: |
| 648.exchange2_s-1227B | 0.337609925790 |
| 470.lbm-1274B | 0.224581674793 |
| 621.wrf_s-575B | 0.147601252239 |
| 464.h264ref-30B | 0.140527669749 |
| 625.x264_s-12B | 0.137093211130 |
| 445.gobmk-17B | 0.123032961986 |
| 638.imagick_s-10316B | 0.122977951134 |
| 600.perlbench_s-1273B | 0.110033439923 |

## Interpretation

- `Coverage` differences are not tiny. The mean absolute delta is about `0.0266`, and more than half of all baseline rows exceed `0.01`.
- `Accuracy` differences are larger. The mean absolute delta is about `0.0548`, and `68/392` rows exceed `0.10`.
- The best-policy identity changes on `41/49` traces, which is a large shift, not noise-level drift.
- Native full-trace tends to raise `L1D coverage` slightly for every policy family, but the increase is much larger for `berti` (`+~0.015`) than for `gaze` (`+~0.004 to +0.005`).
- Native full-trace also raises `L1D accuracy` for all policy families, especially `gaze` (`+~0.022 to +0.025` absolute).
- So if the question is whether the checkpoint pipeline materially changes the conclusions, the answer is `yes`: the difference is large enough to alter which fixed policy wins on most traces.
