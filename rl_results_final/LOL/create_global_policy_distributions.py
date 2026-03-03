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

print("="*100)
print("GENERATING GLOBAL LOSS DISTRIBUTIONS FOR EACH POLICY VS BASELINE")
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


# Collect all policy vs baseline losses
print("\nCollecting policy vs baseline losses across all timesteps...")

policy_losses = {}
benchmarks = [col for col in df.columns if col != 'step']

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
        
        # For each policy, calculate loss vs baseline
        for policy, ipc in policy_dict.items():
            loss_pct = ((baseline_ipc - ipc) / baseline_ipc) * 100 if baseline_ipc > 0 else 0
            
            if policy not in policy_losses:
                policy_losses[policy] = []
            policy_losses[policy].append(loss_pct)

all_policies = sorted(policy_losses.keys())
print(f"Collected data for {len(all_policies)} policies, {len(policy_losses[all_policies[0]])} timesteps each")

# Create individual plots for each policy
for idx, policy in enumerate(all_policies, 1):
    print(f"[{idx}/{len(all_policies)}] Creating distribution plot for {policy}...")
    
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    is_baseline = policy in BASELINE_POLICIES
    
    losses = policy_losses[policy]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Define bins - note we include negative bins for when policy beats baseline
    bins_ranges = ['<-5%', '-5 to -2%', '-2 to -1%', '-1 to -0.5%', '-0.5 to 0%', 
                   '0%', '0-0.1%', '0.1-0.5%', '0.5-1%', '1-2%', '2-5%', '>5%']
    
    bin_counts = [
        sum(1 for l in losses if l < -5.0),
        sum(1 for l in losses if -5.0 <= l < -2.0),
        sum(1 for l in losses if -2.0 <= l < -1.0),
        sum(1 for l in losses if -1.0 <= l < -0.5),
        sum(1 for l in losses if -0.5 <= l < 0.0),
        sum(1 for l in losses if abs(l) < 0.001),  # Equals baseline
        sum(1 for l in losses if 0.001 <= l < 0.1),
        sum(1 for l in losses if 0.1 <= l < 0.5),
        sum(1 for l in losses if 0.5 <= l < 1.0),
        sum(1 for l in losses if 1.0 <= l < 2.0),
        sum(1 for l in losses if 2.0 <= l < 5.0),
        sum(1 for l in losses if l >= 5.0)
    ]
    
    bin_percentages = [100 * c / len(losses) for c in bin_counts]
    
    # Color code: green for negative (better than baseline), red for positive (worse)
    colors = ['darkgreen', 'green', 'lightgreen', 'palegreen', 'lightgray',
              'yellow', 'lightyellow', 'lightcoral', 'coral', 'orangered', 'red', 'darkred']
    
    bars = ax.barh(bins_ranges, bin_percentages, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
    
    ax.set_xlabel('Percentage of Timesteps (%)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Loss Range vs Baseline', fontsize=14, fontweight='bold')
    
    baseline_text = ' [BASELINE POLICY]' if is_baseline else ''
    ax.set_title(f'Global Loss Distribution: {policy_short}{baseline_text}\n' +
                 f'vs Baseline Chip (N=4,900 timesteps)',
                 fontsize=15, fontweight='bold')
    
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    
    # Add percentage labels on bars
    for i, (bar, pct, count) in enumerate(zip(bars, bin_percentages, bin_counts)):
        if pct > 0.5:  # Only show label if bar is visible
            label = f'{pct:.1f}% (n={count})'
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                   label, va='center', fontsize=10, fontweight='bold')
    
    # Add vertical line at 0
    ax.axvline(x=0, color='black', linestyle='-', linewidth=2, alpha=0.5)
    
    # Add statistics box
    stats_text = f'Statistics:\n'
    stats_text += f'Mean:   {np.mean(losses):>7.3f}%\n'
    stats_text += f'Median: {np.median(losses):>7.3f}%\n'
    stats_text += f'Std:    {np.std(losses):>7.3f}%\n'
    stats_text += f'Min:    {np.min(losses):>7.3f}%\n'
    stats_text += f'Max:    {np.max(losses):>7.3f}%\n'
    stats_text += f'P95:    {np.percentile(losses, 95):>7.3f}%'
    
    ax.text(0.98, 0.97, stats_text, transform=ax.transAxes,
           verticalalignment='top', horizontalalignment='right',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9),
           fontsize=11, fontfamily='monospace')
    
    # Add legend explaining colors
    legend_text = 'Green: Policy BEATS baseline\nYellow: Policy EQUALS baseline\nRed: Policy WORSE than baseline'
    ax.text(0.02, 0.97, legend_text, transform=ax.transAxes,
           verticalalignment='top', horizontalalignment='left',
           bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
           fontsize=10)
    
    plt.tight_layout()
    
    # Save with safe filename
    filename = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '_').replace('_l2c_replacement-', '_')
    plt.savefig(f'global_dist_{filename}.png', dpi=200, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: global_dist_{filename}.png")

# Create a summary comparison figure with all policies
print("\nCreating summary comparison figure...")
fig, axes = plt.subplots(2, 4, figsize=(24, 12))
fig.suptitle('Global Loss Distribution Comparison: All Policies vs Baseline Chip\n' +
             'Each distribution shows 4,900 timesteps across all benchmarks',
             fontsize=16, fontweight='bold')

for idx, (ax, policy) in enumerate(zip(axes.flat, all_policies)):
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    is_baseline = policy in BASELINE_POLICIES
    
    losses = policy_losses[policy]
    
    # Simplified bins for overview
    bins_ranges = ['< 0%\n(Beats)', '0%\n(Equals)', '0-1%', '1-2%', '2-5%', '> 5%']
    bin_counts = [
        sum(1 for l in losses if l < 0),
        sum(1 for l in losses if abs(l) < 0.001),
        sum(1 for l in losses if 0.001 <= l < 1.0),
        sum(1 for l in losses if 1.0 <= l < 2.0),
        sum(1 for l in losses if 2.0 <= l < 5.0),
        sum(1 for l in losses if l >= 5.0)
    ]
    bin_percentages = [100 * c / len(losses) for c in bin_counts]
    
    colors = ['green', 'yellow', 'lightcoral', 'coral', 'orangered', 'darkred']
    bars = ax.bar(bins_ranges, bin_percentages, color=colors, alpha=0.7, edgecolor='black')
    
    baseline_marker = ' ★' if is_baseline else ''
    ax.set_title(f'{policy_short}{baseline_marker}', fontsize=11, fontweight='bold')
    ax.set_ylabel('% of Timesteps', fontsize=10)
    ax.set_xlabel('Loss Range', fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    ax.tick_params(axis='x', labelsize=8, rotation=0)
    
    # Add median value
    median_loss = np.median(losses)
    ax.text(0.95, 0.95, f'Median:\n{median_loss:.2f}%', 
           transform=ax.transAxes, ha='right', va='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7),
           fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig('global_dist_summary_all_policies.png', dpi=200, bbox_inches='tight')
print("Saved: global_dist_summary_all_policies.png")

# Create statistics summary CSV
print("\nCreating summary statistics CSV...")
summary_data = []
for policy in all_policies:
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    losses = policy_losses[policy]
    
    summary_data.append({
        'policy': policy_short,
        'is_baseline': policy in BASELINE_POLICIES,
        'mean_loss': np.mean(losses),
        'median_loss': np.median(losses),
        'std_loss': np.std(losses),
        'min_loss': np.min(losses),
        'max_loss': np.max(losses),
        'p25': np.percentile(losses, 25),
        'p75': np.percentile(losses, 75),
        'p95': np.percentile(losses, 95),
        'pct_beats_baseline': 100 * sum(1 for l in losses if l < -0.001) / len(losses),
        'pct_equals_baseline': 100 * sum(1 for l in losses if abs(l) < 0.001) / len(losses),
        'pct_worse_than_baseline': 100 * sum(1 for l in losses if l > 0.001) / len(losses)
    })

summary_df = pd.DataFrame(summary_data)
summary_df = summary_df.sort_values('median_loss')
summary_df.to_csv('global_policy_distributions_summary.csv', index=False)
print("Saved: global_policy_distributions_summary.csv")

print("\n" + "="*100)
print("SUMMARY")
print("="*100)
print("\nPolicies ranked by median loss (lower is better):")
print(summary_df[['policy', 'is_baseline', 'median_loss', 'mean_loss', 'pct_equals_baseline']].to_string(index=False))

print("\n" + "="*100)
print(f"Generated {len(all_policies)} individual distribution plots")
print("Generated 1 summary comparison plot")
print("="*100)
