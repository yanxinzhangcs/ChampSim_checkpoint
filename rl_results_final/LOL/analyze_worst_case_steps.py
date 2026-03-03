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


def analyze_worst_case_per_benchmark(df, benchmark_name):
    """Find the worst-case step for each policy in a benchmark."""
    if benchmark_name not in df.columns:
        return None
    
    worst_cases = {}
    
    for idx, row in df.iterrows():
        step = row['step']
        cell_content = row[benchmark_name]
        
        best_policy, best_ipc, policy_dict = parse_cell(cell_content)
        
        if best_policy is None:
            continue
        
        # For each policy, calculate loss at this step
        for policy, ipc in policy_dict.items():
            loss = best_ipc - ipc
            loss_pct = ((best_ipc - ipc) / best_ipc) * 100 if best_ipc > 0 else 0
            
            # Track worst case for this policy
            if policy not in worst_cases or loss_pct > worst_cases[policy]['loss_pct']:
                worst_cases[policy] = {
                    'step': step,
                    'loss': loss,
                    'loss_pct': loss_pct,
                    'policy_ipc': ipc,
                    'best_ipc': best_ipc,
                    'best_policy_at_step': best_policy
                }
    
    return worst_cases


# Get all benchmark names
benchmarks = [col for col in df.columns if col != 'step']
print(f"Analyzing worst-case time steps for {len(benchmarks)} benchmarks...")
print("=" * 120)

# Collect all worst-case data
all_worst_cases = []

for i, benchmark in enumerate(benchmarks, 1):
    print(f"[{i}/{len(benchmarks)}] {benchmark}...", end=' ')
    
    worst_cases = analyze_worst_case_per_benchmark(df, benchmark)
    
    if worst_cases is None:
        print("SKIPPED")
        continue
    
    for policy, data in worst_cases.items():
        all_worst_cases.append({
            'benchmark': benchmark,
            'policy': policy,
            'worst_step': data['step'],
            'worst_loss_ipc': data['loss'],
            'worst_loss_pct': data['loss_pct'],
            'policy_ipc_at_worst': data['policy_ipc'],
            'best_ipc_at_worst': data['best_ipc'],
            'best_policy_at_worst_step': data['best_policy_at_step']
        })
    
    print(f"OK")

# Create DataFrame
worst_case_df = pd.DataFrame(all_worst_cases)

# Save to CSV
worst_case_df.to_csv('worst_case_steps.csv', index=False)
print(f"\nDetailed worst-case data saved to: worst_case_steps.csv")

# Analysis 1: Which steps are most problematic across all benchmarks?
print("\n" + "=" * 120)
print("MOST PROBLEMATIC STEPS (steps where static policies fail hardest)")
print("=" * 120)

# Group by step and count how many times each step appears as worst-case
step_counts = worst_case_df.groupby('worst_step').agg({
    'worst_loss_pct': ['mean', 'max'],
    'benchmark': 'count'
}).reset_index()
step_counts.columns = ['step', 'avg_loss_pct', 'max_loss_pct', 'count']
step_counts = step_counts.sort_values('count', ascending=False)

print(f"\n{'Step':<10} {'Times Worst':<15} {'Avg Loss %':<15} {'Max Loss %':<15}")
print("-" * 55)
for _, row in step_counts.head(20).iterrows():
    print(f"{int(row['step']):<10} {int(row['count']):<15} {row['avg_loss_pct']:>13.3f}% {row['max_loss_pct']:>13.3f}%")

# Analysis 2: For each policy, find benchmarks with highest worst-case loss
print("\n" + "=" * 120)
print("WORST-CASE LOSSES PER POLICY")
print("=" * 120)

all_policies = sorted(worst_case_df['policy'].unique())

for policy in all_policies:
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    print(f"\n{policy_short}")
    print("-" * 120)
    
    policy_data = worst_case_df[worst_case_df['policy'] == policy].sort_values('worst_loss_pct', ascending=False)
    
    print(f"{'Benchmark':<30} {'Worst Step':<15} {'Loss %':<12} {'Loss IPC':<12} {'Best at That Step':<50}")
    print("-" * 120)
    
    for _, row in policy_data.head(10).iterrows():
        best_short = row['best_policy_at_worst_step'].replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
        print(f"{row['benchmark']:<30} {int(row['worst_step']):<15} {row['worst_loss_pct']:>10.3f}% {row['worst_loss_ipc']:>10.6f} {best_short:<50}")

# Analysis 3: Summary statistics per policy
print("\n" + "=" * 120)
print("SUMMARY: WORST-CASE STATISTICS PER POLICY")
print("=" * 120)

policy_summary = worst_case_df.groupby('policy').agg({
    'worst_loss_pct': ['mean', 'max', 'min', 'std'],
    'worst_step': lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0]
}).reset_index()

policy_summary.columns = ['policy', 'avg_worst_loss_pct', 'max_worst_loss_pct', 'min_worst_loss_pct', 'std_worst_loss_pct', 'most_common_worst_step']
policy_summary = policy_summary.sort_values('avg_worst_loss_pct')

