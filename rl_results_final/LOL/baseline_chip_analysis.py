import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re

# Read the data
print("Loading data...")
df_fulltrace = pd.read_csv('policy_ipc_fulltrace_table.csv')
df_timesteps = pd.read_csv('policy_ipc_table.csv')

# Define the two baseline policy sets
BASELINE_POLICIES = [
    'l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay',
    'l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay'
]

print(f"Baseline chip has access to these two policies:")
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
                ipc_value = float(parts[1].strip())
                policy_dict[policy_name] = ipc_value
    
    return best_policy, best_ipc, policy_dict


def analyze_baseline_vs_oracle(df_timesteps):
    """
    For each application and time step:
    1. Find the oracle IPC (best policy at that time step)
    2. Find the baseline IPC (best of the two baseline policies)
    3. Calculate loss percentage
    """
    benchmarks = [col for col in df_timesteps.columns if col != 'step']
    
    results = {}
    
    for benchmark in benchmarks:
        print(f"Processing {benchmark}...")
        
        oracle_losses = []
        baseline_losses = []
        
        for idx, row in df_timesteps.iterrows():
            cell_content = row[benchmark]
            best_policy, best_ipc, policy_dict = parse_cell(cell_content)
            
            if best_policy is None or best_ipc is None:
                continue
            
            # Oracle IPC is the best IPC (0% loss by definition)
            oracle_ipc = best_ipc
            
            # Baseline IPC is the best of the two baseline policies
            baseline_ipcs = [policy_dict.get(p, 0) for p in BASELINE_POLICIES if p in policy_dict]
            if not baseline_ipcs:
                continue
            baseline_ipc = max(baseline_ipcs)
            
            # Calculate loss percentage for baseline
            baseline_loss_pct = ((oracle_ipc - baseline_ipc) / oracle_ipc) * 100 if oracle_ipc > 0 else 0
            
            oracle_losses.append(0.0)  # Oracle always 0% loss
            baseline_losses.append(baseline_loss_pct)
        
        results[benchmark] = {
            'oracle_losses': oracle_losses,
            'baseline_losses': baseline_losses
        }
    
    return results, benchmarks


def analyze_baseline_vs_oracle_fulltrace(df_fulltrace):
    """
    Analyze for full trace results (single IPC per application)
    """
    applications = df_fulltrace['application'].values
    
    results = {}
    
    for app in applications:
        app_data = df_fulltrace[df_fulltrace['application'] == app].iloc[0]
        
        # Get IPC values
        all_ipcs = {}
        for col in df_fulltrace.columns:
            if col != 'application':
                all_ipcs[col] = app_data[col]
        
        # Oracle IPC (best overall)
        oracle_ipc = max(all_ipcs.values())
        
        # Baseline IPC (best of two policies)
        baseline_ipcs = [all_ipcs.get(p, 0) for p in BASELINE_POLICIES if p in all_ipcs]
        baseline_ipc = max(baseline_ipcs) if baseline_ipcs else 0
        
        # Calculate loss
        baseline_loss_pct = ((oracle_ipc - baseline_ipc) / oracle_ipc) * 100 if oracle_ipc > 0 else 0
        
        results[app] = {
            'oracle_ipc': oracle_ipc,
            'baseline_ipc': baseline_ipc,
            'baseline_loss_pct': baseline_loss_pct
        }
    
    return results, applications


print("\n" + "="*100)
print("ANALYZING TIME STEP DATA (policy_ipc_table.csv)")
print("="*100)

results_timesteps, benchmarks = analyze_baseline_vs_oracle(df_timesteps)

# Create box plots for each application
print("\nCreating box plots per application...")

# Calculate the number of subplots needed
n_apps = len(benchmarks)
n_cols = 7
n_rows = (n_apps + n_cols - 1) // n_cols

fig, axes = plt.subplots(n_rows, n_cols, figsize=(28, 4 * n_rows))
axes = axes.flatten()

for idx, benchmark in enumerate(benchmarks):
    ax = axes[idx]
    
    oracle_losses = results_timesteps[benchmark]['oracle_losses']
    baseline_losses = results_timesteps[benchmark]['baseline_losses']
    
    # Skip if no data
    if len(baseline_losses) == 0:
        ax.text(0.5, 0.5, 'No Data', ha='center', va='center', transform=ax.transAxes)
        ax.set_title(benchmark.split('-')[0][:15], fontsize=9)
        continue
    
    # Create box plot
    bp = ax.boxplot([oracle_losses, baseline_losses], 
                     labels=['Oracle\n(Always Best)', 'Baseline\n(2 Policies)'],
                     patch_artist=True, 
                     widths=0.5)
    
    # Color the boxes
    colors = ['lightgreen', 'lightcoral']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    # Styling
    benchmark_short = benchmark.split('-')[0][:15]
    ax.set_title(f'{benchmark_short}', fontsize=9, fontweight='bold')
    ax.set_ylabel('IPC Loss (%)', fontsize=8)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.axhline(y=0, color='green', linestyle='-', linewidth=1, alpha=0.5)
    
    # Add statistics
    median_baseline = np.median(baseline_losses)
    mean_baseline = np.mean(baseline_losses)
    max_baseline = np.max(baseline_losses)
    
    stats_text = f'Med: {median_baseline:.2f}%\nMean: {mean_baseline:.2f}%\nMax: {max_baseline:.2f}%'
    ax.text(0.98, 0.97, stats_text, transform=ax.transAxes,
            ha='right', va='top', fontsize=7,
            bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))

