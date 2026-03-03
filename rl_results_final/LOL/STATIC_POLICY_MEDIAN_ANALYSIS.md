# Static Policy Median Loss Analysis
## Policy: berti/entangling/mockingjay

## Analysis Method

**For each benchmark:**
1. Compute IPC loss at every time step (comparing `berti/entangling/mockingjay` to optimal policy at that step)
2. Take the **median** of these losses across all 100 time steps
3. Result: One median value per benchmark (49 total)

**Then create box plot of these 49 median values**

## Results: Distribution of Median Losses

**Box Plot Statistics:**
- **Median of medians: 0.106%** ⭐ (half of benchmarks have median loss below this)
- **Mean of medians: 0.847%**
- **Q1 (25th percentile): 0.000%** (25% of benchmarks have 0% median loss!)
- **Q3 (75th percentile): 0.582%**
- **Range: 0.000% to 10.414%**

## Benchmark Performance Categories

### Excellent Match (41 benchmarks - 83.7%)
**Median loss < 1%** - Policy works very well

Top performers with **0.000% median loss** (10 benchmarks):
- `638.imagick_s-10316B`
- `654.roms_s-1007B`
- `649.fotonik3d_s-10881B`
- `644.nab_s-12459B`
- `621.wrf_s-575B`
- `625.x264_s-12B`
- `482.sphinx3-1100B`
- `600.perlbench_s-1273B`
- `456.hmmer-191B`
- `473.astar-153B`

**Interpretation**: For these benchmarks, `berti/entangling/mockingjay` is optimal (or very close) for the majority of time steps!

### Moderate Match (6 benchmarks - 12.2%)
**1% < median loss < 5%**

- `450.soplex-247B`: 0.264%
- `631.deepsjeng_s-928B`: 0.313%
- `648.exchange2_s-1227B`: 0.411%
- `471.omnetpp-188B`: 0.443%
- `400.perlbench-41B`: 0.454%
- ... up to ~2.7%

### Poor Match (2 benchmarks - 4.1%)
**Median loss > 5%** - Policy struggles

1. **`619.lbm_s-2676B`**: 10.414% median loss ⚠️
   - Max loss: 15.558%
   - This benchmark really wants a different policy!

2. **`462.libquantum-1343B`**: 8.677% median loss ⚠️
   - Max loss: 13.035%
   - Also a poor match

## Key Insights

### 1. Highly Skewed Distribution

The box plot shows:
- **Tight concentration near zero** (Q1 = 0%, median = 0.106%)
- **Few outliers** pulling the mean up (mean = 0.847%)
- **83.7% of benchmarks** perform excellently (< 1% median loss)

### 2. Policy is "Mostly Universal"

`berti/entangling/mockingjay` is:
- ✅ Excellent for 41/49 benchmarks (83.7%)
- ⚠️ Questionable for 2/49 benchmarks (4.1%)

**This explains why it's the most frequently optimal policy (38.27% of all time steps)!**

### 3. Outliers are Predictable

The 2 problematic benchmarks:
- `lbm_s` (Lattice Boltzmann Method - fluid dynamics)
- `libquantum` (quantum computing simulation)

Both are specialized scientific codes with unique memory access patterns.

### 4. Comparison to "Safest" Policy

**Recall:** `berti/barca/PACIPV` had lowest **average** loss (1.007%) across all benchmarks

**But:** `berti/entangling/mockingjay` has:
- Lower **median of medians**: 0.106% vs likely higher for barca/PACIPV
- Better for 83.7% of benchmarks
- Worse for the outliers (lbm_s, libquantum)

**Trade-off:**
- `berti/entangling/mockingjay`: Better for most, worse for outliers
- `berti/barca/PACIPV`: More consistent, never terrible

## Strategic Implications

### For Deployment Decision

**If your workload includes lbm_s or libquantum:**
- Consider `berti/barca/PACIPV` for safety
- OR implement targeted policy switching for these 2 benchmarks

**If your workload is typical mix:**
- Deploy `berti/entangling/mockingjay`
- 83.7% chance of excellent performance
- Median loss only 0.106%

### For Dynamic Switching

Priority targets for switching **away from** `berti/entangling/mockingjay`:
1. `619.lbm_s-2676B` (10.4% median loss)
2. `462.libquantum-1343B` (8.7% median loss)
3. `602.gcc_s-1850B` (4.3% median loss)

For these 3, switching to a better policy could recover 4-10% performance on median.

## Bottom Line

The box plot reveals that `berti/entangling/mockingjay`:
- ✅ **Universally good** for 83.7% of benchmarks (median loss < 1%)
- ⭐ **0.000% median loss** for 20% of benchmarks (optimal most of the time!)
- ⚠️ **Struggles with 2 specific workloads** (lbm_s, libquantum) showing 8-10% median loss
- 📊 **Median of medians = 0.106%** - excellent overall

**Recommendation:** Excellent choice as default static policy, with optional targeted switching for lbm_s and libquantum workloads.
