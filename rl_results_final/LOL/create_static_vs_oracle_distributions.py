import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re

# Read the CSV file
df = pd.read_csv('policy_ipc_table.csv')

print("="*100)
print("GENERATING GLOBAL LOSS DISTRIBUTIONS: STATIC POLICIES VS ORACLE")
print("="*100)
print("\nFor each policy: Calculate loss vs ORACLE (best possible) at each timestep")
print("This shows: 'If I had ONLY this policy, what's my loss distribution?'\n")

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


# Collect all policy vs oracle losses
print("Collecting policy vs oracle losses across all timesteps...")

policy_losses = {}
benchmarks = [col for col in df.columns if col != 'step']

for benchmark in benchmarks:
    for idx, row in df.iterrows():
        cell_content = row[benchmark]
        best_policy, best_ipc, policy_dict = parse_cell(cell_content)
        
        if best_policy is None or not policy_dict:
            continue
        
        # For each policy, calculate loss vs ORACLE (best_ipc)
        for policy, ipc in policy_dict.items():
            # Loss vs oracle (always >= 0)
            loss_pct = ((best_ipc - ipc) / best_ipc) * 100 if best_ipc > 0 else 0
            
            if policy not in policy_losses:
                policy_losses[policy] = []
            policy_losses[policy].append(loss_pct)

all_policies = sorted(policy_losses.keys())
print(f"Collected data for {len(all_policies)} policies, {len(policy_losses[all_policies[0]])} timesteps each")

