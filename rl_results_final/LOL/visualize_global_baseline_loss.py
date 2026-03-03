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
print("GLOBAL BASELINE CHIP LOSS DISTRIBUTION")
print("="*100)
print("\nBaseline chip can dynamically choose between:")
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
                    pass
    
    return best_policy, best_ipc, policy_dict


# Collect all baseline vs oracle losses
print("\nCollecting baseline vs oracle losses across all timesteps...")

all_losses = []
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
        
        # Calculate loss percentage
        baseline_loss_pct = ((best_ipc - baseline_ipc) / best_ipc) * 100 if best_ipc > 0 else 0
        all_losses.append(baseline_loss_pct)

print(f"Collected {len(all_losses)} datapoints")

# Calculate statistics
print("\n" + "="*100)
print("SUMMARY STATISTICS")
print("="*100)
print(f"Total datapoints:     {len(all_losses)}")
print(f"Mean loss:            {np.mean(all_losses):.4f}%")
print(f"Median loss:          {np.median(all_losses):.4f}%")
print(f"Std deviation:        {np.std(all_losses):.4f}%")
print(f"Min loss:             {np.min(all_losses):.4f}%")
print(f"Max loss:             {np.max(all_losses):.4f}%")
print(f"25th percentile:      {np.percentile(all_losses, 25):.4f}%")
print(f"75th percentile:      {np.percentile(all_losses, 75):.4f}%")
print(f"90th percentile:      {np.percentile(all_losses, 90):.4f}%")
print(f"95th percentile:      {np.percentile(all_losses, 95):.4f}%")
print(f"99th percentile:      {np.percentile(all_losses, 99):.4f}%")

# Count perfect matches
perfect_count = sum(1 for loss in all_losses if abs(loss) < 0.001)
print(f"\nTimesteps where baseline = oracle: {perfect_count} ({100*perfect_count/len(all_losses):.2f}%)")

# Create a figure with multiple subplots
fig = plt.figure(figsize=(20, 12))
gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)

# 1. Box plot
ax1 = fig.add_subplot(gs[0, :])
bp = ax1.boxplot([all_losses], vert=False, patch_artist=True, widths=0.5,
                  showfliers=True, 
                  flierprops=dict(marker='o', markersize=2, alpha=0.3))
bp['boxes'][0].set_facecolor('lightblue')
bp['boxes'][0].set_alpha(0.7)
ax1.set_ylabel('Baseline Chip', fontsize=14, fontweight='bold')
ax1.set_xlabel('IPC Loss vs Oracle (%)', fontsize=14, fontweight='bold')
ax1.set_title('Global Distribution: Baseline Chip IPC Loss vs Oracle\nAcross All Benchmarks and Timesteps (N=4,900)', 
              fontsize=16, fontweight='bold')
ax1.axvline(x=0, color='green', linestyle='-', linewidth=2, alpha=0.7, label='Oracle Performance')
ax1.axvline(x=np.median(all_losses), color='red', linestyle='--', linewidth=2, alpha=0.7, 
            label=f'Median Loss = {np.median(all_losses):.3f}%')
ax1.grid(axis='x', alpha=0.3)
ax1.legend(fontsize=11)

# Add statistics box
stats_text = f'Mean: {np.mean(all_losses):.3f}%\nMedian: {np.median(all_losses):.3f}%\n'
stats_text += f'Std: {np.std(all_losses):.3f}%\nMax: {np.max(all_losses):.3f}%\n'
stats_text += f'95th %ile: {np.percentile(all_losses, 95):.3f}%'
ax1.text(0.98, 0.95, stats_text, transform=ax1.transAxes,
         verticalalignment='top', horizontalalignment='right',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
         fontsize=11, fontfamily='monospace')

# 2. Histogram (full range)
ax2 = fig.add_subplot(gs[1, 0])
n, bins, patches = ax2.hist(all_losses, bins=100, edgecolor='black', alpha=0.7, color='steelblue')
ax2.axvline(x=0, color='green', linestyle='-', linewidth=2, alpha=0.7, label='Oracle')
ax2.axvline(x=np.median(all_losses), color='red', linestyle='--', linewidth=2, alpha=0.7, 
            label=f'Median = {np.median(all_losses):.3f}%')
ax2.set_xlabel('IPC Loss vs Oracle (%)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Frequency (# of timesteps)', fontsize=12, fontweight='bold')
ax2.set_title('Histogram: Full Distribution', fontsize=13, fontweight='bold')
ax2.grid(axis='y', alpha=0.3)
ax2.legend(fontsize=10)

# 3. Histogram (zoomed to 0-2% range for detail)
ax3 = fig.add_subplot(gs[1, 1])
# Filter data for zoom
zoom_data = [l for l in all_losses if l <= 2.0]
n, bins, patches = ax3.hist(zoom_data, bins=100, edgecolor='black', alpha=0.7, color='coral')
ax3.axvline(x=0, color='green', linestyle='-', linewidth=2, alpha=0.7, label='Oracle')
ax3.axvline(x=np.median(all_losses), color='red', linestyle='--', linewidth=2, alpha=0.7, 
            label=f'Median = {np.median(all_losses):.3f}%')
