import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re

# Read the CSV file
df = pd.read_csv('policy_ipc_table.csv')

# Function to parse the multiline cell content
def parse_cell(cell_content):
    """
    Parse a cell containing multiline IPC data.
    Returns: (best_policy, best_ipc, policy_dict)
    """
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


def analyze_benchmark(df, benchmark_name):
    """
    Analyze a single benchmark to determine performance loss from static policies.
    """
    if benchmark_name not in df.columns:
        return None, None
    
    results = []
    all_policies = set()
    
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
        
        for policy, ipc in policy_dict.items():
            step_data[f'{policy}_ipc'] = ipc
            step_data[f'{policy}_loss'] = best_ipc - ipc
            step_data[f'{policy}_loss_pct'] = ((best_ipc - ipc) / best_ipc) * 100 if best_ipc > 0 else 0
        
        results.append(step_data)
    
    return pd.DataFrame(results), list(all_policies)


# Get all benchmark names (all columns except 'step')
benchmarks = [col for col in df.columns if col != 'step']
print(f"Analyzing {len(benchmarks)} benchmarks...")
print("=" * 100)

# Analyze all benchmarks
all_benchmark_stats = []

for i, benchmark in enumerate(benchmarks, 1):
    print(f"\n[{i}/{len(benchmarks)}] Analyzing {benchmark}...", end=' ')
    
    results_df, all_policies = analyze_benchmark(df, benchmark)
    
    if results_df is None or len(results_df) == 0:
        print("SKIPPED (no data)")
        continue
    
    all_policies = sorted(all_policies)
    
    # Calculate statistics for each policy
    for policy in all_policies:
        loss_col = f'{policy}_loss'
        loss_pct_col = f'{policy}_loss_pct'
        
        if loss_col in results_df.columns:
            all_benchmark_stats.append({
                'benchmark': benchmark,
                'policy': policy,
                'avg_loss': results_df[loss_col].mean(),
                'max_loss': results_df[loss_col].max(),
                'min_loss': results_df[loss_col].min(),
                'std_loss': results_df[loss_col].std(),
                'avg_loss_pct': results_df[loss_pct_col].mean(),
                'max_loss_pct': results_df[loss_pct_col].max(),
                'times_best': (results_df['best_policy'] == policy).sum(),
                'total_steps': len(results_df)
            })
    
    print(f"OK ({len(all_policies)} policies)")

# Create comprehensive DataFrame
all_stats_df = pd.DataFrame(all_benchmark_stats)

# Save comprehensive results
all_stats_df.to_csv('all_benchmarks_policy_stats.csv', index=False)
print(f"\n\nComprehensive results saved to: all_benchmarks_policy_stats.csv")

# Analysis 1: Best static policy per benchmark
print("\n" + "=" * 100)
print("BEST STATIC POLICY PER BENCHMARK")
print("=" * 100)
print(f"{'Benchmark':<30} {'Best Policy':<70} {'Avg Loss %':<12}")
print("-" * 112)

best_per_benchmark = all_stats_df.loc[all_stats_df.groupby('benchmark')['avg_loss_pct'].idxmin()]
for _, row in best_per_benchmark.iterrows():
    policy_short = row['policy'].replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    print(f"{row['benchmark']:<30} {policy_short:<70} {row['avg_loss_pct']:>10.3f}%")

# Analysis 2: Overall best static policy across all benchmarks
print("\n" + "=" * 100)
print("OVERALL BEST STATIC POLICIES (across all benchmarks)")
print("=" * 100)

overall_avg = all_stats_df.groupby('policy').agg({
    'avg_loss_pct': 'mean',
    'max_loss_pct': 'mean',
    'times_best': 'sum',
    'total_steps': 'sum'
}).reset_index()

overall_avg = overall_avg.sort_values('avg_loss_pct')
print(f"{'Policy':<70} {'Avg Loss %':<12} {'Max Loss %':<12} {'Times Best':<12}")
print("-" * 106)
for _, row in overall_avg.iterrows():
    policy_short = row['policy'].replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    print(f"{policy_short:<70} {row['avg_loss_pct']:>10.3f}% {row['max_loss_pct']:>10.3f}% {int(row['times_best']):>10}")

# Analysis 3: Do different benchmarks prefer different policies?
print("\n" + "=" * 100)
print("POLICY PREFERENCE DIVERSITY")
print("=" * 100)

# Count how many unique best policies across benchmarks
best_policies_per_benchmark = best_per_benchmark['policy'].value_counts()
print(f"\nNumber of unique best static policies: {len(best_policies_per_benchmark)}")
print(f"\nPolicy preference distribution:")
for policy, count in best_policies_per_benchmark.items():
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    print(f"  {policy_short}: {count} benchmarks ({count/len(benchmarks)*100:.1f}%)")

# Create visualizations
fig = plt.figure(figsize=(20, 12))
gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

