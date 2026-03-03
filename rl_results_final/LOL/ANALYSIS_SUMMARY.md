# Policy Performance Analysis Summary

## Overview
This analysis examines the performance cost of selecting a static prefetcher/replacement policy versus dynamically choosing the best policy at each execution step (1M instructions).

## Key Findings

### 1. Different Benchmarks Prefer Different Policies ✓

**YES - Different applications show clear preferences for different static policies:**

- **All 8 possible policy combinations** appear as the "best static policy" for at least one benchmark
- Policy preference distribution across 49 benchmarks:
  - `gaze/barca/PACIPV`: **14 benchmarks (28.6%)**
  - `berti/barca/PACIPV`: **11 benchmarks (22.4%)**
  - `berti/barca/mockingjay`: **9 benchmarks (18.4%)**
  - `berti/entangling/PACIPV`: **5 benchmarks (10.2%)**
  - `gaze/entangling/PACIPV`: **4 benchmarks (8.2%)**
  - `gaze/entangling/mockingjay`: **3 benchmarks (6.1%)**
  - `gaze/barca/mockingjay`: **2 benchmarks (4.1%)**
  - `berti/entangling/mockingjay`: **1 benchmark (2.0%)**

### 2. Performance Loss Distribution

**Average performance loss from choosing best static policy per benchmark: 0.225%**

- **Range**: 0.000% to 1.180%
- Most benchmarks see very low loss (<0.5%) from picking the right static policy
- A few benchmarks are more sensitive:
  - `607.cactuBSSN_s-2421B`: 1.180% loss
  - `627.cam4_s-490B`: 1.068% loss
  - `628.pop2_s-17B`: 0.694% loss

### 3. Best Universal Static Policy

If you must choose **one static policy** for all benchmarks:

**Winner: `berti/barca/PACIPV`**
- Average loss across all benchmarks: **1.007%**
- Was the best choice for 46 time steps across all benchmarks
- Very close runners-up:
  - `berti/barca/mockingjay`: 1.010% loss
  - `berti/entangling/PACIPV`: 1.015% loss
  - `berti/entangling/mockingjay`: 1.020% loss

### 4. Policy Component Analysis

Breaking down the policies:

**L1D Prefetcher:**
- `berti` policies generally perform better across benchmarks
- Average loss for `berti` policies: ~1.01%
- Average loss for `gaze` policies: ~1.92%

**L1I Prefetcher:**
- `barca` and `entangling` perform similarly
- Slight edge to `barca` in most cases

**L2C Replacement:**
- `PACIPV` and `mockingjay` perform very similarly
- Nearly identical average losses

### 5. Temporal Variation

From the single-benchmark analysis (400.perlbench-41B):
- Performance loss varies significantly over execution time
- Some time steps see **0% loss** (the static policy happens to be optimal)
- Other time steps see up to **12% instantaneous loss**
- The loss is **not uniformly distributed** - there are "hot spots" where the wrong policy hurts more

### 6. Cost of Being Wrong

**Worst-case scenarios when picking wrong static policy:**
- `berti` policies: max ~3.7% loss at worst time step
- `gaze` policies: max ~6.7% loss at worst time step
- This shows that `gaze` policies can occasionally perform much worse

## Implications

1. **Application-specific tuning matters**: Different benchmarks clearly prefer different policies, with no single policy winning everywhere.

2. **Dynamic switching potential**: The average 0.225% loss from optimal per-benchmark static policy vs. 1.007% from universal static policy suggests **4.5x improvement potential** from application-aware policy selection.

3. **Temporal adaptation potential**: Within a single benchmark, the best policy changes over time. Dynamic switching could eliminate the remaining 0.225% loss.

4. **Safe conservative choice**: If deploying across diverse workloads, `berti/barca/PACIPV` is the safest universal choice with only 1.007% average loss.

5. **Component priorities**: The L1D prefetcher choice (`berti` vs `gaze`) has the biggest impact on performance variance.

## Files Generated

- `400.perlbench-41B_policy_analysis.png`: Detailed single-benchmark visualization
- `400.perlbench-41B_detailed_results.csv`: Per-step results for first benchmark
- `400.perlbench-41B_policy_stats.csv`: Policy statistics for first benchmark
- `all_benchmarks_analysis.png`: Comprehensive cross-benchmark visualization
- `all_benchmarks_policy_stats.csv`: Complete statistics for all 49 benchmarks × 8 policies
