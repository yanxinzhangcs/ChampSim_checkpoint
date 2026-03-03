import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
import re

# Read the CSV file
df = pd.read_csv('policy_ipc_table.csv')

# Function to parse the multiline cell content
def parse_cell(cell_content):
    """
    Parse a cell containing multiline IPC data.
    Returns: (best_policy, best_ipc, policy_dict)
    where policy_dict maps policy names to IPC values
    """
    if pd.isna(cell_content):
        return None, None, {}
    
    lines = cell_content.strip().split('\n')
    policy_dict = {}
    best_policy = None
    best_ipc = None
    
    for line in lines:
        if line.startswith('BEST:'):
            # Extract best policy info
            match = re.search(r'BEST: (.+?) \(IPC=([\d.]+)\)', line)
            if match:
                best_policy = match.group(1)
                best_ipc = float(match.group(2))
        else:
            # Parse policy: IPC line
            parts = line.split(': ')
            if len(parts) == 2:
                policy_name = parts[0].strip()
                ipc_value = float(parts[1].strip())
                policy_dict[policy_name] = ipc_value
    
    return best_policy, best_ipc, policy_dict


def analyze_benchmark(df, benchmark_name):
    """
    Analyze a single benchmark to determine performance loss from static policies.
    """
    if benchmark_name not in df.columns:
        print(f"Benchmark {benchmark_name} not found!")
        return None
    
    results = []
    all_policies = set()
    
    # Parse each step
    for idx, row in df.iterrows():
        step = row['step']
        cell_content = row[benchmark_name]
        
        best_policy, best_ipc, policy_dict = parse_cell(cell_content)
        
        if best_policy is None:
            continue
        
        all_policies.update(policy_dict.keys())
        
        step_data = {
            'step': step,
            'best_policy': best_policy,
            'best_ipc': best_ipc
        }
        
        # Calculate performance loss for each policy
        for policy, ipc in policy_dict.items():
            step_data[f'{policy}_ipc'] = ipc
            step_data[f'{policy}_loss'] = best_ipc - ipc
            step_data[f'{policy}_loss_pct'] = ((best_ipc - ipc) / best_ipc) * 100 if best_ipc > 0 else 0
        
        results.append(step_data)
    
    return pd.DataFrame(results), list(all_policies)


# Analyze the first benchmark
benchmark = '400.perlbench-41B'
print(f"Analyzing benchmark: {benchmark}")
print("=" * 80)

results_df, all_policies = analyze_benchmark(df, benchmark)

# Get sorted list of unique policies
all_policies = sorted(all_policies)
print(f"\nFound {len(all_policies)} policy combinations:")
for i, policy in enumerate(all_policies, 1):
    print(f"  {i}. {policy}")

# Calculate statistics for each static policy choice
print(f"\n{'Policy':<70} {'Avg Loss':<10} {'Max Loss':<10} {'Min Loss':<10}")
print("=" * 100)

policy_stats = []
for policy in all_policies:
    loss_col = f'{policy}_loss'
    if loss_col in results_df.columns:
        avg_loss = results_df[loss_col].mean()
        max_loss = results_df[loss_col].max()
        min_loss = results_df[loss_col].min()
        
        policy_stats.append({
            'policy': policy,
            'avg_loss': avg_loss,
            'max_loss': max_loss,
            'min_loss': min_loss,
            'avg_loss_pct': results_df[f'{policy}_loss_pct'].mean()
        })
        
        print(f"{policy:<70} {avg_loss:>10.6f} {max_loss:>10.6f} {min_loss:>10.6f}")

policy_stats_df = pd.DataFrame(policy_stats).sort_values('avg_loss')

# Create visualizations
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle(f'Policy Performance Analysis: {benchmark}', fontsize=16, fontweight='bold')

