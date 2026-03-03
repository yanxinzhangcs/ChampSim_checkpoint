import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Read the full-trace CSV file
df = pd.read_csv('policy_ipc_fulltrace_table.csv')

print("Analyzing full-trace IPC data...")
print("=" * 100)

# Get all policy columns (all except 'application')
policy_columns = [col for col in df.columns if col != 'application']

print(f"Found {len(policy_columns)} policies and {len(df)} benchmarks")
print(f"\nPolicies:")
for i, policy in enumerate(policy_columns, 1):
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    print(f"  {i}. {policy_short}")

# For each benchmark, find the best IPC
df['best_ipc'] = df[policy_columns].max(axis=1)

# For each policy, calculate loss percentage compared to best
policy_losses = {}

for policy in policy_columns:
    policy_short = policy.replace('l1d_prefetcher-', '').replace('_l1i_prefetcher-', '/').replace('_l2c_replacement-', '/')
    
    # Calculate loss percentage for each benchmark
    losses = ((df['best_ipc'] - df[policy]) / df['best_ipc'] * 100)
    policy_losses[policy_short] = losses.values

print("\n" + "=" * 100)
print("STATISTICS PER POLICY")
print("=" * 100)
print(f"\n{'Policy':<70} {'Median %':<12} {'Mean %':<12} {'Max %':<12} {'Min %':<12}")
print("-" * 106)

stats_data = []
for policy_short, losses in policy_losses.items():
    stats_data.append({
        'policy': policy_short,
        'median_loss': np.median(losses),
        'mean_loss': np.mean(losses),
        'max_loss': np.max(losses),
        'min_loss': np.min(losses),
        'std_loss': np.std(losses),
        'q25': np.percentile(losses, 25),
        'q75': np.percentile(losses, 75)
    })
    print(f"{policy_short:<70} {np.median(losses):>10.3f}% {np.mean(losses):>10.3f}% {np.max(losses):>10.3f}% {np.min(losses):>10.3f}%")

stats_df = pd.DataFrame(stats_data).sort_values('median_loss')
stats_df.to_csv('fulltrace_policy_statistics.csv', index=False)

# Create box plot visualization
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))
fig.suptitle('Full-Trace Performance Loss: Policy Comparison\n(One IPC Value per Application)', 
             fontsize=14, fontweight='bold')

# Box plot 1: All policies
policy_labels = [p.split('/')[-2] + '/' + p.split('/')[-1] if '/' in p else p for p in policy_losses.keys()]
box_data = list(policy_losses.values())

bp1 = ax1.boxplot(box_data, labels=policy_labels, patch_artist=True, 
                   showfliers=True, widths=0.6)

# Color the boxes
colors = ['lightblue', 'lightblue', 'lightblue', 'lightblue',
          'lightcoral', 'lightcoral', 'lightcoral', 'lightcoral']
for patch, color in zip(bp1['boxes'], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)

ax1.set_ylabel('Performance Loss (%)', fontsize=12, fontweight='bold')
ax1.set_xlabel('Policy (L1I/L2C)', fontsize=12, fontweight='bold')
ax1.set_title('Distribution of Performance Loss Across Benchmarks', fontsize=12, fontweight='bold')
ax1.grid(axis='y', alpha=0.3, linestyle='--')
ax1.axhline(y=0, color='green', linestyle='-', linewidth=1, alpha=0.5)

# Rotate labels
plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)

# Add legend for colors
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor='lightblue', alpha=0.7, label='berti L1D'),
                   Patch(facecolor='lightcoral', alpha=0.7, label='gaze L1D')]
ax1.legend(handles=legend_elements, loc='upper right', fontsize=9)

# Box plot 2: Sorted by median
sorted_policies = stats_df['policy'].tolist()
sorted_data = [policy_losses[p] for p in sorted_policies]
sorted_labels = [p.split('/')[-2] + '/' + p.split('/')[-1] if '/' in p else p for p in sorted_policies]

bp2 = ax2.boxplot(sorted_data, labels=sorted_labels, patch_artist=True,
                   showfliers=True, widths=0.6, vert=False)