# 1. Heatmap: Average loss % for each benchmark-policy combination
ax1 = fig.add_subplot(gs[0, :])
pivot_data = all_stats_df.pivot_table(values='avg_loss_pct', index='policy', columns='benchmark')
# Select top policies
top_policies = overall_avg.head(8)['policy'].tolist()
pivot_data_subset = pivot_data.loc[top_policies]

im = ax1.imshow(pivot_data_subset.values, cmap='RdYlGn_r', aspect='auto', vmin=0, vmax=2)
ax1.set_xticks(np.arange(len(pivot_data_subset.columns)))
ax1.set_yticks(np.arange(len(pivot_data_subset.index)))
ax1.set_xticklabels([b.split('-')[0][:15] for b in pivot_data_subset.columns], rotation=90, fontsize=7)
ax1.set_yticklabels([p.split('_')[-1] for p in pivot_data_subset.index], fontsize=8)
ax1.set_title('Performance Loss Heatmap: Top 8 Policies Across All Benchmarks (%)', fontsize=12, fontweight='bold')
plt.colorbar(im, ax=ax1, label='Avg Loss %')

# 2. Best policy per benchmark
ax2 = fig.add_subplot(gs[1, 0])
policy_counts = best_per_benchmark['policy'].value_counts()
colors = plt.cm.Set3(np.linspace(0, 1, len(policy_counts)))
ax2.bar(range(len(policy_counts)), policy_counts.values, color=colors)
ax2.set_xticks(range(len(policy_counts)))
ax2.set_xticklabels([p.split('_')[-1] for p in policy_counts.index], rotation=45, ha='right', fontsize=8)
ax2.set_ylabel('Number of Benchmarks', fontsize=10)
ax2.set_title('Best Static Policy Distribution', fontsize=11, fontweight='bold')
ax2.grid(axis='y', alpha=0.3)

# 3. Average loss distribution across benchmarks
ax3 = fig.add_subplot(gs[1, 1])
for policy in top_policies[:4]:
    policy_data = all_stats_df[all_stats_df['policy'] == policy]
    label = policy.split('_')[-1]
    ax3.hist(policy_data['avg_loss_pct'], alpha=0.5, bins=20, label=label)
ax3.set_xlabel('Average Loss (%)', fontsize=10)
ax3.set_ylabel('Frequency', fontsize=10)
ax3.set_title('Distribution of Avg Loss Across Benchmarks', fontsize=11, fontweight='bold')
ax3.legend(fontsize=8)
ax3.grid(alpha=0.3)

# 4. Max loss distribution
ax4 = fig.add_subplot(gs[1, 2])
for policy in top_policies[:4]:
    policy_data = all_stats_df[all_stats_df['policy'] == policy]
    label = policy.split('_')[-1]
    ax4.hist(policy_data['max_loss_pct'], alpha=0.5, bins=20, label=label)
ax4.set_xlabel('Max Loss (%)', fontsize=10)
ax4.set_ylabel('Frequency', fontsize=10)
ax4.set_title('Distribution of Max Loss Across Benchmarks', fontsize=11, fontweight='bold')
ax4.legend(fontsize=8)
ax4.grid(alpha=0.3)

# 5. Overall policy ranking
ax5 = fig.add_subplot(gs[2, :])
top_n = 8
top_overall = overall_avg.head(top_n)
y_pos = np.arange(len(top_overall))
bars = ax5.barh(y_pos, top_overall['avg_loss_pct'])
ax5.set_yticks(y_pos)
policy_labels = [p.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/') 
                 for p in top_overall['policy']]
ax5.set_yticklabels(policy_labels, fontsize=9)
ax5.set_xlabel('Average Performance Loss Across All Benchmarks (%)', fontsize=11)
ax5.set_title(f'Top {top_n} Static Policies (Overall Ranking)', fontsize=12, fontweight='bold')
ax5.grid(axis='x', alpha=0.3)
ax5.invert_yaxis()

# Add value labels on bars
for i, (bar, val) in enumerate(zip(bars, top_overall['avg_loss_pct'])):
    ax5.text(val + 0.01, bar.get_y() + bar.get_height()/2, f'{val:.3f}%', 
             va='center', fontsize=8)

plt.savefig('all_benchmarks_analysis.png', dpi=300, bbox_inches='tight')
print(f"\nComprehensive visualization saved to: all_benchmarks_analysis.png")

# Summary statistics
print("\n" + "=" * 100)
print("SUMMARY STATISTICS")
print("=" * 100)
print(f"Total benchmarks analyzed: {len(benchmarks)}")
print(f"Total unique policies: {len(all_stats_df['policy'].unique())}")
print(f"Average performance loss from best static policy: {best_per_benchmark['avg_loss_pct'].mean():.3f}%")
print(f"Range of average losses: {best_per_benchmark['avg_loss_pct'].min():.3f}% to {best_per_benchmark['avg_loss_pct'].max():.3f}%")
print(f"\nBest universal static policy: {overall_avg.iloc[0]['policy']}")
print(f"  - Average loss across all benchmarks: {overall_avg.iloc[0]['avg_loss_pct']:.3f}%")
print(f"  - Number of times it was the best: {int(overall_avg.iloc[0]['times_best'])}")