# 1. Which policy was best over time
ax1 = axes[0, 0]
best_policy_counts = results_df['best_policy'].value_counts()
ax1.bar(range(len(best_policy_counts)), best_policy_counts.values)
ax1.set_xticks(range(len(best_policy_counts)))
ax1.set_xticklabels([p.split('_')[-1] if 'replacement' in p else p[:20] 
                       for p in best_policy_counts.index], rotation=45, ha='right', fontsize=8)
ax1.set_ylabel('Number of Steps', fontsize=10)
ax1.set_title('Which Policy Was Best (by frequency)', fontsize=12)
ax1.grid(axis='y', alpha=0.3)

# 2. Average performance loss for each static policy
ax2 = axes[0, 1]
top_n = 8  # Show top 8 best policies
top_policies = policy_stats_df.head(top_n)
y_pos = np.arange(len(top_policies))
ax2.barh(y_pos, top_policies['avg_loss_pct'])
ax2.set_yticks(y_pos)
ax2.set_yticklabels([p.split('_')[-1] if 'replacement' in p else p[-30:] 
                       for p in top_policies['policy']], fontsize=8)
ax2.set_xlabel('Average Performance Loss (%)', fontsize=10)
ax2.set_title(f'Top {top_n} Policies by Average Loss', fontsize=12)
ax2.grid(axis='x', alpha=0.3)
ax2.invert_yaxis()

# 3. Distribution of performance loss for top policies
ax3 = axes[1, 0]
for policy in policy_stats_df.head(4)['policy']:
    loss_col = f'{policy}_loss_pct'
    if loss_col in results_df.columns:
        label = policy.split('_')[-1] if 'replacement' in policy else policy[-20:]
        ax3.hist(results_df[loss_col], alpha=0.5, bins=30, label=label)
ax3.set_xlabel('Performance Loss (%)', fontsize=10)
ax3.set_ylabel('Frequency', fontsize=10)
ax3.set_title('Distribution of Performance Loss (Top 4 Policies)', fontsize=12)
ax3.legend(fontsize=8)
ax3.grid(alpha=0.3)

# 4. Performance loss over time for top policies
ax4 = axes[1, 1]
for policy in policy_stats_df.head(4)['policy']:
    loss_col = f'{policy}_loss_pct'
    if loss_col in results_df.columns:
        label = policy.split('_')[-1] if 'replacement' in policy else policy[-20:]
        ax4.plot(results_df['step'], results_df[loss_col], alpha=0.7, label=label, linewidth=1.5)
ax4.set_xlabel('Step (1M instructions)', fontsize=10)
ax4.set_ylabel('Performance Loss (%)', fontsize=10)
ax4.set_title('Performance Loss Over Time (Top 4 Policies)', fontsize=12)
ax4.legend(fontsize=8)
ax4.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(f'{benchmark}_policy_analysis.png', dpi=300, bbox_inches='tight')
print(f"\nVisualization saved to: {benchmark}_policy_analysis.png")

# Save detailed results to CSV
results_df.to_csv(f'{benchmark}_detailed_results.csv', index=False)
policy_stats_df.to_csv(f'{benchmark}_policy_stats.csv', index=False)
print(f"Detailed results saved to: {benchmark}_detailed_results.csv")
print(f"Policy statistics saved to: {benchmark}_policy_stats.csv")

print("\n" + "=" * 80)
print("KEY INSIGHTS:")
print("=" * 80)
print(f"Best static policy: {policy_stats_df.iloc[0]['policy']}")
print(f"  - Average loss: {policy_stats_df.iloc[0]['avg_loss_pct']:.3f}%")
print(f"  - Max loss: {policy_stats_df.iloc[0]['max_loss']:.6f} IPC")
print(f"\nWorst static policy: {policy_stats_df.iloc[-1]['policy']}")
print(f"  - Average loss: {policy_stats_df.iloc[-1]['avg_loss_pct']:.3f}%")
print(f"  - Max loss: {policy_stats_df.iloc[-1]['max_loss']:.6f} IPC")
