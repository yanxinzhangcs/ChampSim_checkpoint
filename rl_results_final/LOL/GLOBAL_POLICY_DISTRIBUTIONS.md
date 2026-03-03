# Global Loss Distribution Analysis: All Policies vs Baseline

## Overview

This analysis generates **global loss distributions** for each of the 8 policies, treating all 4,900 timesteps (49 benchmarks × 100 steps) as individual datapoints.

Each policy's loss is calculated vs the **baseline chip** (which dynamically switches between `berti/entangling/mockingjay` and `gaze/entangling/mockingjay`).

## Summary Rankings

Policies ranked by **median loss** (lower is closer to baseline):

| Rank | Policy | Median Loss | Mean Loss | % Equals Baseline | Baseline? |
|------|--------|-------------|-----------|-------------------|-----------|
| 1 | **berti/entangling/mockingjay** | 0.000% | 0.928% | 54.0% | ✓ **Yes** |
| 2 | **gaze/entangling/mockingjay** | 0.000% | 1.843% | 50.7% | ✓ **Yes** |
| 3 | berti/barca/mockingjay | 0.004% | 0.917% | 40.1% | No |
| 4 | berti/entangling/PACIPV | 0.020% | 0.923% | 39.0% | No |
| 5 | berti/barca/PACIPV | 0.055% | 0.914% | 27.8% | No |
| 6 | gaze/entangling/PACIPV | 0.059% | 1.835% | 36.4% | No |
| 7 | gaze/barca/mockingjay | 0.068% | 1.832% | 34.4% | No |
| 8 | gaze/barca/PACIPV | 0.119% | 1.826% | 23.1% | No |

## Key Insights

### 1. **Baseline Policies Show Expected Behavior**

The two baseline policies (`berti/entangling/mockingjay` and `gaze/entangling/mockingjay`) have:
- **Median loss of 0%** - they form the baseline, so equals baseline 50-54% of the time
- **Non-zero mean loss** - because when one is chosen, the other shows positive loss
- This is exactly what we expect!

### 2. **Clear Performance Tiers**

**Tier 1 - Excellent** (median < 0.1%):
- All 4 `berti/entangling` and `berti/barca` variants
- These are very close to baseline performance

**Tier 2 - Good** (median < 0.15%):
- All 4 `gaze` variants  
- Still close to baseline, but slightly worse

### 3. **Component Importance Hierarchy**

Looking at non-baseline policies:

**L1D Prefetcher** (most important):
- `berti` best median: 0.004%
- `gaze` best median: 0.059%
- **15x difference!**

**L2C Replacement** (second):
- `mockingjay` average median: ~0.036%
- `PACIPV` average median: ~0.064%
- ~2x difference

**L1I Prefetcher** (least important for matching baseline):
- `entangling` vs `barca` show minimal difference
- Both are close when paired with right L1D and L2C

### 4. **Distribution Shapes Reveal Behavior**

**Baseline policies** (`berti/entangling/mockingjay` and `gaze/entangling/mockingjay`):
- **54% and 51%** at exactly 0% (equals baseline)
- **0%** at negative loss (never beat baseline, they ARE baseline!)
- Rest distributed in positive loss (when other baseline policy is chosen)

**Best non-baseline** (`berti/barca/mockingjay`):
- **40%** at 0% (frequently equals baseline)
- **~9%** at negative loss (sometimes beats baseline!)
- Generally tight distribution near zero

**Worst** (`gaze/barca/PACIPV`):
- **23%** at 0% (less frequently equals baseline)
- **~16%** at negative loss (beats baseline moderately often)
- More spread out distribution

### 5. **Negative Loss is Common for Non-Baseline Policies**

All 6 non-baseline policies show **8-17%** of timesteps with negative loss (beating the baseline).

This shows the baseline chip's limitation - it can only choose between 2 policies, so sometimes other configurations are actually better.

## Visualization Files Generated

**Individual Detailed Plots** (8 files):
- `global_dist_berti_barca_PACIPV.png`
- `global_dist_berti_barca_mockingjay.png`
- `global_dist_berti_entangling_PACIPV.png`
- `global_dist_berti_entangling_mockingjay.png` (baseline policy)
- `global_dist_gaze_barca_PACIPV.png`
- `global_dist_gaze_barca_mockingjay.png`
- `global_dist_gaze_entangling_PACIPV.png`
- `global_dist_gaze_entangling_mockingjay.png` (baseline policy)

Each shows:
- Detailed loss distribution by ranges (including negative ranges)
- Color coding: Green = beats baseline, Yellow = equals, Red = worse
- Statistics box with mean, median, std, min, max, 95th percentile

**Summary Comparison** (1 file):
- `global_dist_summary_all_policies.png`
- Shows all 8 policies side-by-side
- Simplified view for easy comparison
- Baseline policies marked with ★

**Summary Statistics** (1 file):
- `global_policy_distributions_summary.csv`
- Complete statistics for all policies

## Comparison: Baseline Chip vs Best Static Policy

### Baseline Chip (vs Oracle):
- Median loss: **0.000%**
- Mean loss: **0.093%**
- 70.6% of timesteps: Perfect oracle match

### Best Static Policy (`berti/barca/mockingjay` vs Baseline):
- Median loss: **0.004%**
- Mean loss: **0.917%**
- 40.1% of timesteps: Equals baseline

**But wait!** This isn't comparing apples to apples:
- Baseline vs Oracle: Shows how close baseline is to perfect
- Static vs Baseline: Shows how close static is to baseline

**To compare static vs oracle**, we need to add the losses:
- Best static vs oracle ≈ 0.004% (vs baseline) + 0.093% (baseline vs oracle) ≈ **0.10%**

Still **excellent**, but the baseline chip with dynamic switching is better!

## Bottom Line

✓ **Global distributions are much clearer** than per-benchmark box plots  
✓ **Baseline policies dominate** with median loss of 0%  
✓ **Best non-baseline policy** (`berti/barca/mockingjay`) has median loss of only 0.004%  
✓ **All `berti` policies** are within 0.055% median loss of baseline  
✓ **`gaze` policies** show 0.06-0.12% median loss - still very good  

The two-policy baseline chip is **remarkably effective** - even the best alternative single static policy can only match its performance ~40% of the time.

## Files Generated

- 8 individual detailed distribution plots
- 1 summary comparison figure
- 1 summary statistics CSV
- `create_global_policy_distributions.py` - Analysis script