# Remove extra subplots
for idx in range(len(benchmarks), len(axes)):
    fig.delaxes(axes[idx])

plt.suptitle('IPC Loss Distribution: Oracle vs Baseline Chip (berti|gaze / entangling / mockingjay)\n' + 
             'Baseline chip can choose between two policies at each time step',
             fontsize=14, fontweight='bold', y=0.995)

plt.tight_layout()
plt.savefig('baseline_vs_oracle_boxplots.png', dpi=200, bbox_inches='tight')
print("Saved: baseline_vs_oracle_boxplots.png")

# Create summary statistics
print("\n" + "="*100)
print("SUMMARY STATISTICS: BASELINE CHIP PERFORMANCE")
print("="*100)

stats_data = []
for benchmark in benchmarks:
    baseline_losses = results_timesteps[benchmark]['baseline_losses']
    
    # Skip if no data
    if len(baseline_losses) == 0:
        continue
    
    stats_data.append({
        'benchmark': benchmark,
        'median_loss': np.median(baseline_losses),
        'mean_loss': np.mean(baseline_losses),
        'std_loss': np.std(baseline_losses),
        'min_loss': np.min(baseline_losses),
        'max_loss': np.max(baseline_losses),
        'q25_loss': np.percentile(baseline_losses, 25),
        'q75_loss': np.percentile(baseline_losses, 75),
        'iqr_loss': np.percentile(baseline_losses, 75) - np.percentile(baseline_losses, 25),
        'num_steps': len(baseline_losses)
    })

stats_df = pd.DataFrame(stats_data)

if len(stats_df) > 0:
    stats_df = stats_df.sort_values('median_loss', ascending=False)
    stats_df.to_csv('baseline_chip_statistics.csv', index=False)
    print("Saved: baseline_chip_statistics.csv")

    print("\nTop 10 applications with HIGHEST median loss (baseline vs oracle):")
    print(stats_df.head(10)[['benchmark', 'median_loss', 'mean_loss', 'max_loss']].to_string(index=False))

    print("\nTop 10 applications with LOWEST median loss (baseline vs oracle):")
    print(stats_df.tail(10)[['benchmark', 'median_loss', 'mean_loss', 'max_loss']].to_string(index=False))

    print("\nOverall statistics across ALL applications and time steps:")
    all_baseline_losses = [loss for bench in benchmarks 
                          for loss in results_timesteps[bench]['baseline_losses'] 
                          if len(results_timesteps[bench]['baseline_losses']) > 0]
    if len(all_baseline_losses) > 0:
        print(f"  Median loss: {np.median(all_baseline_losses):.3f}%")
        print(f"  Mean loss: {np.mean(all_baseline_losses):.3f}%")
        print(f"  Std dev: {np.std(all_baseline_losses):.3f}%")
        print(f"  Max loss: {np.max(all_baseline_losses):.3f}%")
        print(f"  75th percentile: {np.percentile(all_baseline_losses, 75):.3f}%")
        print(f"  95th percentile: {np.percentile(all_baseline_losses, 95):.3f}%")
else:
    print("WARNING: No valid timestep data found for analysis")


# Analyze full trace data
print("\n" + "="*100)
print("ANALYZING FULL TRACE DATA (policy_ipc_fulltrace_table.csv)")
print("="*100)

results_fulltrace, applications = analyze_baseline_vs_oracle_fulltrace(df_fulltrace)

fulltrace_stats = []
for app in applications:
    fulltrace_stats.append({
        'application': app,
        'oracle_ipc': results_fulltrace[app]['oracle_ipc'],
        'baseline_ipc': results_fulltrace[app]['baseline_ipc'],
        'baseline_loss_pct': results_fulltrace[app]['baseline_loss_pct']
    })

fulltrace_df = pd.DataFrame(fulltrace_stats)
fulltrace_df = fulltrace_df.sort_values('baseline_loss_pct', ascending=False)
fulltrace_df.to_csv('baseline_chip_fulltrace_statistics.csv', index=False)
print("Saved: baseline_chip_fulltrace_statistics.csv")

print("\nTop 10 applications with HIGHEST loss (full trace baseline vs oracle):")
print(fulltrace_df.head(10).to_string(index=False))

print("\nTop 10 applications with LOWEST loss (full trace baseline vs oracle):")
print(fulltrace_df.tail(10).to_string(index=False))

print("\nOverall full trace statistics:")
print(f"  Median loss: {np.median(fulltrace_df['baseline_loss_pct']):.3f}%")
print(f"  Mean loss: {np.mean(fulltrace_df['baseline_loss_pct']):.3f}%")
print(f"  Std dev: {np.std(fulltrace_df['baseline_loss_pct']):.3f}%")
print(f"  Max loss: {np.max(fulltrace_df['baseline_loss_pct']):.3f}%")

print("\n" + "="*100)
print("ANALYSIS COMPLETE")
print("="*100)
