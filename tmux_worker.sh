#!/usr/bin/env bash
set -euo pipefail

WORKER_ID="${1:-1}"

# 必须设置，否则会报 IPV not specified
export L2C_IPV="0 1 1 0 3#0 1 0 0 3"

# ====== 你给的实验参数（可按需改）======
CONFIG="rl_controller/action_space_perlbench_combo.json"
WARMUP=1000000
WINDOW=200000
RESUME_WARMUP=100
STEPS=100
EPSILON=0.1
SEED=0

# trace 放哪里：默认当前目录；如果你放在 traces/ 里，就改成 TRACE_DIR="traces"
TRACE_DIR="."

OUTROOT="rl_results"
LOGDIR="logs"
JOBS_FILE="jobs.txt"
LOCKFILE=".jobs.lock"
# ======================================

mkdir -p "$OUTROOT" "$LOGDIR"

while true; do
  TRACE_NAME=""

  # 原子取走 jobs.txt 第一行
  {
    flock -x 9
    if [[ ! -s "$JOBS_FILE" ]]; then
      echo "[$(date)] worker=$WORKER_ID: no more jobs, exit."
      exit 0
    fi
    TRACE_NAME="$(head -n 1 "$JOBS_FILE")"
    tail -n +2 "$JOBS_FILE" > "${JOBS_FILE}.tmp"
    mv "${JOBS_FILE}.tmp" "$JOBS_FILE"
  } 9>"$LOCKFILE"

  BASE="${TRACE_NAME%.champsimtrace.xz}"
  TRACE_PATH="${TRACE_DIR%/}/${TRACE_NAME}"
  OUTDIR="${OUTROOT}/${BASE}"
  LOGFILE="${LOGDIR}/${BASE}.w${WORKER_ID}.log"

  mkdir -p "$OUTDIR"

  echo "==================================================" | tee -a "$LOGFILE"
  echo "[$(date)] worker=$WORKER_ID start trace=$TRACE_NAME" | tee -a "$LOGFILE"
  echo "outdir=$OUTDIR" | tee -a "$LOGFILE"

  python3 -m rl_controller.experiments \
    --config "$CONFIG" \
    --trace "$TRACE_PATH" \
    --warmup "$WARMUP" \
    --window "$WINDOW" \
    --resume-warmup "$RESUME_WARMUP" \
    --steps "$STEPS" \
    --epsilon "$EPSILON" \
    --seed "$SEED" \
    --output "$OUTDIR" 2>&1 | tee -a "$LOGFILE"

  echo "[$(date)] worker=$WORKER_ID done trace=$TRACE_NAME" | tee -a "$LOGFILE"
done
