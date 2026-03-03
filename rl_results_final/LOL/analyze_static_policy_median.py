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


# Target policy: berti/entangling/mockingjay
target_policy = 'l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay'
target_policy_short = 'berti/entangling/mockingjay'

print(f"Analyzing static policy: {target_policy_short}")
print("=" * 100)

# Get all benchmark names
benchmarks = [col for col in df.columns if col != 'step']

# Store median loss for each benchmark
benchmark_median_losses = []

for benchmark in benchmarks:
    losses = []
    
    for idx, row in df.iterrows():
        cell_content = row[benchmark]
        best_policy, best_ipc, policy_dict = parse_cell(cell_content)
        
        if best_policy is None or target_policy not in policy_dict:
            continue
        
        # Calculate loss at this time step
        target_ipc = policy_dict[target_policy]
        loss_pct = ((best_ipc - target_ipc) / best_ipc) * 100 if best_ipc > 0 else 0
        losses.append(loss_pct)
    
    if len(losses) > 0:
        median_loss = np.median(losses)
        benchmark_median_losses.append({
            'benchmark': benchmark,
            'median_loss_pct': median_loss,
            'mean_loss_pct': np.mean(losses),
            'min_loss_pct': np.min(losses),
            'max_loss_pct': np.max(losses),
            'num_steps': len(losses)
        })

# Create DataFrame
results_df = pd.DataFrame(benchmark_median_losses).sort_values('median_loss_pct', ascending=False)

# Save to CSV
results_df.to_csv(f'static_policy_median_loss_{target_policy_short.replace("/", "_")}.csv', index=False)

# Print statistics
print(f"\nAnalyzed {len(results_df)} benchmarks")
print(f"\nBenchmarks ranked by median loss (highest to lowest):")
print(f"\n{'Benchmark':<30} {'Median Loss %':<15} {'Mean Loss %':<15} {'Max Loss %':<15}")
print("-" * 75)

for _, row in results_df.head(20).iterrows():
    print(f"{row['benchmark']:<30} {row['median_loss_pct']:>13.3f}% {row['mean_loss_pct']:>13.3f}% {row['max_loss_pct']:>13.3f}%")

print("\n...")
print(f"\nBenchmarks with LOWEST median loss:")
print(f"\n{'Benchmark':<30} {'Median Loss %':<15} {'Mean Loss %':<15} {'Min Loss %':<15}")
print("-" * 75)

for _, row in results_df.tail(10).iterrows():
    print(f"{row['benchmark']:<30} {row['median_loss_pct']:>13.3f}% {row['mean_loss_pct']:>13.3f}% {row['min_loss_pct']:>13.3f}%")

# Create visualization
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
fig.suptitle(f'Performance Analysis: Static Policy "{target_policy_short}"', 
             fontsize=14, fontweight='bold')

# Single box plot of median losses
ax1.boxplot([results_df['median_loss_pct']], labels=['Median Loss\nAcross Benchmarks'], 
            patch_artist=True, widths=0.5, showfliers=True)
ax1.set_ylabel('Median IPC Loss (%)', fontsize=12, fontweight='bold')
ax1.set_title('Distribution of Median Losses\n(One Value per Benchmark)', 
              fontsize=12, fontweight='bold')
ax1.grid(axis='y', alpha=0.3)

# Add statistics text
median_of_medians = np.median(results_df['median_loss_pct'])
mean_of_medians = np.mean(results_df['median_loss_pct'])
max_median = np.max(results_df['median_loss_pct'])
min_median = np.min(results_df['median_loss_pct'])

stats_text = f'Median of medians: {median_of_medians:.3f}%\nMean of medians: {mean_of_medians:.3f}%\n'
stats_text += f'Range: {min_median:.3f}% to {max_median:.3f}%'
ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes,
         verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7),
         fontsize=10)

# Bar chart of median losses per benchmark
ax2.barh(range(len(results_df)), results_df['median_loss_pct'], color='steelblue', alpha=0.7)
ax2.set_yticks(range(0, len(results_df), max(1, len(results_df)//15)))  # Show ~15 labels
ax2.set_yticklabels([results_df.iloc[i]['benchmark'].split('-')[0][:15] 
                      for i in range(0, len(results_df), max(1, len(results_df)//15))], fontsize=7)
ax2.set_xlabel('Median IPC Loss (%)', fontsize=11, fontweight='bold')
ax2.set_title('Median Loss by Benchmark (sorted)', fontsize=12, fontweight='bold')
ax2.grid(axis='x', alpha=0.3)
ax2.invert_yaxis()

# Add horizontal line at y=0
ax2.axvline(x=0, color='green', linestyle='-', linewidth=1.5, alpha=0.7)

plt.tight_layout()
plt.savefig(f'static_policy_median_analysis_{target_policy_short.replace("/", "_")}.png', 
            dpi=300, bbox_inches='tight')

print(f"\nVisualization saved to: static_policy_median_analysis_{target_policy_short.replace('/', '_')}.png")
print(f"Data saved to: static_policy_median_loss_{target_policy_short.replace('/', '_')}.csv")

# Summary statistics
print("\n" + "=" * 100)
print("SUMMARY STATISTICS")
print("=" * 100)
print(f"\nDistribution of median losses across {len(results_df)} benchmarks:")
print(f"  Median of medians: {median_of_medians:.3f}%")
print(f"  Mean of medians:   {mean_of_medians:.3f}%")
print(f"  Std dev:           {np.std(results_df['median_loss_pct']):.3f}%")
print(f"  Min median:        {min_median:.3f}%")
print(f"  Max median:        {max_median:.3f}%")
print(f"  Q1 (25th):         {np.percentile(results_df['median_loss_pct'], 25):.3f}%")
print(f"  Q3 (75th):         {np.percentile(results_df['median_loss_pct'], 75):.3f}%")

# How many benchmarks have median loss < 1%?
low_loss = len(results_df[results_df['median_loss_pct'] < 1.0])
print(f"\nBenchmarks with median loss < 1%: {low_loss} / {len(results_df)} ({low_loss/len(results_df)*100:.1f}%)")

high_loss = len(results_df[results_df['median_loss_pct'] > 5.0])
print(f"Benchmarks with median loss > 5%: {high_loss} / {len(results_df)} ({high_loss/len(results_df)*100:.1f}%)")

print("\n" + "=" * 100)
print("INTERPRETATION")
print("=" * 100)
print(f"\nStatic policy '{target_policy_short}' performance:")
print(f"  - Works well (median < 1%) for {low_loss} benchmarks")
print(f"  - Struggles (median > 5%) with {high_loss} benchmarks")
print(f"  - Overall median loss: {median_of_medians:.3f}%")
print(f"\nThis shows how a single static policy performs differently across workloads.")
