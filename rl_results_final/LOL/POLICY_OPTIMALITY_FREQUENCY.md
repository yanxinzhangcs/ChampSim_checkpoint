# Policy Optimality Frequency Analysis

## Question
**What fraction of all time steps (across all applications) is each policy the optimal choice?**

## Results Summary

Analyzed **4,900 total time steps** (49 benchmarks × 100 steps each)

### Overall Policy Rankings

| Rank | Policy | Times Optimal | Percentage |
|------|--------|---------------|------------|
| 1 | **berti/entangling/mockingjay** | 1,875 | **38.27%** |
| 2 | **gaze/entangling/mockingjay** | 1,525 | **31.12%** |
| 3 | berti/entangling/PACIPV | 368 | 7.51% |
| 4 | gaze/entangling/PACIPV | 361 | 7.37% |
| 5 | berti/barca/mockingjay | 359 | 7.33% |
| 6 | gaze/barca/mockingjay | 323 | 6.59% |
| 7 | berti/barca/PACIPV | 46 | 0.94% |
| 8 | gaze/barca/PACIPV | 43 | 0.88% |

### Key Findings

**Top 2 policies dominate:**
- `berti/entangling/mockingjay` + `gaze/entangling/mockingjay` = **69.39%** of all time steps
- These two alone cover nearly 70% of optimal configurations!

**Bottom tier is rare:**
- `barca/PACIPV` combinations (both berti and gaze) account for only **1.82%** combined
- Rarely the optimal choice

## Component-Level Analysis

### L1D Prefetcher Impact

| Component | Optimal Frequency | Ratio |
|-----------|------------------|-------|
| **berti** | 54.04% | 1.18x |
| **gaze** | 45.96% | baseline |

**Insight**: `berti` is modestly more frequently optimal (1.18x), but `gaze` is still optimal 46% of the time - significant presence!

### L1I Prefetcher Impact ⭐ **DOMINANT FACTOR**

| Component | Optimal Frequency | Ratio |
|-----------|------------------|-------|
| **entangling** | 84.27% | **5.36x** |
| **barca** | 15.73% | baseline |

**Critical Insight**: `entangling` L1I prefetcher is optimal **5.36x more often** than `barca`! This is the most important component choice.

### L2C Replacement Impact ⭐ **SECOND MOST IMPORTANT**

| Component | Optimal Frequency | Ratio |
|-----------|------------------|-------|
| **mockingjay** | 83.31% | **4.99x** |
| **PACIPV** | 16.69% | baseline |

**Critical Insight**: `mockingjay` is optimal **4.99x more often** than `PACIPV`! Also a very important component.

## Comparison with Earlier Findings

### Interesting Contradiction!

**From average loss analysis:**
- Best universal static policy: `berti/barca/PACIPV`
- Why? Lowest average loss (1.007%)

**From optimality frequency analysis:**
- Most frequently optimal: `berti/entangling/mockingjay` (38.27%)
- `berti/barca/PACIPV` is optimal only 0.94% of the time!

### Resolution of Contradiction

**`berti/barca/PACIPV` has low average loss because:**
- When it's not optimal, it's **close** to optimal (low loss)
- Safe, consistent "runner-up" performance
- Best for risk-averse single static choice

**`berti/entangling/mockingjay` is frequently optimal because:**
- When workload suits it, it's the **best** (optimal 38% of time)
- But when workload doesn't suit it, performance degrades more
- Best for oracle/dynamic switching scenarios

## Strategic Implications

### For Static Policy Deployment

**If you can only pick ONE static policy for ALL workloads:**
- Choose: `berti/barca/PACIPV`
- Reason: Lowest average loss, most consistent
- You'll rarely be optimal, but you'll rarely be terrible

### For Dynamic Policy Switching

**If you can switch policies dynamically:**
- Primary targets: `berti/entangling/mockingjay` (38%) + `gaze/entangling/mockingjay` (31%)
- These two cover **69%** of optimal cases
- Adding `berti/entangling/PACIPV` (7.5%) gets you to **77%** coverage

**Three-policy dynamic switcher would cover 77% of optimal choices!**

### Component Priority for Tuning

**Ranked by impact:**

1. **L1I Prefetcher: entangling vs barca** (5.36x difference)
   - Most critical choice
   - Getting this right matters most

2. **L2C Replacement: mockingjay vs PACIPV** (4.99x difference)
   - Second most critical
   - Nearly as important as L1I

3. **L1D Prefetcher: berti vs gaze** (1.18x difference)
   - Least critical for optimality frequency
   - BUT: Still matters for worst-case/variance (from earlier analyses)

## Bottom Line

**Optimality is concentrated:**
- 2 policies account for 69% of optimal time steps
- 3 policies account for 77% of optimal time steps
- Top 4 policies account for 84% of optimal time steps

**Component hierarchy:**
1. L1I prefetcher choice matters most (5.36x)
2. L2C replacement matters second (4.99x)
3. L1D prefetcher matters least for frequency (1.18x), but matters for variance/risk

**Practical recommendation:**
- **Static**: Use `berti/barca/PACIPV` for safety
- **Dynamic (2-way)**: Switch between `berti/entangling/mockingjay` ↔ `gaze/entangling/mockingjay` (69% coverage)
- **Dynamic (3-way)**: Add `berti/entangling/PACIPV` (77% coverage)

## Files Generated

- `policy_optimality_frequency.png` - Pie chart and bar chart visualization
- `policy_optimality_frequency.csv` - Complete statistics
