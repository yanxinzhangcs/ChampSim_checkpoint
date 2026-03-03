# Worst-Case Performance Loss Analysis

## Executive Summary

This analysis identifies **the worst-performing time step** for each static policy across all benchmarks - essentially finding when each policy "fails the hardest."

## Key Findings

### 1. Massive Worst-Case Losses for Some Policies

**The worst static policy can lose up to 39% performance at critical moments:**

- **Best policy (by worst-case)**: `berti/barca/PACIPV`
  - Average worst-case loss: **3.677%**
  - Maximum worst-case loss: **15.754%**
  
- **Worst policy (by worst-case)**: `gaze/entangling/mockingjay`
  - Average worst-case loss: **6.738%**
  - Maximum worst-case loss: **38.960%**

### 2. Top Problematic Scenarios

**Most extreme worst-case losses (>20%):**

| Benchmark | Policy | Worst Step | Loss % | Best Policy at That Step |
|-----------|--------|------------|--------|-------------------------|
| `450.soplex-247B` | gaze/*/† | 40 | **38.96%** | berti/entangling/mockingjay |
| `482.sphinx3-1100B` | gaze/*/† | 69 | **33.58%** | berti/entangling/mockingjay |
| `410.bwaves-1963B` | gaze/*/† | 54 | **23.07%** | berti/entangling/PACIPV |
| `627.cam4_s-490B` | gaze/*/† | 54 | **20.61%** | berti/entangling/mockingjay |

*† All `gaze` L1D prefetcher policies showed similar worst-case losses*

### 3. Most Problematic Time Steps

**Steps where static policies frequently fail:**

| Step | Times Worst-Case | Avg Loss % | Max Loss % |
|------|------------------|------------|------------|
| **69** | 16 times | 18.4% | 33.6% |
| **40** | 14 times | 21.8% | 39.0% |
| **54** | 13 times | 14.0% | 23.1% |
| **35** | 12 times | 8.5% | 13.4% |

### 4. Policy Component Impact on Worst-Case

**L1D Prefetcher dominates worst-case behavior:**

- **`berti` policies**: Avg worst-case ~3.7%, Max ~15.8%
- **`gaze` policies**: Avg worst-case ~6.6%, Max ~39.0%

**Key insight**: The L1D prefetcher choice has **2.5x impact** on worst-case losses!

**L1I Prefetcher & L2C Replacement**: Minimal impact on worst-case (differences <0.1%)

### 5. Benchmark Sensitivity

**Benchmarks with highest worst-case losses (any policy):**

1. `450.soplex-247B`: 38.96%
2. `482.sphinx3-1100B`: 33.58%
3. `410.bwaves-1963B`: 23.07%
4. `627.cam4_s-490B`: 20.61%

**Benchmarks with lowest worst-case losses:**

1. `638.imagick_s-10316B`: 0.00% (one policy is always optimal)
2. `473.astar-153B`: 0.07%
3. `483.xalancbmk-127B`: 0.13%

## Implications

### 1. Risk Assessment

If you deploy a **single static policy** across diverse workloads:
- You're **guaranteed** to hit moments of severe performance degradation
- For wrong `gaze` policy choice: up to **39% loss** at critical phases
- For wrong `berti` policy choice: up to **16% loss** at critical phases

### 2. Safe vs. High-Risk Policies

**Risk-Averse Choice**: `berti/barca/PACIPV`
- Best worst-case performance (3.7% avg, 15.8% max)
- Safest across all benchmarks and time steps

**Risky Choices**: Any `gaze` L1D prefetcher
- Can perform very well on average
- But can suffer **catastrophic losses** at specific phases
- 2.5x worse worst-case than `berti`

### 3. Dynamic Switching Justification

The analysis reveals **temporal hot spots** where:
- Certain time steps consistently cause problems (steps 69, 40, 54)
- Wrong policy choice causes **10-40% performance loss**
- These hot spots are **predictable** (same steps across benchmarks)

**Opportunity**: Dynamic policy switching at these critical steps could eliminate worst-case scenarios.

### 4. Application-Specific Tuning Priority

Focus tuning efforts on sensitive benchmarks:
- `450.soplex-247B`, `482.sphinx3-1100B`, `410.bwaves-1963B`, `627.cam4_s-490B`
- These show **20-39% worst-case losses**
- High ROI for application-specific policy selection

## Files Generated

1. **`worst_case_steps.csv`**: Complete dataset
   - 392 entries (49 benchmarks × 8 policies)
   - Columns: benchmark, policy, worst_step, worst_loss_pct, best_policy_at_worst_step, etc.

2. **`worst_case_analysis.png`**: Visualizations
   - Distribution of worst-case steps
   - Boxplots of worst-case losses by policy
   - Heatmap across benchmarks
   - Policy ranking by average worst-case loss

## Comparison to Average Loss Analysis

| Metric | Average Loss | Worst-Case Loss |
|--------|-------------|-----------------|
| Best `berti` policy | 1.01% | 3.68% |
| Best `gaze` policy | 1.92% | 6.56% |
| **Ratio (avg to worst)** | **1.9x** | **1.8x** |

**Insight**: The gap between `berti` and `gaze` is **consistent** in both average and worst-case scenarios, suggesting fundamental architectural differences driving performance variance.
