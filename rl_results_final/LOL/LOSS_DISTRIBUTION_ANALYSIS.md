# Loss Distribution Box Plot Analysis

## Visualization Overview

Created box plot distributions showing **how performance loss varies across time steps** for each policy-benchmark combination.

**What each box plot shows:**
- One box plot per benchmark (49 total)
- Each box represents the distribution of loss percentages across ALL time steps
- Box elements: median (line), 25th-75th percentile (box), whiskers (range), outliers (dots)

## Key Findings

### 1. Temporal Variability Champions

**Benchmarks with HIGHEST loss variability across time** (measured by IQR):

| Benchmark | Avg IQR | Interpretation |
|-----------|---------|----------------|
| `644.nab_s-12459B` | 4.39% | **Highly phase-sensitive** - policy choice impact varies dramatically |
| `450.soplex-247B` | 4.07% | Extreme temporal variation |
| `470.lbm-1274B` | 2.39% | Significant phase behavior |
| `625.x264_s-12B` | 2.26% | Video codec shows phase variation |
| `607.cactuBSSN_s-2421B` | 2.26% | Scientific computing phases |

**Implication**: These benchmarks are **prime candidates for dynamic policy switching** - significant gains possible from phase-aware adaptation.

### 2. Stable Performers

**Benchmarks with LOWEST loss variability** (most consistent):

| Benchmark | Avg IQR | Interpretation |
|-----------|---------|----------------|
| `403.gcc-16B` | 0.01% | **Nearly phase-insensitive** - static policy works fine |
| `600.perlbench_s-1273B` | 0.07% | Very consistent behavior |
| `429.mcf-184B` | 0.11% | Memory-bound, consistent |

**Implication**: For these benchmarks, static policy is sufficient - minimal gains from dynamic switching.

### 3. Policy Consistency Ranking

**Policies by temporal consistency** (lowest std dev = most predictable):

1. `berti/barca/mockingjay` - 0.701% avg std dev
2. `berti/entangling/mockingjay` - 0.706%
3. `berti/barca/PACIPV` - 0.707%
4. `berti/entangling/PACIPV` - 0.712%
---
5. `gaze/barca/PACIPV` - 1.316% ⚠️ **1.9x MORE variable**
6. `gaze/entangling/PACIPV` - 1.323%
7. `gaze/barca/mockingjay` - 1.339%
8. `gaze/entangling/mockingjay` - 1.339%

**Key Insight**: `berti` policies are not only better on average, but also **more predictable** - nearly 2x less temporal variation than `gaze` policies.

## Visual Patterns Observed

### berti Policies (safer, more consistent)
- **Tighter boxes**: Lower temporal variability
- **Fewer outliers**: More predictable behavior
- **Lower median**: Better average performance
- **Smaller range**: Bounded performance loss

### gaze Policies (higher variance, riskier)
- **Wider boxes**: High temporal variability
- **Many outliers**: Unpredictable spikes
- **Higher median**: Worse average performance
- **Larger range**: Can swing wildly (0-39%)

## Actionable Insights

### For Workload Prioritization

**High-value targets for dynamic optimization:**
1. `nab_s`, `soplex`, `lbm`, `x264_s`, `cactuBSSN_s` (IQR > 2%)
   - Large temporal variation = large optimization opportunity

**Low-value targets (keep static policy):**
2. `gcc`, `perlbench_s`, `mcf`, `wrf_s` (IQR < 0.15%)
   - Minimal variation = minimal gains from dynamic switching

### For Risk Management

**If deploying unknown workload mix:**
- Choose `berti/barca/PACIPV` or `berti/barca/mockingjay`
- These have the **tightest loss distributions**
- Predictable, bounded performance impact

**Avoid for risk-averse scenarios:**
- Any `gaze` policy
- 2x higher variability
- Unpredictable outliers up to 39%

## Files Generated

1. **8 detailed box plot figures** (one per policy)
   - `loss_distribution_berti_barca_PACIPV.png`
   - `loss_distribution_berti_barca_mockingjay.png`
   - `loss_distribution_berti_entangling_PACIPV.png`
   - `loss_distribution_berti_entangling_mockingjay.png`
   - `loss_distribution_gaze_barca_PACIPV.png`
   - `loss_distribution_gaze_barca_mockingjay.png`
   - `loss_distribution_gaze_entangling_PACIPV.png`
   - `loss_distribution_gaze_entangling_mockingjay.png`

2. **Summary comparison figure**
   - `loss_distribution_summary.png` - All 8 policies side-by-side

3. **Statistical data**
   - `loss_distribution_statistics.csv` - Complete statistics for all combinations

## Bottom Line

**These box plots reveal:**
1. ✅ Some benchmarks are phase-insensitive (static policy fine)
2. ⚠️ But many show **4%+ IQR** - huge temporal variation
3. 🎯 Clear optimization targets identified
4. 📊 `berti` policies 2x more predictable than `gaze`
5. 🔧 Dynamic switching justified for high-IQR benchmarks
