#!/usr/bin/env bash

# Quick smoke test that builds and runs a tiny ChampSim simulation for every
# branch predictor, prefetcher, and replacement policy available in this repo.
# Usage:
#   TRACE=path/to/trace.xz WARMUP=100000 SIM=200000 JOBS=4 ./policy_smoke_test.sh
# Positional arg overrides TRACE. Logs and generated configs are written under
# $LOG_DIR (default: policy_test_logs).

set -uo pipefail

TRACE=${1:-${TRACE:-600.perlbench_s-210B.champsimtrace.xz}}
BASE_CFG=${BASE_CFG:-champsim_config.json}
LOG_DIR=${LOG_DIR:-policy_test_logs}
WARMUP=${WARMUP:-100000}
SIM=${SIM:-200000}
JOBS=${JOBS:-$(nproc)}
BTB=${BTB:-basic_btb}
KEEP=KEEP

BRANCHES=(bimodal gshare perceptron hashed_perceptron)
PREFETCHERS=(no next_line ip_stride spp_dev va_ampm_lite barca berti)
REPLACEMENTS=(lru random srrip drrip ship mockingjay)

if [ ! -f "$BASE_CFG" ]; then
  echo "Base config not found: $BASE_CFG" >&2
  exit 1
fi

if [ ! -f "$TRACE" ]; then
  echo "Trace not found: $TRACE" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
failures=()

write_config() {
  local outfile=$1 exe=$2 branch=$3 btb=$4 pref=$5 repl=$6
  python3 - "$BASE_CFG" "$outfile" "$exe" "$branch" "$btb" "$pref" "$repl" <<'PY'
import json, sys
base_path, out_path, exe, branch, btb, pref, repl = sys.argv[1:]
cfg = json.load(open(base_path))

cfg["executable_name"] = exe

if branch != "KEEP":
    cfg["ooo_cpu"][0]["branch_predictor"] = branch
if btb != "KEEP":
    cfg["ooo_cpu"][0]["btb"] = btb
if pref != "KEEP":
    for level in ("L2C", "LLC"):
        if isinstance(cfg.get(level), dict) and "prefetcher" in cfg[level]:
            cfg[level]["prefetcher"] = pref
if repl != "KEEP":
    if isinstance(cfg.get("LLC"), dict):
        cfg["LLC"]["replacement"] = repl

with open(out_path, "w", encoding="utf-8") as fp:
    json.dump(cfg, fp, indent=2)
PY
}

run_case() {
  local label=$1 branch=$2 pref=$3 repl=$4
  local cfg_file="$LOG_DIR/${label}.json"
  local exe="champsim-${label}"

  write_config "$cfg_file" "$exe" "$branch" "$BTB" "$pref" "$repl"
  echo "[$label] branch=${branch/KEEP/base} pref=${pref/KEEP/base} repl=${repl/KEEP/base}"

  if ! ./config.sh "$cfg_file" > "$LOG_DIR/${label}.config.log" 2>&1; then
    echo "[$label] config failed (see $LOG_DIR/${label}.config.log)"
    failures+=("$label (config)")
    return
  fi

  if ! make -j"${JOBS}" > "$LOG_DIR/${label}.build.log" 2>&1; then
    echo "[$label] build failed (see $LOG_DIR/${label}.build.log)"
    failures+=("$label (build)")
    return
  fi

  if ! ./bin/"$exe" --warmup-instructions "$WARMUP" --simulation-instructions "$SIM" "$TRACE" \
      > "$LOG_DIR/${label}.run.log" 2>&1; then
    echo "[$label] run failed (see $LOG_DIR/${label}.run.log)"
    failures+=("$label (run)")
    return
  fi

  echo "[$label] PASS (logs in $LOG_DIR/${label}.*)"
}

for branch in "${BRANCHES[@]}"; do
  run_case "branch-${branch}" "$branch" "$KEEP" "$KEEP"
done

for pref in "${PREFETCHERS[@]}"; do
  run_case "prefetcher-${pref}" "$KEEP" "$pref" "$KEEP"
done

for repl in "${REPLACEMENTS[@]}"; do
  run_case "replacement-${repl}" "$KEEP" "$KEEP" "$repl"
done

if ((${#failures[@]})); then
  echo
  echo "Some policies failed:"
  printf '  - %s\n' "${failures[@]}"
  exit 1
fi

echo
echo "All policy smoke tests passed."
