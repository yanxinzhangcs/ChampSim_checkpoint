import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re

# Read the CSV file
df = pd.read_csv('policy_ipc_table.csv')

# Define the two baseline policies
BASELINE_POLICIES = [
    'l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay',
    'l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay'
]

print("Baseline chip can dynamically choose between:")
for pol in BASELINE_POLICIES:
    short_name = pol.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    print(f"  - {short_name}")

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
                    pass  # Skip lines that don't have valid float values
    
    return best_policy, best_ipc, policy_dict


def collect_policy_vs_baseline_losses(df):
    """
    For each timestep and benchmark:
    - Calculate baseline IPC (best of two baseline policies)
    - For each policy, calculate loss vs baseline
    """
    benchmarks = [col for col in df.columns if col != 'step']
    
    # Dictionary to store: policy -> benchmark -> list of losses (vs baseline)
    policy_benchmark_losses = {}
    
    # Also track baseline statistics
    baseline_stats = {
        'vs_oracle_losses': [],  # Baseline vs oracle
        'benchmarks_perfect': 0,  # Count where baseline = oracle
        'total_steps': 0
    }
    
    for benchmark in benchmarks:
        for idx, row in df.iterrows():
            cell_content = row[benchmark]
            best_policy, best_ipc, policy_dict = parse_cell(cell_content)
            
            if best_policy is None or not policy_dict:
                continue
            
            # Calculate baseline IPC (best of the two baseline policies)
            baseline_ipcs = [policy_dict.get(p, 0) for p in BASELINE_POLICIES if p in policy_dict]
            if not baseline_ipcs:
                continue
            
            baseline_ipc = max(baseline_ipcs)
            
            # Track baseline vs oracle
            baseline_stats['total_steps'] += 1
            if baseline_ipc == best_ipc:
                baseline_stats['benchmarks_perfect'] += 1
            baseline_loss_pct = ((best_ipc - baseline_ipc) / best_ipc) * 100 if best_ipc > 0 else 0
            baseline_stats['vs_oracle_losses'].append(baseline_loss_pct)
            
            # For each policy, calculate loss vs baseline
            for policy, ipc in policy_dict.items():
                # Calculate loss percentage: how much worse is this policy vs baseline?
                if baseline_ipc > 0:
                    loss_pct = ((baseline_ipc - ipc) / baseline_ipc) * 100
                else:
                    loss_pct = 0
                
                if policy not in policy_benchmark_losses:
                    policy_benchmark_losses[policy] = {}
                if benchmark not in policy_benchmark_losses[policy]:
                    policy_benchmark_losses[policy][benchmark] = []
                
                policy_benchmark_losses[policy][benchmark].append(loss_pct)
    
    return policy_benchmark_losses, benchmarks, baseline_stats


print("\nCollecting loss distributions vs baseline...")
policy_benchmark_losses, benchmarks, baseline_stats = collect_policy_vs_baseline_losses(df)
all_policies = sorted(policy_benchmark_losses.keys())

print(f"\nCollected data for {len(all_policies)} policies and {len(benchmarks)} benchmarks")
print(f"Total time steps analyzed: {baseline_stats['total_steps']}")

if baseline_stats['total_steps'] > 0:
    print(f"Time steps where baseline = oracle: {baseline_stats['benchmarks_perfect']} ({100*baseline_stats['benchmarks_perfect']/baseline_stats['total_steps']:.1f}%)")
    print(f"Mean baseline vs oracle loss: {np.mean(baseline_stats['vs_oracle_losses']):.3f}%")
else:
    print("WARNING: No data was found! Check the data format.")
    exit(1)

# Create summary comparison figure (all policies in one view)
print("\nCreating summary comparison figure...")
fig, axes = plt.subplots(2, 4, figsize=(28, 12))
fig.suptitle('IPC Loss vs Baseline Chip (berti|gaze / entangling / mockingjay)\n' + 
             'Baseline can dynamically choose between two policies. Negative = worse than baseline.',
             fontsize=16, fontweight='bold')

