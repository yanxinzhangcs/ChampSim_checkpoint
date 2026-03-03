# Understanding Loss Semantics: Static Policy vs Baseline vs Oracle

## The Question

Why is IPC loss **sometimes negative** when comparing static policies vs baseline, but was **always positive or zero** when comparing vs oracle?

## Short Answer

**Negative loss = The static policy is BETTER than the baseline at that timestep.**

This is semantically correct! The baseline chip can only choose between TWO policies, so sometimes other policies outperform it.

## Detailed Explanation

### Reference Point Matters

#### 1. **Static Policy vs Oracle (Previous Analysis)**

```python
loss = (oracle_ipc - policy_ipc) / oracle_ipc * 100
```

- **Oracle IPC**: The BEST possible IPC (best of all 8 policies)
- **Result**: Loss is always ≥ 0
- **Why**: Oracle is the maximum by definition, so `oracle_ipc >= policy_ipc` always

**Example**:
```
Oracle IPC:  1.60 (berti/barca/PACIPV is best)
Policy IPC:  1.50 (berti/entangling/mockingjay)
Loss:        (1.60 - 1.50) / 1.60 * 100 = 6.25%
```

#### 2. **Static Policy vs Baseline (New Analysis)**

```python
loss = (baseline_ipc - policy_ipc) / baseline_ipc * 100
```

- **Baseline IPC**: The best of only TWO policies:
  - `berti/entangling/mockingjay`
  - `gaze/entangling/mockingjay`
- **Result**: Loss CAN be negative
- **Why**: Other policies might beat both baseline options

**Example** (negative loss):
```
Baseline choices:
  - berti/entangling/mockingjay: IPC = 1.50
  - gaze/entangling/mockingjay:  IPC = 1.40
  
Baseline selects: 1.50 (berti/entangling/mockingjay)

But berti/barca/PACIPV: IPC = 1.60

Loss for berti/barca/PACIPV:
  (1.50 - 1.60) / 1.50 * 100 = -6.67%
  
Negative! This policy BEATS the baseline!
```

## Interpretation Guide

### For Oracle Comparison (Previous Analysis)
- **Loss = 0%**: Policy is optimal (matches oracle)
- **Loss > 0%**: Policy is suboptimal
- **Loss < 0%**: IMPOSSIBLE (oracle is always best)

### For Baseline Comparison (New Analysis)
- **Loss = 0%**: Policy matches baseline performance
- **Loss > 0%**: Policy is WORSE than baseline
- **Loss < 0%**: Policy is BETTER than baseline ← **This is new!**

## Real Data Examples

From the actual analysis, here are the minimum losses (most negative = best cases where static beats baseline):

| Policy | Min Loss vs Baseline | Meaning |
|--------|---------------------|---------|
| `berti/barca/PACIPV` | **-9.82%** | Sometimes beats baseline by ~10%! |
| `berti/barca/mockingjay` | **-9.82%** | Sometimes beats baseline by ~10%! |
| `gaze/barca/mockingjay` | **-7.58%** | Sometimes beats baseline by ~8%! |
| `gaze/barca/PACIPV` | **-7.27%** | Sometimes beats baseline by ~7%! |
| `gaze/entangling/PACIPV` | **-6.48%** | Sometimes beats baseline by ~6%! |
| `berti/entangling/PACIPV` | **-4.05%** | Sometimes beats baseline by ~4%! |

## Why This Happens

The baseline chip is **constrained** to only two policies. At any timestep:

**Baseline's view**:
```
Option A: berti/entangling/mockingjay
Option B: gaze/entangling/mockingjay
Choose: max(A, B)
```

**Reality (all 8 policies)**:
```
Sometimes: berti/barca/PACIPV > max(A, B)
```

When this happens, the restricted baseline chip makes a **suboptimal choice** compared to having access to all policies. The negative loss captures this.

## Key Insight

**The baseline chip is better than any SINGLE static policy overall, but sometimes individual static policies can beat it at specific timesteps.**

From the analysis:
- **Baseline median loss vs oracle**: 0.093%
- **Best static policy median loss vs baseline**: 0.761%
- But best static policy **min loss vs baseline**: -4.05% (can beat it!)

This shows:
- On **average**: Baseline >> any static policy ✓
- At **some timesteps**: Specific static policies > baseline ✓

## Conclusion

✅ **No bug** - the semantics are correct!

✅ Negative loss = static policy outperforms baseline at that timestep

✅ This is expected because baseline is limited to 2 out of 8 policies

✅ Despite occasional losses, baseline still wins overall (much better average/median performance)