# Create individual plots for each policy
for idx, policy in enumerate(all_policies, 1):
    print(f"[{idx}/{len(all_policies)}] Creating distribution plot for {policy}...")
    
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    
    losses = policy_losses[policy]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Define bins (all non-negative since we can't beat oracle)
    bins_ranges = ['0%\n(Optimal)', '0-0.1%', '0.1-0.5%', '0.5-1%', '1-2%', '2-5%', '5-10%', '>10%']
    
    bin_counts = [
        sum(1 for l in losses if abs(l) < 0.001),  # Optimal (equals oracle)
        sum(1 for l in losses if 0.001 <= l < 0.1),
        sum(1 for l in losses if 0.1 <= l < 0.5),
        sum(1 for l in losses if 0.5 <= l < 1.0),
        sum(1 for l in losses if 1.0 <= l < 2.0),
        sum(1 for l in losses if 2.0 <= l < 5.0),
        sum(1 for l in losses if 5.0 <= l < 10.0),
        sum(1 for l in losses if l >= 10.0)
    ]
    
    bin_percentages = [100 * c / len(losses) for c in bin_counts]
    
    # Color code: green for optimal, gradient to red for worse
    colors = ['green', 'lightgreen', 'yellow', 'lightyellow', 'lightcoral', 'coral', 'orangered', 'darkred']
    
    bars = ax.barh(bins_ranges, bin_percentages, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
    
    ax.set_xlabel('Percentage of Timesteps (%)', fontsize=14, fontweight='bold')
    ax.set_ylabel('IPC Loss vs Oracle (Best Possible)', fontsize=14, fontweight='bold')
    
    ax.set_title(f'Global Loss Distribution: {policy_short}\n' +
                 f'Static Policy vs Oracle Across All Timesteps (N=4,900)',
                 fontsize=15, fontweight='bold')
    
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    
    # Add percentage labels on bars
    for i, (bar, pct, count) in enumerate(zip(bars, bin_percentages, bin_counts)):
        if pct > 0.5:  # Only show label if bar is visible
            label = f'{pct:.1f}% (n={count})'
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                   label, va='center', fontsize=10, fontweight='bold')
    
    # Add statistics box
    stats_text = f'Statistics:\n'
    stats_text += f'Mean:   {np.mean(losses):>7.3f}%\n'
    stats_text += f'Median: {np.median(losses):>7.3f}%\n'
    stats_text += f'Std:    {np.std(losses):>7.3f}%\n'
    stats_text += f'Min:    {np.min(losses):>7.3f}%\n'
    stats_text += f'Max:    {np.max(losses):>7.3f}%\n'
    stats_text += f'P95:    {np.percentile(losses, 95):>7.3f}%\n'
    stats_text += f'P99:    {np.percentile(losses, 99):>7.3f}%'
    
    ax.text(0.98, 0.97, stats_text, transform=ax.transAxes,
           verticalalignment='top', horizontalalignment='right',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9),
           fontsize=11, fontfamily='monospace')
    
    # Add legend explaining interpretation
    legend_text = 'Green: Policy is OPTIMAL (matches oracle)\nRed: Policy is SUBOPTIMAL\n\nLoss is always >= 0%\n(Cannot beat oracle by definition)'
    ax.text(0.02, 0.97, legend_text, transform=ax.transAxes,
           verticalalignment='top', horizontalalignment='left',
           bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
           fontsize=10)
    
    plt.tight_layout()
    
    # Save with safe filename
    filename = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '_').replace('_l2c_replacement-', '_')
    plt.savefig(f'static_vs_oracle_dist_{filename}.png', dpi=200, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: static_vs_oracle_dist_{filename}.png")

# Create a summary comparison figure with all policies
print("\nCreating summary comparison figure...")
fig, axes = plt.subplots(2, 4, figsize=(24, 12))
fig.suptitle('Static Policy Loss Distribution vs Oracle: All Policies\n' +
             'Each shows 4,900 timesteps - lower is better',
             fontsize=16, fontweight='bold')

for idx, (ax, policy) in enumerate(zip(axes.flat, all_policies)):
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    
    losses = policy_losses[policy]
    
    # Simplified bins for overview
    bins_ranges = ['0%\n(Optimal)', '0-1%', '1-2%', '2-5%', '5-10%', '>10%']
    bin_counts = [
        sum(1 for l in losses if abs(l) < 0.001),
        sum(1 for l in losses if 0.001 <= l < 1.0),
        sum(1 for l in losses if 1.0 <= l < 2.0),
        sum(1 for l in losses if 2.0 <= l < 5.0),
        sum(1 for l in losses if 5.0 <= l < 10.0),
        sum(1 for l in losses if l >= 10.0)
    ]
    bin_percentages = [100 * c / len(losses) for c in bin_counts]
    
    colors = ['green', 'yellow', 'lightcoral', 'coral', 'orangered', 'darkred']
    bars = ax.bar(bins_ranges, bin_percentages, color=colors, alpha=0.7, edgecolor='black')
    
    ax.set_title(f'{policy_short}', fontsize=11, fontweight='bold')
    ax.set_ylabel('% of Timesteps', fontsize=10)
    ax.set_xlabel('Loss Range', fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    ax.tick_params(axis='x', labelsize=8, rotation=0)
    
    # Add median value
    median_loss = np.median(losses)
    mean_loss = np.mean(losses)
    ax.text(0.95, 0.95, f'Median: {median_loss:.2f}%\nMean: {mean_loss:.2f}%', 
           transform=ax.transAxes, ha='right', va='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7),
           fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig('static_vs_oracle_dist_summary.png', dpi=200, bbox_inches='tight')
print("Saved: static_vs_oracle_dist_summary.png")

# Create statistics summary CSV
print("\nCreating summary statistics CSV...")
summary_data = []
for policy in all_policies:
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    losses = policy_losses[policy]
    
    summary_data.append({
        'policy': policy_short,
        'mean_loss': np.mean(losses),
        'median_loss': np.median(losses),
        'std_loss': np.std(losses),
        'min_loss': np.min(losses),
        'max_loss': np.max(losses),
        'p25': np.percentile(losses, 25),
        'p75': np.percentile(losses, 75),
        'p95': np.percentile(losses, 95),
        'p99': np.percentile(losses, 99),
        'pct_optimal': 100 * sum(1 for l in losses if abs(l) < 0.001) / len(losses),
        'pct_excellent': 100 * sum(1 for l in losses if l < 1.0) / len(losses),
        'pct_bad': 100 * sum(1 for l in losses if l >= 5.0) / len(losses)
    })

summary_df = pd.DataFrame(summary_data)
summary_df = summary_df.sort_values('median_loss')
summary_df.to_csv('static_vs_oracle_dist_summary.csv', index=False)
print("Saved: static_vs_oracle_dist_summary.csv")

print("\n" + "="*100)
print("SUMMARY")
print("="*100)
print("\nPolicies ranked by median loss vs oracle (lower is better):")
print(summary_df[['policy', 'median_loss', 'mean_loss', 'pct_optimal', 'pct_excellent']].to_string(index=False))

print("\n" + "="*100)
print(f"Generated {len(all_policies)} individual distribution plots")
print("Generated 1 summary comparison plot")
print("="*100)
print("\nNote: This shows STATIC policies (one policy for all timesteps) vs ORACLE")
print("Loss is always >= 0 because oracle = best possible by definition")
print("="*100)
