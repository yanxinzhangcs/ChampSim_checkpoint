#!/usr/bin/env bash
# Collect instruction feature/cycle datasets for the 9 advanced policy configurations.
#
# Usage:
#   scripts/collect_9_policy_traces.sh TRACE_FILE OUT_ROOT
#   scripts/collect_9_policy_traces.sh TRACE_DIR  OUT_ROOT
#
# Environment knobs:
#   WARMUP_INSTRUCTIONS=2000000
#   SIMULATION_INSTRUCTIONS=100000000
#   JOBS=$(nproc)
#   SKIP_EXISTING=1        # skip a policy if output.npy already exists
#   DELETE_COMMIT_CSV=0    # set to 1 after validating output.npy/input.npy

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  collect_9_policy_traces.sh TRACE_FILE OUT_ROOT
  collect_9_policy_traces.sh TRACE_DIR  OUT_ROOT

Collects 9-policy ChampSim commit traces and converts them into input.npy/output.npy.
If TRACE_DIR is provided, every *.champsimtrace.xz file under that directory is collected
into OUT_ROOT/<trace-name>/.
EOF
}

if [[ $# -ne 2 ]]; then
  usage >&2
  exit 2
fi

TRACE_INPUT="$1"
OUT_ROOT="$2"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

WARMUP_INSTRUCTIONS="${WARMUP_INSTRUCTIONS:-2000000}"
SIMULATION_INSTRUCTIONS="${SIMULATION_INSTRUCTIONS:-100000000}"
JOBS="${JOBS:-$(nproc)}"
SKIP_EXISTING="${SKIP_EXISTING:-1}"
DELETE_COMMIT_CSV="${DELETE_COMMIT_CSV:-0}"

POLICY_ORDER=(
  berti_barca_mock
  berti_barca_pacipv
  berti_entangle_mock
  berti_entangle_pacipv
  gaze_barca_mock
  gaze_barca_pacipv
  gaze_entangle_mock
  gaze_entangle_pacipv
  stride_stride_lru
)

declare -A CONFIGS=(
  [berti_barca_pacipv]="rl_controller/build_configs/champsim_rl_L1D-prefetcher-berti_L1I-prefetcher-barca_L2C-replacement-PACIPV.json"
  [berti_barca_mock]="rl_controller/build_configs/champsim_rl_L1D-prefetcher-berti_L1I-prefetcher-barca_L2C-replacement-mockingjay.json"
  [berti_entangle_pacipv]="rl_controller/build_configs/champsim_rl_L1D-prefetcher-berti_L1I-prefetcher-entangling_L2C-replacement-PACIPV.json"
  [berti_entangle_mock]="rl_controller/build_configs/champsim_rl_L1D-prefetcher-berti_L1I-prefetcher-entangling_L2C-replacement-mockingjay.json"
  [gaze_barca_pacipv]="rl_controller/build_configs/champsim_rl_L1D-prefetcher-gaze_L1I-prefetcher-barca_L2C-replacement-PACIPV.json"
  [gaze_barca_mock]="rl_controller/build_configs/champsim_rl_L1D-prefetcher-gaze_L1I-prefetcher-barca_L2C-replacement-mockingjay.json"
  [gaze_entangle_pacipv]="rl_controller/build_configs/champsim_rl_L1D-prefetcher-gaze_L1I-prefetcher-entangling_L2C-replacement-PACIPV.json"
  [gaze_entangle_mock]="rl_controller/build_configs/champsim_rl_L1D-prefetcher-gaze_L1I-prefetcher-entangling_L2C-replacement-mockingjay.json"
  [stride_stride_lru]="rl_controller/build_configs/champsim_rl_L1D-prefetcher-ip_stride_L1D-replacement-lru_L1I-prefetcher-ip_stride_L1I-replacement-lru_L2C-prefetcher-no_L2C-replacement-lru.json"
)

trace_name() {
  local trace="$1"
  local base
  base="$(basename "$trace")"
  base="${base%.champsimtrace.xz}"
  base="${base%.xz}"
  echo "$base"
}

json_executable_name() {
  local cfg="$1"
  python3 - "$cfg" <<'PYJSON'
import json
import sys
with open(sys.argv[1]) as f:
    print(json.load(f)["executable_name"])
PYJSON
}

write_manifest() {
  local run_root="$1"
  mkdir -p "$run_root"
  {
    echo -e "policy\tconfig_json"
    for policy in "${POLICY_ORDER[@]}"; do
      echo -e "${policy}\t${CONFIGS[$policy]}"
    done
  } > "${run_root}/policy_configs.tsv"
}

collect_one_trace() {
  local trace="$1"
  local run_root="$2"

  if [[ ! -f "$trace" ]]; then
    echo "ERROR: missing trace file: $trace" >&2
    exit 1
  fi

  mkdir -p "$run_root"
  write_manifest "$run_root"

  echo "=== trace: $trace ==="
  echo "=== output root: $run_root ==="
  echo "=== warmup: ${WARMUP_INSTRUCTIONS}, simulation: ${SIMULATION_INSTRUCTIONS}, jobs: ${JOBS} ==="

  for policy in "${POLICY_ORDER[@]}"; do
    local cfg="${CONFIGS[$policy]}"
    local out_dir="${run_root}/${policy}"

    if [[ ! -f "$cfg" ]]; then
      echo "ERROR: missing config for ${policy}: ${cfg}" >&2
      exit 1
    fi

    if [[ "$SKIP_EXISTING" == "1" && -f "${out_dir}/output.npy" && -f "${out_dir}/stats.json" ]]; then
      echo "=== skipping existing policy output: ${policy} ==="
      if [[ ! -f "${run_root}/input.npy" && -f "${out_dir}/input.npy" ]]; then
        cp "${out_dir}/input.npy" "${run_root}/input.npy"
      fi
      continue
    fi

    echo "=== building and collecting policy: ${policy} ==="
    echo "config: ${cfg}"

    ./config.sh "$cfg"
    make -j"$JOBS"

    local exe
    exe="$(json_executable_name "$cfg")"
    if [[ ! -x "./bin/${exe}" ]]; then
      echo "ERROR: expected executable not found: ./bin/${exe}" >&2
      exit 1
    fi

    mkdir -p "$out_dir"

    "./bin/${exe}" \
      --warmup-instructions "$WARMUP_INSTRUCTIONS" \
      --simulation-instructions "$SIMULATION_INSTRUCTIONS" \
      --commit-trace "${out_dir}/commit_trace" \
      --json "${out_dir}/stats.json" \
      "$trace"

    shopt -s nullglob
    local csvs=("${out_dir}"/commit_trace*.csv)
    shopt -u nullglob
    if [[ ${#csvs[@]} -eq 0 ]]; then
      echo "ERROR: no commit_trace*.csv files produced in ${out_dir}" >&2
      exit 1
    fi

    python3 post_processing/parse_champsim_commit_trace.py \
      "${csvs[@]}" \
      --out-dir "$out_dir"

    if [[ ! -f "${out_dir}/input.npy" || ! -f "${out_dir}/output.npy" ]]; then
      echo "ERROR: parser did not produce input.npy/output.npy in ${out_dir}" >&2
      exit 1
    fi

    if [[ ! -f "${run_root}/input.npy" ]]; then
      cp "${out_dir}/input.npy" "${run_root}/input.npy"
    fi

    if [[ "$DELETE_COMMIT_CSV" == "1" ]]; then
      rm -f "${csvs[@]}"
    fi
  done

  echo "=== done: ${run_root} ==="
  echo "Shared input: ${run_root}/input.npy"
  echo "Policy outputs: ${run_root}/<policy>/output.npy"
}

mkdir -p "$OUT_ROOT"

if [[ -d "$TRACE_INPUT" ]]; then
  shopt -s nullglob
  traces=("${TRACE_INPUT}"/*.champsimtrace.xz)
  shopt -u nullglob
  if [[ ${#traces[@]} -eq 0 ]]; then
    echo "ERROR: no *.champsimtrace.xz files found in ${TRACE_INPUT}" >&2
    exit 1
  fi
  for trace in "${traces[@]}"; do
    collect_one_trace "$trace" "${OUT_ROOT}/$(trace_name "$trace")"
  done
elif [[ -f "$TRACE_INPUT" ]]; then
  collect_one_trace "$TRACE_INPUT" "$OUT_ROOT"
else
  echo "ERROR: TRACE_INPUT is neither a file nor directory: ${TRACE_INPUT}" >&2
  exit 1
fi
