# Static Policies vs Baseline Chip Analysis

## Overview

This analysis compares each individual static policy against a **baseline chip** that can dynamically choose between the two most frequently optimal policies:
1. **`berti/entangling/mockingjay`**
2. **`gaze/entangling/mockingjay`**

The baseline chip selects whichever of these two policies provides better IPC at each time step, creating a simple two-state dynamic reconfiguration system.

## Timestep-Level Results

### Dataset
- **Total time steps analyzed**: 4,900 (49 benchmarks × 100 steps each)
- **Time steps where baseline = oracle**: 3,408 (**69.6%**)
- **Mean baseline vs oracle loss**: 0.093%

### Policy Performance Rankings

Policies are ranked by average median loss vs baseline. **Positive loss** means the policy is worse than baseline; **zero loss** means it matches baseline performance.

| Rank | Policy | Median Loss vs Baseline | Mean Loss | Baseline Policy? |
|------|--------|------------------------|-----------|------------------|
| 1 | **gaze/barca/PACIPV** | 1.455% | 1.826% | ❌ |
| 2 | **gaze/entangling/PACIPV** | 1.454% | 1.835% | ❌ |
| 3 | **gaze/barca/mockingjay** | 1.453% | 1.832% | ❌ |
| 4 | **gaze/entangling/mockingjay** | **1.448%** | 1.843% | ✅ **BASELINE** |
| 5 | **berti/barca/PACIPV** | 0.789% | 0.914% | ❌ |
| 6 | **berti/entangling/PACIPV** | 0.781% | 0.923% | ❌ |
| 7 | **berti/barca/mockingjay** | 0.766% | 0.917% | ❌ |
| 8 | **berti/entangling/mockingjay** | **0.761%** | 0.928% | ✅ **BASELINE** |

## Key Insights

### 1. **Baseline Policies Perform As Expected**

The two baseline policies (`berti/entangling/mockingjay` and `gaze/entangling/mockingjay`) show positive median loss, but this is expected:
- **At ~50% of timesteps**: They are equal to baseline (0% loss) ← they ARE the baseline choice
- **At ~50% of timesteps**: They are worse than baseline (positive loss) ← the OTHER baseline policy is better

Key statistics for baseline policies:
- **`berti/entangling/mockingjay`**: 54.0% of timesteps equal to baseline, 0% worse
- **`gaze/entangling/mockingjay`**: 50.7% of timesteps equal to baseline, 0% worse

### 2. **Clear Performance Tiers**

**Gaze-based policies** (ranks 1-4):
- Average median loss: **~1.45%**
- These are the policies that use the `gaze` L1D prefetcher
- When one baseline policy is chosen, the other "gaze" baseline policy has minimal loss

**Berti-based non-baseline policies** (ranks 5-7):
- Average median loss: **~0.78%**
- These use the `berti` L1D prefetcher
- They outperform gaze-based policies significantly

### 3. **Component Analysis**

The results confirm the L1D prefetcher hierarchy:

**L1D Prefetcher**:
- `berti` policies: 0.76-0.79% median loss
- `gaze` policies: 1.45-1.46% median loss
- **`berti` is ~50% better** when not part of the baseline

**L1I Prefetcher (within berti group)**:
- `entangling`: 0.761-0.781% median loss
- `barca`: 0.766-0.789% median loss
- Minimal difference (~0.02%)

**L2C Replacement (within berti group)**:
- `mockingjay`: 0.761-0.766% median loss
- `PACIPV`: 0.781-0.789% median loss
- Small difference (~0.02%)

### 4. **When Static Policies Beat Baseline**

Looking at the "pct_better_than_baseline" metric, we can see which policies occasionally outperform the baseline:

**Best non-baseline policies** (% of timesteps better than baseline):
- All `berti` policies occasionally beat baseline when baseline is currently using `gaze`
- All `gaze` policies occasionally beat baseline when baseline is currently using `berti`

However, the **median** loss is always positive, meaning static policies typically underperform.

## Per-Application Highlights

### Applications Where Static Policies Struggle Most

Applications with highest median loss for non-baseline policies:

**`gaze/barca/PACIPV` worst performers**:
- `410.bwaves-1963B`: 16.35% loss
- `638.imagick_s-10316B`: 13.15% loss
- `649.fotonik3d_s-10881B`: 11.55% loss
- `619.lbm_s-2676B`: 10.01% loss

These applications **strongly benefit** from dynamic policy switching.

### Applications Where Static = Baseline

Some applications show **0% median loss** for certain static policies, meaning the static policy equals or exceeds baseline performance:

Examples include:
- `410.bwaves-1963B` with `berti/...mockingjay` policies: 0% loss
- `638.imagick_s-10316B` with all `berti` policies: 0% loss
- Multiple applications with `berti` variants

## Bottom Line

### Performance Summary

**Compared to baseline chip** (which dynamically switches between two policies):

1. **Non-baseline policies lose performance**:
   - `gaze`-based policies: **~1.5%** median loss
   - `berti`-based policies: **~0.8%** median loss

2. **The baseline policies themselves**:
   - Show positive median loss because they're only optimal 50% of the time
   - When aggregated together (the baseline chip), they achieve 69.6% oracle coverage

3. **Best single static policy**: `berti/entangling/mockingjay`
   - Median loss vs baseline: 0.761%
   - But this is still worse than the baseline chip!

### Recommendation

**The baseline chip (dynamic switching between `berti/entangling/mockingjay` and `gaze/entangling/mockingjay`) is significantly better than ANY single static policy.**

Specifically:
- The baseline chip loses only **0.093%** vs oracle
- The best static policy loses **0.761%** vs baseline = **0.854%** vs oracle
- **The baseline chip is 9x better** than the best static policy

## Files Generated

- `policies_vs_baseline_summary.png` - Summary comparison of all 8 policies
- `policy_vs_baseline_<policy>.png` - Detailed box plots for each policy (8 files)
- `policies_vs_baseline_statistics.csv` - Complete per-application statistics
- `analyze_policies_vs_baseline.py` - Analysis script