ax3.set_xlabel('IPC Loss vs Oracle (%)', fontsize=12, fontweight='bold')
ax3.set_ylabel('Frequency (# of timesteps)', fontsize=12, fontweight='bold')
ax3.set_title(f'Histogram: Zoomed View (0-2%)\n{len(zoom_data)} of {len(all_losses)} timesteps shown ({100*len(zoom_data)/len(all_losses):.1f}%)', 
              fontsize=13, fontweight='bold')
ax3.set_xlim(0, 2.0)
ax3.grid(axis='y', alpha=0.3)
ax3.legend(fontsize=10)

# 4. Cumulative distribution
ax4 = fig.add_subplot(gs[2, 0])
sorted_losses = np.sort(all_losses)
cumulative = np.arange(1, len(sorted_losses) + 1) / len(sorted_losses) * 100
ax4.plot(sorted_losses, cumulative, linewidth=2, color='darkblue')
ax4.axvline(x=0, color='green', linestyle='-', linewidth=2, alpha=0.7, label='Oracle')
ax4.axhline(y=50, color='gray', linestyle=':', linewidth=1, alpha=0.5)
ax4.axvline(x=np.median(all_losses), color='red', linestyle='--', linewidth=2, alpha=0.7, 
            label=f'Median = {np.median(all_losses):.3f}%')
ax4.axhline(y=69.6, color='purple', linestyle='--', linewidth=2, alpha=0.7, 
            label='69.6% = Oracle match rate')
ax4.set_xlabel('IPC Loss vs Oracle (%)', fontsize=12, fontweight='bold')
ax4.set_ylabel('Cumulative Percentage (%)', fontsize=12, fontweight='bold')
ax4.set_title('Cumulative Distribution Function (CDF)', fontsize=13, fontweight='bold')
ax4.grid(True, alpha=0.3)
ax4.legend(fontsize=10)

# 5. Loss distribution by bins
ax5 = fig.add_subplot(gs[2, 1])
bins_ranges = ['0%', '0-0.1%', '0.1-0.5%', '0.5-1%', '1-2%', '2-5%', '>5%']
bin_counts = [
    sum(1 for l in all_losses if abs(l) < 0.001),
    sum(1 for l in all_losses if 0.001 <= l < 0.1),
    sum(1 for l in all_losses if 0.1 <= l < 0.5),
    sum(1 for l in all_losses if 0.5 <= l < 1.0),
    sum(1 for l in all_losses if 1.0 <= l < 2.0),
    sum(1 for l in all_losses if 2.0 <= l < 5.0),
    sum(1 for l in all_losses if l >= 5.0)
]
bin_percentages = [100 * c / len(all_losses) for c in bin_counts]

bars = ax5.barh(bins_ranges, bin_percentages, color='teal', alpha=0.7, edgecolor='black')
ax5.set_xlabel('Percentage of Timesteps (%)', fontsize=12, fontweight='bold')
ax5.set_title('Loss Distribution by Ranges', fontsize=13, fontweight='bold')
ax5.grid(axis='x', alpha=0.3)

# Add percentage labels on bars
for i, (bar, pct, count) in enumerate(zip(bars, bin_percentages, bin_counts)):
    ax5.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, 
             f'{pct:.1f}% (n={count})',
             va='center', fontsize=9, fontweight='bold')

plt.suptitle('Baseline Chip Performance Analysis: Global Distribution\n' +
             'Baseline = Dynamic switching between berti/entangling/mockingjay ↔ gaze/entangling/mockingjay',
             fontsize=14, fontweight='bold', y=0.995)

plt.savefig('baseline_global_loss_distribution.png', dpi=300, bbox_inches='tight')
print("\n" + "="*100)
print("VISUALIZATION SAVED")
print("="*100)
print("Saved: baseline_global_loss_distribution.png")

# Save summary statistics to CSV
summary_stats = {
    'metric': ['count', 'mean', 'median', 'std', 'min', 'max', 
               'p25', 'p50', 'p75', 'p90', 'p95', 'p99', 
               'perfect_match_count', 'perfect_match_pct'],
    'value': [
        len(all_losses),
        np.mean(all_losses),
        np.median(all_losses),
        np.std(all_losses),
        np.min(all_losses),
        np.max(all_losses),
        np.percentile(all_losses, 25),
        np.percentile(all_losses, 50),
        np.percentile(all_losses, 75),
        np.percentile(all_losses, 90),
        np.percentile(all_losses, 95),
        np.percentile(all_losses, 99),
        perfect_count,
        100 * perfect_count / len(all_losses)
    ]
}

summary_df = pd.DataFrame(summary_stats)
summary_df.to_csv('baseline_global_loss_summary.csv', index=False)
print("Saved: baseline_global_loss_summary.csv")

print("\n" + "="*100)
print("KEY INSIGHTS")
print("="*100)
print(f"* Baseline matches oracle at {perfect_count} timesteps ({100*perfect_count/len(all_losses):.2f}%)")
print(f"* Median loss is only {np.median(all_losses):.4f}%")
print(f"* 75% of timesteps have loss <= {np.percentile(all_losses, 75):.4f}%")
print(f"* 95% of timesteps have loss <= {np.percentile(all_losses, 95):.4f}%")
print(f"* Maximum loss observed: {np.max(all_losses):.4f}%")
print("\n" + "="*100)
