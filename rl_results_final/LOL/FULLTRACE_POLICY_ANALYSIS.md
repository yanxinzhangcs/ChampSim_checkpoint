# Full-Trace IPC Policy Analysis

## Overview

Analysis of **full-trace IPC data** - each benchmark has ONE IPC value per policy (total application runtime), not broken down by time steps.

**Dataset:** 46 benchmarks × 8 policies = 368 data points

## Results: Policy Performance Rankings

### Box Plot Statistics (Median Loss %)

Ranked from **best to worst**:

| Rank | Policy | Median Loss | Mean Loss | Max Loss |
|------|--------|-------------|-----------|----------|
| 1 | **gaze/entangling/mockingjay** | **0.042%** | 0.929% | 14.041% |
| 2 | **berti/entangling/mockingjay** | 0.232% | 1.431% | 9.906% |
| 3 | gaze/barca/mockingjay | 0.230% | 1.195% | 14.045% |
| 4 | berti/entangling/PACIPV | 0.250% | 1.382% | 9.933% |
| 5 | gaze/entangling/PACIPV | 0.271% | 1.082% | 14.182% |
| 6 | gaze/barca/PACIPV | 0.502% | 1.303% | 14.203% |
| 7 | berti/barca/PACIPV | 0.688% | 1.612% | 9.933% |
| 8 | berti/barca/mockingjay | 0.696% | 1.611% | 9.906% |

## Component-Level Analysis

### L1D Prefetcher

| Component | Median Loss | Mean Loss |
|-----------|-------------|-----------|
| **gaze** | **0.235%** | 1.127% |
| **berti** | 0.465% | 1.509% |

**⚠️ SURPRISE:** `gaze` is better for full-trace performance! (Opposite of per-timestep analysis)

### L1I Prefetcher

| Component | Median Loss | Mean Loss |
|-----------|-------------|-----------|
| **entangling** | **0.182%** | 1.206% |
| **barca** | 0.477% | 1.430% |

**✓ CONSISTENT:** `entangling` is better (same as per-timestep)

### L2C Replacement

| Component | Median Loss | Mean Loss |
|-----------|-------------|-----------|
| **mockingjay** | **0.206%** | 1.291% |
| **PACIPV** | 0.414% | 1.345% |

**✓ CONSISTENT:** `mockingjay` is better (same as per-timestep)

## Key Insights

### 1. Best Policy: gaze/entangling/mockingjay

**Full-trace performance:**
- Median loss: **0.042%** (excellent!)
- Only 0.929% mean loss
- Max loss: 14.041% (highest outlier)

**Why it wins here:**
- When looking at overall application performance, `gaze` L1D prefetcher performs better
- Suggests `gaze` might have higher peak benefits that offset its temporal variance

### 2. Interesting Contrast with Per-Timestep Analysis

**Per-timestep (optimality frequency):**
- Winner: `berti/entangling/mockingjay` (38.27% of time steps)
- Runner-up: `gaze/entangling/mockingjay` (31.12%)

**Full-trace (application-level):**
- Winner: `gaze/entangling/mockingjay` (0.042% median loss)
- Runner-up: `berti/entangling/mockingjay` (0.232%)

**Interpretation:**
- `berti` is more **frequently** optimal across time steps
- But `gaze` delivers better **overall** application performance
- This suggests `gaze` has higher performance **peaks** when it's good, even if less consistent

### 3. Component Hierarchy Changed!

**Per-timestep importance:**
1. L1I Prefetcher: entangling >> barca (5.36x frequency)
2. L2C Replacement: mockingjay >> PACIPV (4.99x frequency)
3. L1D Prefetcher: berti > gaze (1.18x frequency)

**Full-trace importance:**
1. L1I Prefetcher: entangling > barca (still best)
2. L2C Replacement: mockingjay > PACIPV (still good)
3. **L1D Prefetcher: gaze > berti** ⚠️ (REVERSED!)

### 4. Consistency vs. Peak Performance Trade-off

**berti policies:**
- Lower max losses (~10%)
- More predictable but higher median loss
- **Consistent performer**

**gaze policies:**
- Higher max losses (~14%)
- Lower median loss overall
- **High-risk, high-reward**

## Practical Implications

### For Overall Application Performance

**If you care about end-to-end IPC:**
- Deploy: **`gaze/entangling/mockingjay`**
- Median loss: only 0.042%
- Best overall performance

### For Predictability and Safety

**If you want bounded worst-case:**
- Deploy: `berti/entangling/mockingjay`
- Max loss: 9.906% (vs 14.041% for gaze)
- Median loss: 0.232% (still very good)

### Trade-off Summary

| Metric | gaze/entangling/mockingjay | berti/entangling/mockingjay |
|--------|---------------------------|----------------------------|
| **Median loss** | 0.042% ✅ | 0.232% |
| **Mean loss** | 0.929% ✅ | 1.431% |
| **Max loss** | 14.041% ⚠️ | 9.906% ✅ |
| **Risk profile** | High variance, best median | Low variance, good median |

## Why Results Differ from Per-Timestep Analysis

**Per-timestep analysis** measures:
- How often each policy is optimal at individual moments
- Temporal consistency and frequency

**Full-trace analysis** measures:
- Overall application performance
- Integrated impact across entire runtime

**gaze wins full-trace because:**
- When it's good, it's REALLY good (high peaks)
- These peaks contribute significantly to overall IPC
- Even though it's optimal less frequently in time, the magnitude of benefit is larger

**berti wins per-timestep because:**
- More consistently close to optimal
- Optimal more frequently across time steps
- But performance gains when optimal are smaller

## Recommendation Matrix

| Scenario | Best Choice | Reason |
|----------|-------------|--------|
| **Maximize overall IPC** | `gaze/entangling/mockingjay` | 0.042% median loss |
| **Minimize worst-case** | `berti/entangling/mockingjay` | 9.9% max vs 14% |
| **Balance both** | `berti/entangling/mockingjay` | Good median, bounded max |
| **Risk-tolerant** | `gaze/entangling/mockingjay` | Best median/mean |

## Files Generated

- `fulltrace_policy_boxplot.png` - Box plots of loss distributions
- `fulltrace_policy_statistics.csv` - Complete statistics
