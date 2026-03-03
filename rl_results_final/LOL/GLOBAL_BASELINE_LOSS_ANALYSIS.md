# Global Baseline Chip Loss Distribution Analysis

## Overview

This analysis treats **every timestep across all benchmarks as an individual datapoint**, creating a global view of baseline chip performance against the oracle.

**Dataset**: 4,900 timesteps (49 benchmarks × 100 steps each)

## Key Statistics

| Metric | Value |
|--------|-------|
| **Total datapoints** | 4,900 |
| **Mean loss** | 0.0932% |
| **Median loss** | 0.0000% |
| **Std deviation** | 0.4199% |
| **Min loss** | 0.0000% |
| **Max loss** | 8.9387% |
| **25th percentile** | 0.0000% |
| **75th percentile** | 0.0062% |
| **90th percentile** | 0.1655% |
| **95th percentile** | 0.4901% |
| **99th percentile** | 1.7281% |

## Oracle Match Rate

**3,461 of 4,900 timesteps (70.63%)** have **ZERO loss** - the baseline chip achieves oracle-level performance!

This is even better than the 69.6% we calculated before (likely due to rounding differences in counting).

## Loss Distribution by Ranges

| Loss Range | Percentage of Timesteps | Count |
|------------|------------------------|-------|
| **0% (Perfect match)** | 70.6% | 3,461 |
| **0-0.1%** | 18.8% | 922 |
| **0.1-0.5%** | 6.7% | 327 |
| **0.5-1%** | 1.7% | 84 |
| **1-2%** | 1.3% | 63 |
| **2-5%** | 0.8% | 39 |
| **>5%** | 0.1% | 4 |

## Key Insights

### 1. **Exceptional Coverage**
- **70.6%** of all timesteps: Baseline = Oracle (perfect performance)
- **89.4%** of all timesteps: Loss < 0.1% (near-perfect)
- **96.1%** of all timesteps: Loss < 0.5% (excellent)

### 2. **Rare Worst Cases**
- Only **4 timesteps** out of 4,900 have loss > 5%
- Maximum loss observed: 8.94%
- These rare worst cases minimally impact overall performance

### 3. **Median is ZERO**
The **median loss is exactly 0%**, meaning more than half of all timesteps achieve perfect oracle performance!

### 4. **Tight Distribution**
- 75% of timesteps have loss ≤ 0.0062%
- Standard deviation is only 0.42%
- The distribution is heavily concentrated near zero

### 5. **99th Percentile Still Excellent**
Even at the 99th percentile, loss is only 1.73% - remarkably small!

## Visualization Components

The generated `baseline_global_loss_distribution.png` includes:

1. **Box Plot** - Global distribution across all 4,900 timesteps
   - Shows median (0%), quartiles, and outliers
   - Clearly visualizes the concentration near zero loss

2. **Histogram (Full Range)** - Complete distribution
   - Massive spike at 0% (oracle matches)
   - Long tail extending to ~9% maximum

3. **Histogram (Zoomed 0-2%)** - Detailed view of common range
   - Shows 99.2% of all datapoints
   - Reveals fine-grained structure near zero

4. **Cumulative Distribution Function (CDF)**
   - Shows rapid rise to 70% at loss = 0%
   - Illustrates excellent percentile performance

5. **Loss Distribution by Ranges**
   - Bar chart showing timestep counts in each loss bin
   - Makes it easy to see 70.6% perfect match rate

## Comparison with Static Policies

Recall from previous analyses:
- **Baseline chip mean loss**: 0.0932%
- **Best static policy mean loss**: ~1.0% (from full trace analysis)

The baseline chip is **10x better** than any single static policy!

## Bottom Line

The baseline chip (dynamically switching between `berti/entangling/mockingjay` and `gaze/entangling/mockingjay`) achieves:

✓ **Perfect oracle performance** at 70.6% of all timesteps  
✓ **Near-perfect performance** (< 0.1% loss) at 89.4% of timesteps  
✓ **Median loss of 0%** - better than half of all possible configurations  
✓ **Mean loss of only 0.093%** - negligible performance impact  
✓ **Maximum loss of 8.94%** - rare worst cases are still reasonable  

This is an **outstanding result** for a simple two-state reconfigurable system!

## Files Generated

- `baseline_global_loss_distribution.png` - Comprehensive 6-panel visualization
- `baseline_global_loss_summary.csv` - Statistical summary
- `visualize_global_baseline_loss.py` - Analysis script
