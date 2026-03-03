import pandas as pd
import numpy as np
import re

# Read the CSV file
df = pd.read_csv('policy_ipc_table.csv')

print("="*100)
print("CALCULATING IMPROVEMENT HEADROOM FOR DYNAMIC POLICY SWITCHING")
print("="*100)

# Function to parse the multiline cell content
def parse_cell(cell_content):
    """Parse a cell containing multiline IPC data."""
    if pd.isna(cell_content):
        return None, None, {}
    
    lines = cell_content.strip().split('\n')
    policy_dict = {}
    best_policy = None
    best_ipc = None
    
    for line in lines:
        if line.startswith('BEST:'):
            match = re.search(r'BEST: (.+?) \(IPC=([\d.]+)\)', line)
            if match:
                best_policy = match.group(1)
                best_ipc = float(match.group(2))
        else:
            parts = line.split(': ')
            if len(parts) == 2:
                policy_name = parts[0].strip()
                try:
                    ipc_value = float(parts[1].strip())
                    policy_dict[policy_name] = ipc_value
                except ValueError:
                    pass
    
    return best_policy, best_ipc, policy_dict

# Identify the best static policy from the CURRENT data (min median loss vs oracle).
print("\nCollecting loss distributions for all static policies vs oracle...")

benchmarks = [col for col in df.columns if col != 'step']
policy_losses = {}

for benchmark in benchmarks:
    for _, row in df.iterrows():
        cell_content = row[benchmark]
        best_policy, best_ipc, policy_dict = parse_cell(cell_content)

        if best_policy is None or not policy_dict:
            continue

        for policy, ipc in policy_dict.items():
            loss_pct = ((best_ipc - ipc) / best_ipc) * 100 if best_ipc > 0 else 0
            policy_losses.setdefault(policy, []).append(loss_pct)

if not policy_losses:
    print("ERROR: No valid data found in policy_ipc_table.csv")
    raise SystemExit(1)

# Best static policy = lowest median loss vs oracle.
best_static_policy, losses = min(policy_losses.items(), key=lambda kv: np.median(kv[1]))
best_static_policy_short = best_static_policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')

print(f"\nBest Static Policy (by median loss vs oracle): {best_static_policy}")
print(f"                                         aka: {best_static_policy_short}")
print(f"Collected {len(losses)} timesteps (expected ~{len(benchmarks)}*{len(df)}={len(benchmarks)*len(df)})")

# Calculate statistics
print("\n" + "="*100)
print("BASELINE POLICY STATISTICS")
print("="*100)
print(f"Mean loss:       {np.mean(losses):.4f}%")
print(f"Median loss:     {np.median(losses):.4f}%")
print(f"Std deviation:   {np.std(losses):.4f}%")
print(f"Max loss:        {np.max(losses):.4f}%")

# Calculate improvement headroom
print("\n" + "="*100)
print("IMPROVEMENT HEADROOM: Perfect Dynamic Switching vs Best Static Policy")
print("="*100)
print("\nThe BEST case improvement a perfect mechanism that dynamically changes")
print("policies would achieve, considering the baseline policy as berti/barca/PACIPV:\n")

thresholds = [0.5, 1.0, 2.0, 5.0, 10.0]
results = []

for threshold in thresholds:
    count = sum(1 for l in losses if l >= threshold)
    percentage = 100 * count / len(losses)
    results.append({
        'threshold': threshold,
        'count': count,
        'percentage': percentage
    })
    print(f"To get {threshold:>4.1f}% or more improvement: {percentage:>5.2f}% of timesteps (n={count})")

# Also show the inverse - what percentage have loss BELOW thresholds
print("\n" + "="*100)
print("COMPLEMENTARY VIEW: How often is the static policy already good enough?")
print("="*100)
print()

for threshold in thresholds:
    count = sum(1 for l in losses if l < threshold)
    percentage = 100 * count / len(losses)
    print(f"Loss already < {threshold:>4.1f}%: {percentage:>5.2f}% of timesteps (n={count})")

# Detailed breakdown by ranges
print("\n" + "="*100)
print("DETAILED LOSS DISTRIBUTION")
print("="*100)
print()

ranges = [
    (0, 0.001, "0% (Optimal - no improvement possible)"),
    (0.001, 0.1, "0-0.1% (minimal improvement possible)"),
    (0.1, 0.5, "0.1-0.5% (small improvement possible)"),
    (0.5, 1.0, "0.5-1% (moderate improvement possible)"),
    (1.0, 2.0, "1-2% (significant improvement possible)"),
    (2.0, 5.0, "2-5% (large improvement possible)"),
    (5.0, 10.0, "5-10% (very large improvement possible)"),
    (10.0, float('inf'), ">10% (huge improvement possible)")
]

for low, high, label in ranges:
    if high == float('inf'):
        count = sum(1 for l in losses if l >= low)
    else:
        count = sum(1 for l in losses if low <= l < high)
    percentage = 100 * count / len(losses)
    print(f"{label:50s}: {percentage:>5.2f}% of timesteps (n={count})")

# Save results to file
results_df = pd.DataFrame(results)
results_df.insert(0, 'baseline_policy', best_static_policy)
results_df.insert(1, 'baseline_policy_short', best_static_policy_short)
results_df.to_csv('improvement_headroom_analysis.csv', index=False)
print("\n" + "="*100)
print("Saved: improvement_headroom_analysis.csv")
print("="*100)

# Create a formatted statement
print("\n" + "="*100)
print("FORMATTED STATEMENT FOR PAPER/PRESENTATION")
print("="*100)
print()
print("The BEST case improvement a perfect mechanism that dynamically changes")
print("policies would achieve, considering the baseline policy as berti/barca/PACIPV:")
print()
for threshold in [0.5, 1.0, 2.0, 5.0]:
    pct = [r['percentage'] for r in results if r['threshold'] == threshold][0]
    print(f"  • To get {threshold:.1f}% or more improvement: {pct:.2f}% of timesteps")
print()
print(f"(Based on {len(losses)} timesteps across {len(benchmarks)} benchmarks)")
print("="*100)