print(f"\n{'Policy':<70} {'Avg Worst %':<15} {'Max Worst %':<15} {'Min Worst %':<15}")
print("-" * 115)
for _, row in policy_summary.iterrows():
    policy_short = row['policy'].replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    print(f"{policy_short:<70} {row['avg_worst_loss_pct']:>13.3f}% {row['max_worst_loss_pct']:>13.3f}% {row['min_worst_loss_pct']:>13.3f}%")

# Create visualizations
fig, axes = plt.subplots(2, 2, figsize=(18, 12))
fig.suptitle('Worst-Case Performance Loss Analysis', fontsize=16, fontweight='bold')

# 1. Distribution of worst-case steps
ax1 = axes[0, 0]
step_hist = worst_case_df['worst_step'].value_counts().sort_index()
ax1.bar(step_hist.index, step_hist.values, width=1, alpha=0.7)
ax1.set_xlabel('Step (1M instructions)', fontsize=11)
ax1.set_ylabel('Frequency', fontsize=11)
ax1.set_title('Distribution of Worst-Case Steps', fontsize=12, fontweight='bold')
ax1.grid(axis='y', alpha=0.3)

# 2. Worst-case loss distribution per policy
ax2 = axes[0, 1]
policy_labels_short = [p.split('_')[-1] for p in all_policies[:8]]
worst_losses_by_policy = [worst_case_df[worst_case_df['policy'] == p]['worst_loss_pct'].values 
                          for p in all_policies[:8]]
bp = ax2.boxplot(worst_losses_by_policy, labels=policy_labels_short, patch_artist=True)
for patch in bp['boxes']:
    patch.set_facecolor('lightblue')
ax2.set_xticklabels(policy_labels_short, rotation=45, ha='right', fontsize=8)
ax2.set_ylabel('Worst-Case Loss (%)', fontsize=11)
ax2.set_title('Distribution of Worst-Case Losses by Policy', fontsize=12, fontweight='bold')
ax2.grid(axis='y', alpha=0.3)

# 3. Heatmap of worst-case losses
ax3 = axes[1, 0]
top_policies = policy_summary.head(8)['policy'].tolist()
pivot_worst = worst_case_df[worst_case_df['policy'].isin(top_policies)].pivot_table(
    values='worst_loss_pct', index='policy', columns='benchmark', aggfunc='first'
)
im = ax3.imshow(pivot_worst.values, cmap='YlOrRd', aspect='auto')
ax3.set_yticks(range(len(pivot_worst.index)))
ax3.set_yticklabels([p.split('_')[-1] for p in pivot_worst.index], fontsize=8)
ax3.set_xticks(range(0, len(pivot_worst.columns), 5))
ax3.set_xticklabels([pivot_worst.columns[i].split('-')[0][:10] for i in range(0, len(pivot_worst.columns), 5)], 
                     rotation=90, fontsize=7)
ax3.set_title('Worst-Case Loss Heatmap (Top 8 Policies)', fontsize=12, fontweight='bold')
plt.colorbar(im, ax=ax3, label='Worst Loss %')

# 4. Average worst-case loss per policy
ax4 = axes[1, 1]
y_pos = np.arange(len(policy_summary))
bars = ax4.barh(y_pos, policy_summary['avg_worst_loss_pct'])
ax4.set_yticks(y_pos)
policy_labels = [p.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/') 
                 for p in policy_summary['policy']]
ax4.set_yticklabels(policy_labels, fontsize=9)
ax4.set_xlabel('Average Worst-Case Loss (%)', fontsize=11)
ax4.set_title('Average Worst-Case Loss by Policy', fontsize=12, fontweight='bold')
ax4.grid(axis='x', alpha=0.3)
ax4.invert_yaxis()

# Add value labels
for i, (bar, val) in enumerate(zip(bars, policy_summary['avg_worst_loss_pct'])):
    ax4.text(val + 0.1, bar.get_y() + bar.get_height()/2, f'{val:.2f}%', 
             va='center', fontsize=8)

plt.tight_layout()
plt.savefig('worst_case_analysis.png', dpi=300, bbox_inches='tight')
print(f"\nVisualization saved to: worst_case_analysis.png")

print("\n" + "=" * 120)
print("KEY INSIGHTS")
print("=" * 120)
print(f"Best policy by worst-case loss: {policy_summary.iloc[0]['policy']}")
print(f"  - Average worst-case loss: {policy_summary.iloc[0]['avg_worst_loss_pct']:.3f}%")
print(f"  - Maximum worst-case loss: {policy_summary.iloc[0]['max_worst_loss_pct']:.3f}%")
print(f"\nWorst policy by worst-case loss: {policy_summary.iloc[-1]['policy']}")
print(f"  - Average worst-case loss: {policy_summary.iloc[-1]['avg_worst_loss_pct']:.3f}%")
print(f"  - Maximum worst-case loss: {policy_summary.iloc[-1]['max_worst_loss_pct']:.3f}%")
print(f"\nMost problematic step overall: Step {step_counts.iloc[0]['step']:.0f}")
print(f"  - Appears as worst-case {step_counts.iloc[0]['count']:.0f} times")
