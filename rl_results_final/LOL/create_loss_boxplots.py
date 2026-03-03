import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re

# Read the CSV file
df = pd.read_csv('policy_ipc_table.csv')

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
                ipc_value = float(parts[1].strip())
                policy_dict[policy_name] = ipc_value
    
    return best_policy, best_ipc, policy_dict


def collect_loss_distributions(df):
    """Collect loss distributions for all benchmark-policy combinations."""
    benchmarks = [col for col in df.columns if col != 'step']
    
    # Dictionary to store: policy -> benchmark -> list of losses
    policy_benchmark_losses = {}
    
    for benchmark in benchmarks:
        for idx, row in df.iterrows():
            cell_content = row[benchmark]
            best_policy, best_ipc, policy_dict = parse_cell(cell_content)
            
            if best_policy is None:
                continue
            
            # For each policy, calculate loss at this step
            for policy, ipc in policy_dict.items():
                loss_pct = ((best_ipc - ipc) / best_ipc) * 100 if best_ipc > 0 else 0
                
                if policy not in policy_benchmark_losses:
                    policy_benchmark_losses[policy] = {}
                if benchmark not in policy_benchmark_losses[policy]:
                    policy_benchmark_losses[policy][benchmark] = []
                
                policy_benchmark_losses[policy][benchmark].append(loss_pct)
    
    return policy_benchmark_losses, benchmarks


print("Collecting loss distributions...")
policy_benchmark_losses, benchmarks = collect_loss_distributions(df)
all_policies = sorted(policy_benchmark_losses.keys())

print(f"Collected data for {len(all_policies)} policies and {len(benchmarks)} benchmarks")
print("Creating visualizations...")

# Create one figure per policy
for policy_idx, policy in enumerate(all_policies, 1):
    print(f"[{policy_idx}/{len(all_policies)}] Creating boxplot for {policy}...")
    
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
    for patch in bp['boxes']:
        patch.set_facecolor('lightblue')
        patch.set_alpha(0.7)
    
    # Styling
    ax.set_xlabel('Benchmark', fontsize=12, fontweight='bold')
    ax.set_ylabel('Performance Loss (%)', fontsize=12, fontweight='bold')
    ax.set_title(f'Distribution of Performance Loss Across Time Steps\nPolicy: {policy_short}', 
                 fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # Rotate x-axis labels
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=90, ha='right', fontsize=8)
    
    # Add horizontal line at y=0
    ax.axhline(y=0, color='green', linestyle='-', linewidth=1, alpha=0.5)
    
    # Add statistics text
    all_losses = [loss for losses in box_data for loss in losses]
    stats_text = f'Overall: Median={np.median(all_losses):.2f}%, Mean={np.mean(all_losses):.2f}%, Max={np.max(all_losses):.2f}%'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            fontsize=10)
    
    plt.tight_layout()
    
    # Save with safe filename
    filename = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '_').replace('_l2c_replacement-', '_')
    plt.savefig(f'loss_distribution_{filename}.png', dpi=200, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: loss_distribution_{filename}.png")

# Create a summary comparison figure
print("\nCreating summary comparison figure...")
fig, axes = plt.subplots(2, 4, figsize=(28, 12))
fig.suptitle('Performance Loss Distribution Summary: All Policies', fontsize=16, fontweight='bold')

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
    
    for patch in bp['boxes']:
        patch.set_facecolor('lightcoral')
        patch.set_alpha(0.6)
    
    #ax.set_title(policy_short.split('/')[-1], fontsize=10, fontweight='bold')
    ax.set_title(policy_short, fontsize=10, fontweight='bold')
    ax.set_ylabel('Loss (%)', fontsize=9)
    ax.set_xlabel('Benchmarks', fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    ax.set_xticklabels([])  # Remove x-tick labels for cleaner look
    
    # Add statistics
    all_losses = [loss for losses in box_data for loss in losses]
    median_loss = np.median(all_losses)
    ax.axhline(y=median_loss, color='red', linestyle='--', linewidth=1, alpha=0.7)
    ax.text(0.98, 0.95, f'Med: {median_loss:.2f}%', transform=ax.transAxes,
            ha='right', va='top', fontsize=8, bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))

plt.tight_layout()
plt.savefig('loss_distribution_summary.png', dpi=200, bbox_inches='tight')
print("Saved: loss_distribution_summary.png")

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
                'benchmark': benchmark,
                'median_loss': np.median(losses),
                'mean_loss': np.mean(losses),
                'std_loss': np.std(losses),
                'min_loss': np.min(losses),
                'max_loss': np.max(losses),
                'q25_loss': np.percentile(losses, 25),
                'q75_loss': np.percentile(losses, 75),
                'iqr_loss': np.percentile(losses, 75) - np.percentile(losses, 25),
                'num_steps': len(losses)
            })

stats_df = pd.DataFrame(stats_data)
stats_df.to_csv('loss_distribution_statistics.csv', index=False)
print("Saved: loss_distribution_statistics.csv")

# Print summary insights
print("\n" + "=" * 100)
print("KEY INSIGHTS FROM LOSS DISTRIBUTIONS")
print("=" * 100)

# Find benchmarks with highest variability (IQR)
print("\nBenchmarks with HIGHEST temporal variability (averaged across policies):")
high_var = stats_df.groupby('benchmark')['iqr_loss'].mean().sort_values(ascending=False).head(10)
for bench, iqr in high_var.items():
    print(f"  {bench:<30} IQR = {iqr:.3f}%")

print("\nBenchmarks with LOWEST temporal variability (averaged across policies):")
low_var = stats_df.groupby('benchmark')['iqr_loss'].mean().sort_values(ascending=True).head(10)
for bench, iqr in low_var.items():
    print(f"  {bench:<30} IQR = {iqr:.3f}%")

# Find policies with most consistent losses
print("\nPolicies with MOST consistent losses (lowest std dev across all benchmarks):")
consistent = stats_df.groupby('policy')['std_loss'].mean().sort_values(ascending=True)
for policy, std in consistent.items():
    print(f"  {policy:<70} Avg StdDev = {std:.3f}%")

print("\n" + "=" * 100)
print(f"Generated {len(all_policies)} detailed box plot figures (one per policy)")
print("Each figure shows the distribution of losses across time steps for all 49 benchmarks")
print("=" * 100)
