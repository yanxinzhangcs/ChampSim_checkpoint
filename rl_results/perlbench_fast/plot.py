import json
from pathlib import Path

data = json.loads(Path("/home/ubuntu/yanxin/ChampSim_checkpoint/rl_results/perlbench_fast/experiment_summary.json").read_text())

policies = {
    "no":     data["fixed_policies"]["l2c_prefetcher-no_llc_replacement-lru"]["per_step_ipc"],
    "next_line": data["fixed_policies"]["l2c_prefetcher-next_line_llc_replacement-lru"]["per_step_ipc"],
    "ip_stride": data["fixed_policies"]["l2c_prefetcher-ip_stride_llc_replacement-lru"]["per_step_ipc"],
}

for step in range(len(policies["no"])):
    print(step, policies["no"][step], policies["next_line"][step], policies["ip_stride"][step])