for idx, (ax, policy) in enumerate(zip(axes.flat, all_policies)):
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    
    # Prepare data
    box_data = []
    for benchmark in benchmarks:
        if benchmark in policy_benchmark_losses[policy]:
            losses = policy_benchmark_losses[policy][benchmark]
            box_data.append(losses)
    
    # Create box plot (simplified - just show distribution across all benchmarks)
    bp = ax.boxplot(box_data, patch_artist=True, showfliers=False, widths=0.4)
    
    # Color based on whether this is a baseline policy
    if policy in BASELINE_POLICIES:
        color = 'lightgreen'
        alpha = 0.8
    else:
        color = 'lightcoral'
        alpha = 0.6
    
    for patch in bp['boxes']:
        patch.set_facecolor(color)
        patch.set_alpha(alpha)
    
    ax.set_title(policy_short, fontsize=10, fontweight='bold')
    ax.set_ylabel('Loss vs Baseline (%)', fontsize=9)
    ax.set_xlabel('Benchmarks', fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    ax.set_xticklabels([])  # Remove x-tick labels for cleaner look
    
    # Add horizontal line at y=0 (baseline performance)
    ax.axhline(y=0, color='green', linestyle='-', linewidth=2, alpha=0.7, label='Baseline')
    
    # Add statistics
    all_losses = [loss for losses in box_data for loss in losses]
    median_loss = np.median(all_losses)
    mean_loss = np.mean(all_losses)
    
    # Determine color based on performance
    if median_loss < -0.5:
        box_color = 'red'
    elif median_loss < 0.1:
        box_color = 'yellow'
    else:
        box_color = 'lightgreen'
    
    ax.text(0.98, 0.95, f'Med: {median_loss:.2f}%\nMean: {mean_loss:.2f}%', 
            transform=ax.transAxes,
            ha='right', va='top', fontsize=8, 
            bbox=dict(boxstyle='round', facecolor=box_color, alpha=0.5))

plt.tight_layout()
plt.savefig('policies_vs_baseline_summary.png', dpi=200, bbox_inches='tight')
print("Saved: policies_vs_baseline_summary.png")

# Create ONE detailed figure per policy with per-benchmark breakdown
print("\nCreating detailed per-policy box plots...")
for policy_idx, policy in enumerate(all_policies, 1):
    print(f"[{policy_idx}/{len(all_policies)}] Creating detailed boxplot for {policy}...")
    
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    
    # Prepare data for box plot
    box_data = []
    box_labels = []
    
    for benchmark in benchmarks:
        if benchmark in policy_benchmark_losses[policy]:
            losses = policy_benchmark_losses[policy][benchmark]
            box_data.append(losses)
            # Shorten benchmark name for display
            label = benchmark.split('-')[0][:20]
            box_labels.append(label)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(24, 8))
    
    # Create box plot
    bp = ax.boxplot(box_data, labels=box_labels, patch_artist=True, 
                    showfliers=True, widths=0.6)
    
    # Color the boxes
    if policy in BASELINE_POLICIES:
        box_color = 'lightgreen'
        alpha = 0.8
    else:
        box_color = 'lightcoral'
        alpha = 0.7
    
    for patch in bp['boxes']:
        patch.set_facecolor(box_color)
        patch.set_alpha(alpha)
    
    # Styling
    ax.set_xlabel('Benchmark', fontsize=12, fontweight='bold')
    ax.set_ylabel('IPC Loss vs Baseline (%)', fontsize=12, fontweight='bold')
    
    is_baseline = " [BASELINE POLICY]" if policy in BASELINE_POLICIES else ""
    ax.set_title(f'IPC Loss vs Baseline Chip Across Time Steps\nPolicy: {policy_short}{is_baseline}', 
                 fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # Rotate x-axis labels
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=90, ha='right', fontsize=8)
    
    # Add horizontal line at y=0 (baseline performance)
    ax.axhline(y=0, color='green', linestyle='-', linewidth=2, alpha=0.7, label='Baseline Performance')
    ax.legend(loc='upper right')
    
    # Add statistics text
    all_losses = [loss for losses in box_data for loss in losses]
    stats_text = f'Overall: Median={np.median(all_losses):.2f}%, Mean={np.mean(all_losses):.2f}%, Min={np.min(all_losses):.2f}%, Max={np.max(all_losses):.2f}%'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            fontsize=10)
    
    plt.tight_layout()
    
    # Save with safe filename
    filename = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '_').replace('_l2c_replacement-', '_')
    plt.savefig(f'policy_vs_baseline_{filename}.png', dpi=200, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: policy_vs_baseline_{filename}.png")

# Create aggregate statistics DataFrame
print("\nCreating aggregate statistics...")
stats_data = []

for policy in all_policies:
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    
    for benchmark in benchmarks:
        if benchmark in policy_benchmark_losses[policy]:
            losses = policy_benchmark_losses[policy][benchmark]
            
            stats_data.append({
                'policy': policy_short,
                'is_baseline_policy': policy in BASELINE_POLICIES,
                'benchmark': benchmark,
                'median_loss_vs_baseline': np.median(losses),
                'mean_loss_vs_baseline': np.mean(losses),
                'std_loss': np.std(losses),
                'min_loss': np.min(losses),
                'max_loss': np.max(losses),
                'q25_loss': np.percentile(losses, 25),
                'q75_loss': np.percentile(losses, 75),
                'iqr_loss': np.percentile(losses, 75) - np.percentile(losses, 25),
                'num_steps': len(losses),
                'pct_worse_than_baseline': 100 * sum(1 for l in losses if l < 0) / len(losses),
                'pct_equal_to_baseline': 100 * sum(1 for l in losses if abs(l) < 0.001) / len(losses),
                'pct_better_than_baseline': 100 * sum(1 for l in losses if l > 0.001) / len(losses)
            })

stats_df = pd.DataFrame(stats_data)
stats_df.to_csv('policies_vs_baseline_statistics.csv', index=False)
print("Saved: policies_vs_baseline_statistics.csv")

# Summary statistics by policy
print("\n" + "="*100)
print("SUMMARY: POLICIES VS BASELINE CHIP")
print("="*100)

policy_summary = stats_df.groupby(['policy', 'is_baseline_policy']).agg({
    'median_loss_vs_baseline': 'mean',
    'mean_loss_vs_baseline': 'mean',
    'pct_worse_than_baseline': 'mean',
    'pct_equal_to_baseline': 'mean'
}).round(3)

policy_summary = policy_summary.sort_values('median_loss_vs_baseline', ascending=False)

print("\nPolicies ranked by average median loss vs baseline (higher = closer to baseline):")
print(policy_summary.to_string())

print("\n" + "="*100)
print("INTERPRETATION:")
print("="*100)
print("- Loss vs Baseline = 0%: Policy performs equal to baseline")
print("- Loss vs Baseline > 0%: Policy performs BETTER than baseline (rare!)")
print("- Loss vs Baseline < 0%: Policy performs WORSE than baseline (common)")
print("\nBaseline policies should show ~0% median loss (they ARE the baseline)")
print("="*100)

# Find which non-baseline policies come closest to baseline
print("\nBest non-baseline policies (closest to baseline performance):")
non_baseline = stats_df[~stats_df['is_baseline_policy']].groupby('policy').agg({
    'median_loss_vs_baseline': 'mean',
    'mean_loss_vs_baseline': 'mean'
}).sort_values('median_loss_vs_baseline', ascending=False)

print(non_baseline.head(6).to_string())

print("\n" + "="*100)
print(f"Generated {len(all_policies)} detailed box plot figures (one per policy)")
print("Each figure shows IPC loss vs baseline across time steps for all benchmarks")
print("="*100)
