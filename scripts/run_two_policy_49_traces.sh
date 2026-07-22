#!/usr/bin/env bash
set -uo pipefail

BASE_URL="${BASE_URL:-https://dpc3.compas.cs.stonybrook.edu/champsim-traces/speccpu}"
CONFIG="${CONFIG:-rl_controller/action_space_two_policy_l1d_barca_pacipv.json}"
TRACE_LIST="${TRACE_LIST:-jobs.txt}"
TRACE_DIR="${TRACE_DIR:-traces}"
OUTPUT_ROOT="${OUTPUT_ROOT:-rl_real_two_policy/49_traces}"
WARMUP="${WARMUP:-1000000}"
WINDOW="${WINDOW:-200000}"
RESUME_WARMUP="${RESUME_WARMUP:-100}"
STEPS="${STEPS:-100}"
AGENT="${AGENT:-epsilon_greedy}"
EPSILON="${EPSILON:-0.1}"
SEED="${SEED:-0}"
RUN_GRID="${RUN_GRID:-1}"
COMPARE_LIMIT="${COMPARE_LIMIT:-}"
export L2C_IPV="${L2C_IPV:-0 1 1 0 3#0 1 0 0 3}"

mkdir -p "$TRACE_DIR" "$OUTPUT_ROOT/logs"

cat > "$OUTPUT_ROOT/manifest.txt" <<MANIFEST
config=$CONFIG
trace_list=$TRACE_LIST
trace_dir=$TRACE_DIR
warmup=$WARMUP
window=$WINDOW
resume_warmup=$RESUME_WARMUP
steps=$STEPS
agent=$AGENT
epsilon=$EPSILON
seed=$SEED
run_grid=$RUN_GRID
compare_limit=$COMPARE_LIMIT
l2c_ipv=$L2C_IPV
MANIFEST

total=$(wc -l < "$TRACE_LIST" | tr -d ' ')
index=0

while IFS= read -r trace || [ -n "$trace" ]; do
  [ -z "$trace" ] && continue
  index=$((index + 1))

  name="${trace%.champsimtrace.xz}"
  trace_path="$TRACE_DIR/$trace"
  trace_out="$OUTPUT_ROOT/$name"
  log_path="$OUTPUT_ROOT/logs/$name.log"
  done_path="$trace_out/DONE"
  failed_path="$trace_out/FAILED"

  mkdir -p "$trace_out"
  rm -f "$failed_path"

  if [ -f "$done_path" ] && [ -f "$trace_out/experiment_summary.json" ]; then
    echo "[$index/$total] skip completed $trace"
    continue
  fi

  echo "[$index/$total] start $trace"

  if [ ! -s "$trace_path" ]; then
    echo "[$index/$total] download $trace"
    if ! curl -L --fail --retry 3 --retry-delay 5 -o "$trace_path.tmp" "$BASE_URL/$trace"; then
      echo "download failed: $trace" | tee "$failed_path"
      rm -f "$trace_path.tmp"
      continue
    fi
    mv "$trace_path.tmp" "$trace_path"
  fi

  if command -v xz >/dev/null 2>&1; then
    if ! xz -t "$trace_path"; then
      echo "xz validation failed: $trace" | tee "$failed_path"
      continue
    fi
  fi

  cmd=(
    python3 -m rl_controller.experiments
    --config "$CONFIG"
    --trace "$trace_path"
    --warmup "$WARMUP"
    --window "$WINDOW"
    --resume-warmup "$RESUME_WARMUP"
    --steps "$STEPS"
    --agent "$AGENT"
    --epsilon "$EPSILON"
    --seed "$SEED"
    --output "$trace_out"
  )

  if [ "$RUN_GRID" = "0" ]; then
    cmd+=(--skip-grid)
  elif [ -n "$COMPARE_LIMIT" ]; then
    cmd+=(--compare-limit "$COMPARE_LIMIT")
  fi

  if "${cmd[@]}" > "$log_path" 2>&1; then
    touch "$done_path"
    echo "[$index/$total] done $trace"
  else
    status=$?
    echo "experiment failed with status $status: $trace" | tee "$failed_path"
  fi
done < "$TRACE_LIST"

echo "batch finished"
