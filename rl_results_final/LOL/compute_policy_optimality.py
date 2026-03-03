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


# Get all benchmark names
benchmarks = [col for col in df.columns if col != 'step']

print("Computing policy optimality frequency...")
print("=" * 100)

# Count how many times each policy is best
policy_best_counts = {}
total_steps = 0

for benchmark in benchmarks:
    for idx, row in df.iterrows():
        step = row['step']
        cell_content = row[benchmark]
        
        best_policy, best_ipc, policy_dict = parse_cell(cell_content)
        
        if best_policy is None:
            continue
        
        # Increment counter for this policy
        if best_policy not in policy_best_counts:
            policy_best_counts[best_policy] = 0
        policy_best_counts[best_policy] += 1
        total_steps += 1

# Calculate percentages
policy_stats = []
for policy, count in policy_best_counts.items():
    percentage = (count / total_steps) * 100
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    policy_stats.append({
        'policy': policy,
        'policy_short': policy_short,
        'times_best': count,
        'percentage': percentage
    })

# Create DataFrame and sort by percentage
policy_stats_df = pd.DataFrame(policy_stats).sort_values('percentage', ascending=False)

# Save to CSV
policy_stats_df.to_csv('policy_optimality_frequency.csv', index=False)

# Print results
print(f"\nTotal time steps analyzed: {total_steps:,}")
print(f"Total benchmarks: {len(benchmarks)}")
print(f"Average steps per benchmark: {total_steps / len(benchmarks):.1f}")
print(f"\n{'Policy':<70} {'Times Best':<15} {'Percentage':<15}")
print("-" * 100)

for _, row in policy_stats_df.iterrows():
    print(f"{row['policy_short']:<70} {row['times_best']:>13,} {row['percentage']:>13.2f}%")

# Create visualization
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
fig.suptitle('Policy Optimality Frequency Across All Time Steps', fontsize=16, fontweight='bold')

# Pie chart
colors = plt.cm.Set3(np.linspace(0, 1, len(policy_stats_df)))
wedges, texts, autotexts = ax1.pie(policy_stats_df['percentage'], 
                                     labels=policy_stats_df['policy_short'],
                                     autopct='%1.1f%%',
                                     colors=colors,
                                     startangle=90)
ax1.set_title('Fraction of Time Each Policy is Optimal', fontsize=12, fontweight='bold')

# Make percentage text more readable
for autotext in autotexts:
    autotext.set_color('black')
    autotext.set_fontsize(9)
    autotext.set_fontweight('bold')

# Bar chart
ax2.barh(range(len(policy_stats_df)), policy_stats_df['percentage'], color=colors)
ax2.set_yticks(range(len(policy_stats_df)))
ax2.set_yticklabels(policy_stats_df['policy_short'], fontsize=9)
ax2.set_xlabel('Percentage of Time Steps (%)', fontsize=11, fontweight='bold')
ax2.set_title('Policy Optimality Ranking', fontsize=12, fontweight='bold')
ax2.grid(axis='x', alpha=0.3)
ax2.invert_yaxis()

# Add value labels on bars
for i, (val, count) in enumerate(zip(policy_stats_df['percentage'], policy_stats_df['times_best'])):
    ax2.text(val + 0.5, i, f'{val:.1f}% ({count:,})', va='center', fontsize=8)

plt.tight_layout()
plt.savefig('policy_optimality_frequency.png', dpi=300, bbox_inches='tight')
print(f"\nVisualization saved to: policy_optimality_frequency.png")
print(f"Statistics saved to: policy_optimality_frequency.csv")

# Additional analysis: Break down by L1D prefetcher
print("\n" + "=" * 100)
print("BREAKDOWN BY L1D PREFETCHER")
print("=" * 100)

berti_stats = policy_stats_df[policy_stats_df['policy'].str.contains('berti')]
gaze_stats = policy_stats_df[policy_stats_df['policy'].str.contains('gaze')]

berti_total = berti_stats['percentage'].sum()
gaze_total = gaze_stats['percentage'].sum()

print(f"\nberti L1D prefetcher: {berti_total:.2f}% of time steps")
print(f"gaze L1D prefetcher:  {gaze_total:.2f}% of time steps")
print(f"\nRatio: berti is optimal {berti_total/gaze_total:.2f}x more often than gaze")

# Breakdown by L1I prefetcher
print("\n" + "=" * 100)
print("BREAKDOWN BY L1I PREFETCHER")
print("=" * 100)

entangling_stats = policy_stats_df[policy_stats_df['policy'].str.contains('entangling')]
barca_stats = policy_stats_df[policy_stats_df['policy'].str.contains('barca')]

entangling_total = entangling_stats['percentage'].sum()
barca_total = barca_stats['percentage'].sum()

print(f"\nentangling L1I prefetcher: {entangling_total:.2f}% of time steps")
print(f"barca L1I prefetcher:      {barca_total:.2f}% of time steps")
print(f"\nRatio: entangling is optimal {entangling_total/barca_total:.2f}x more often than barca")

# Breakdown by L2C replacement
print("\n" + "=" * 100)
print("BREAKDOWN BY L2C REPLACEMENT POLICY")
print("=" * 100)

mockingjay_stats = policy_stats_df[policy_stats_df['policy'].str.contains('mockingjay')]
pacipv_stats = policy_stats_df[policy_stats_df['policy'].str.contains('PACIPV')]

mockingjay_total = mockingjay_stats['percentage'].sum()
pacipv_total = pacipv_stats['percentage'].sum()

print(f"\nmockingjay L2C replacement: {mockingjay_total:.2f}% of time steps")
print(f"PACIPV L2C replacement:     {pacipv_total:.2f}% of time steps")
print(f"\nRatio: mockingjay is optimal {mockingjay_total/pacipv_total:.2f}x more often than PACIPV")

print("\n" + "=" * 100)
print("KEY INSIGHTS")
print("=" * 100)
print(f"\nMost frequently optimal policy: {policy_stats_df.iloc[0]['policy_short']}")
print(f"  - Optimal for {policy_stats_df.iloc[0]['percentage']:.2f}% of all time steps")
print(f"  - Appears {policy_stats_df.iloc[0]['times_best']:,} times out of {total_steps:,} total")
print(f"\nLeast frequently optimal policy: {policy_stats_df.iloc[-1]['policy_short']}")
print(f"  - Optimal for only {policy_stats_df.iloc[-1]['percentage']:.2f}% of all time steps")
print(f"  - Appears {policy_stats_df.iloc[-1]['times_best']:,} times")