# Color by L1D prefetcher
for i, (patch, policy) in enumerate(zip(bp2['boxes'], sorted_policies)):
    if 'berti' in policy:
        patch.set_facecolor('lightblue')
    else:
        patch.set_facecolor('lightcoral')
    patch.set_alpha(0.7)

ax2.set_xlabel('Performance Loss (%)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Policy (L1I/L2C)', fontsize=12, fontweight='bold')
ax2.set_title('Policies Ranked by Median Loss (Best to Worst)', fontsize=12, fontweight='bold')
ax2.grid(axis='x', alpha=0.3, linestyle='--')
ax2.axvline(x=0, color='green', linestyle='-', linewidth=1, alpha=0.5)
ax2.invert_yaxis()

# Rotate labels
plt.setp(ax2.yaxis.get_majorticklabels(), fontsize=9)

plt.tight_layout()
plt.savefig('fulltrace_policy_boxplot.png', dpi=300, bbox_inches='tight')
print(f"\nVisualization saved to: fulltrace_policy_boxplot.png")
print(f"Statistics saved to: fulltrace_policy_statistics.csv")

# Additional analysis
print("\n" + "=" * 100)
print("COMPONENT ANALYSIS")
print("=" * 100)

# Group by L1D prefetcher
berti_losses = [losses for policy, losses in policy_losses.items() if 'berti' in policy]
gaze_losses = [losses for policy, losses in policy_losses.items() if 'gaze' in policy]

print(f"\nL1D Prefetcher Comparison:")
print(f"  berti - Median: {np.median(np.concatenate(berti_losses)):.3f}%, Mean: {np.mean(np.concatenate(berti_losses)):.3f}%")
print(f"  gaze  - Median: {np.median(np.concatenate(gaze_losses)):.3f}%, Mean: {np.mean(np.concatenate(gaze_losses)):.3f}%")

# Group by L1I prefetcher
entangling_losses = [losses for policy, losses in policy_losses.items() if 'entangling' in policy]
barca_losses = [losses for policy, losses in policy_losses.items() if 'barca' in policy]

print(f"\nL1I Prefetcher Comparison:")
print(f"  entangling - Median: {np.median(np.concatenate(entangling_losses)):.3f}%, Mean: {np.mean(np.concatenate(entangling_losses)):.3f}%")
print(f"  barca      - Median: {np.median(np.concatenate(barca_losses)):.3f}%, Mean: {np.mean(np.concatenate(barca_losses)):.3f}%")

# Group by L2C replacement
mockingjay_losses = [losses for policy, losses in policy_losses.items() if 'mockingjay' in policy]
pacipv_losses = [losses for policy, losses in policy_losses.items() if 'PACIPV' in policy]

print(f"\nL2C Replacement Comparison:")
print(f"  mockingjay - Median: {np.median(np.concatenate(mockingjay_losses)):.3f}%, Mean: {np.mean(np.concatenate(mockingjay_losses)):.3f}%")
print(f"  PACIPV     - Median: {np.median(np.concatenate(pacipv_losses)):.3f}%, Mean: {np.mean(np.concatenate(pacipv_losses)):.3f}%")

print("\n" + "=" * 100)
print("KEY INSIGHTS")
print("=" * 100)
print(f"\nBest policy (lowest median loss): {stats_df.iloc[0]['policy']}")
print(f"  - Median loss: {stats_df.iloc[0]['median_loss']:.3f}%")
print(f"  - Mean loss: {stats_df.iloc[0]['mean_loss']:.3f}%")
print(f"  - Max loss: {stats_df.iloc[0]['max_loss']:.3f}%")

print(f"\nWorst policy (highest median loss): {stats_df.iloc[-1]['policy']}")
print(f"  - Median loss: {stats_df.iloc[-1]['median_loss']:.3f}%")
print(f"  - Mean loss: {stats_df.iloc[-1]['mean_loss']:.3f}%")
print(f"  - Max loss: {stats_df.iloc[-1]['max_loss']:.3f}%")
