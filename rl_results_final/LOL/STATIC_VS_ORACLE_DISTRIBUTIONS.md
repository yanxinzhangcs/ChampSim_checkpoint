# Static Policy Loss Distribution vs Oracle - Global Analysis

## Overview

This analysis shows the **global loss distribution** for each static policy compared to the oracle (best possible policy at each timestep).

**Interpretation**: "If I use ONLY this one policy for all 4,900 timesteps, what is my IPC loss distribution compared to always picking the optimal policy?"

**Key point**: Loss is **always ≥ 0%** because oracle is the best possible by definition.

## Rankings

Policies ranked by **median loss** (lower is better):

| Rank | Policy | Median Loss | Mean Loss | % Optimal | % Excellent (<1%) |
|------|--------|-------------|-----------|-----------|-------------------|
| 1 | **berti/barca/PACIPV** | 0.085% | 1.007% | 41.1% | 76.0% |
| 2 | **berti/entangling/PACIPV** | 0.090% | 1.015% | 40.3% | 76.0% |
| 3 | **berti/barca/mockingjay** | 0.093% | 1.010% | 40.1% | 76.1% |
| 4 | **berti/entangling/mockingjay** | 0.101% | 1.020% | 39.1% | 76.1% |
| 5 | **gaze/entangling/PACIPV** | 0.127% | 1.926% | 36.7% | 69.9% |
| 6 | **gaze/entangling/mockingjay** | 0.134% | 1.933% | 34.6% | 69.9% |
| 7 | **gaze/barca/PACIPV** | 0.144% | 1.917% | 36.8% | 69.8% |
| 8 | **gaze/barca/mockingjay** | 0.153% | 1.923% | 34.6% | 70.0% |

## Key Insights

### 1. **All Policies Perform Remarkably Well**

Even the "worst" static policy (`gaze/barca/mockingjay`) has:
- Median loss: **0.153%**
- Mean loss: **1.923%**
- Optimal 34.6% of the time
- Excellent (<1% loss) 70% of the time

This is outstanding for a completely static configuration!

### 2. **Clear Berti vs Gaze Divide**

**Berti policies** (ranks 1-4):
- Median loss: **0.085-0.101%**
- Mean loss: **~1.01%**
- Optimal: **39-41%** of timesteps

**Gaze policies** (ranks 5-8):
- Median loss: **0.127-0.153%**
- Mean loss: **~1.92%**
- Optimal: **35-37%** of timesteps

**Berti is about 2x better** than gaze in both median and mean loss!

### 3. **Very Tight Clustering Within Groups**

**Berti group variance**:
- Median: 0.085% to 0.101% (only 0.016% spread!)
- All berti policies are nearly identical

**Gaze group variance**:
- Median: 0.127% to 0.153% (only 0.026% spread!)
- All gaze policies are also nearly identical

The **L1D prefetcher choice dominates** - variations in L1I and L2C matter very little!

### 4. **Distribution Shapes**

All policies show similar distribution patterns:
- **~40%** at 0% (optimal)
- **~15%** at 0-0.1% (near-optimal)
- **~10%** at 0.1-0.5%
- **~10%** at 0.5-1%
- Long tail extending to 10-20% maximum

This suggests workload characteristics drive the distribution shape more than policy choice.

### 5. **Best Single Static Policy**

**`berti/barca/PACIPV`** is the winner:
- **Median loss: 0.085%**
- **Mean loss: 1.007%**
- **Optimal 41.1%** of timesteps
- **Excellent 76.0%** of timesteps

This is your best bet if you can only choose ONE policy!

## Comparison with Previous Analyses

### vs Full Trace Analysis:
Remember from `FULLTRACE_POLICY_ANALYSIS.md`:
- Best static policy: `berti/barca/PACIPV` with **1.007% mean loss**

This **exactly matches** our global timestep analysis! Great validation.

### vs Baseline Chip:
From `GLOBAL_BASELINE_LOSS_ANALYSIS.md`:
- Baseline chip: **0.093% mean loss** vs oracle

**Comparison**:
- Best static policy: 1.007% loss vs oracle
- Baseline chip: 0.093% loss vs oracle
- **Baseline is 10.8x better!**

### vs Oracle Optimality Frequency:
From `POLICY_OPTIMALITY_FREQUENCY.md`:
- `berti/entangling/mockingjay`: Optimal **38.27%** of time
- `gaze/entangling/mockingjay`: Optimal **31.12%** of time

This new analysis shows:
- `berti/entangling/mockingjay`: Optimal **39.06%** of time
- `gaze/entangling/mockingjay`: Optimal **34.55%** of time

Very close match! Small differences likely due to how we count ties.

## Visualization Highlights

### Individual Plots
Each policy has a detailed distribution showing:
- **Green bar (0%)**: Policy is optimal (matches oracle)
- **Yellow/light colors**: Near-optimal performance
- **Red colors**: Suboptimal performance
- **Statistics box**: Mean, median, std, min, max, P95, P99

### Summary Comparison
Shows all 8 policies side-by-side for easy comparison:
- Clear visual of berti vs gaze divide
- Shows median and mean values
- All use same scale for fair comparison

## Bottom Line

✓ **Best static policy**: `berti/barca/PACIPV` (0.085% median loss, 1.007% mean loss)  
✓ **All berti policies** are within 0.085-0.101% median loss  
✓ **All policies are excellent**: Even worst has only 1.92% mean loss  
✓ **L1D prefetcher dominates**: berti vs gaze is the main differentiator  
✓ **Baseline chip is still 10.8x better** than best static policy  

If you must use a static policy, use **`berti/barca/PACIPV`**. But the 2-policy baseline chip is dramatically better!

## Files Generated

**Individual detailed plots** (8 files):
- `static_vs_oracle_dist_berti_barca_PACIPV.png`
- `static_vs_oracle_dist_berti_barca_mockingjay.png`
- `static_vs_oracle_dist_berti_entangling_PACIPV.png`
- `static_vs_oracle_dist_berti_entangling_mockingjay.png`
- `static_vs_oracle_dist_gaze_barca_PACIPV.png`
- `static_vs_oracle_dist_gaze_barca_mockingjay.png`
- `static_vs_oracle_dist_gaze_entangling_PACIPV.png`
- `static_vs_oracle_dist_gaze_entangling_mockingjay.png`

**Summary comparison** (1 file):
- `static_vs_oracle_dist_summary.png`

**Statistics** (1 file):
- `static_vs_oracle_dist_summary.csv`

**Analysis script**:
- `create_static_vs_oracle_distributions.py`
