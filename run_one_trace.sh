#!/usr/bin/env bash
set -euo pipefail

# 用法：
#   ./run_one_trace.sh 600.perlbench_s-1273B.champsimtrace.xz

TRACE_NAME="${1:?usage: $0 <trace_file_name.champsimtrace.xz>}"
BASE_URL="https://dpc3.compas.cs.stonybrook.edu/champsim-traces/speccpu"

# 必须，不然会报 IPV not specified
export L2C_IPV="0 1 1 0 3#0 1 0 0 3"

# 只创建 traces 路径（按你的原要求）
TRACE_DIR="traces"
mkdir -p "$TRACE_DIR"

TRACE_PATH="${TRACE_DIR}/${TRACE_NAME}"
TRACE_URL="${BASE_URL}/${TRACE_NAME}"

# trace_name（去掉后缀）
TRACE_BASE="${TRACE_NAME%.champsimtrace.xz}"

# 每个 trace 单独的输出目录与 config
OUTDIR="rl_results/${TRACE_BASE}_combo"
CONFIG_SRC="rl_controller/action_space_perlbench_combo.json"
CONFIG_DST="rl_controller/action_space_${TRACE_BASE}_combo.json"

mkdir -p "${OUTDIR}"
LOGFILE="${OUTDIR}/run.log"
rm -f "${OUTDIR}/DONE" "${OUTDIR}/FAILED"

# 保存原始 stdout/stderr：只把精简进度输出到屏幕，其余全部写入 run.log
exec 3>&1 4>&2

term () {
  printf '%s\n' "$*" >&3
}

# 让 tmux 后台运行时也能保留完整日志，便于定位中途退出原因
exec >> "${LOGFILE}" 2>&1

START_TS="$(date)"
echo "[INFO] start: ${START_TS} trace=${TRACE_NAME} outdir=${OUTDIR}"
term "[INFO] start: ${START_TS} trace=${TRACE_NAME} outdir=${OUTDIR}"

MONITOR_PID=""

cleanup () {
  rc=$?
  if [[ -n "${MONITOR_PID:-}" ]]; then
    kill "${MONITOR_PID}" 2>/dev/null || true
    wait "${MONITOR_PID}" 2>/dev/null || true
  fi

  if (( rc == 0 )); then
    END_TS="$(date)"
    echo "[INFO] done: ${END_TS}"
    term "[INFO] done: ${END_TS} trace=${TRACE_NAME}"
    touch "${OUTDIR}/DONE"
  else
    END_TS="$(date)"
    echo "[ERROR] failed rc=${rc} at ${END_TS}"
    term "[ERROR] failed rc=${rc} at ${END_TS} trace=${TRACE_NAME} (see ${LOGFILE})"
    echo "${rc}" > "${OUTDIR}/FAILED"
  fi
}
trap cleanup EXIT

download_trace () {
  echo "[INFO] downloading: ${TRACE_URL}"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 3 --retry-delay 2 -o "${TRACE_PATH}.part" "${TRACE_URL}"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "${TRACE_PATH}.part" "${TRACE_URL}"
  else
    echo "[ERROR] need curl or wget" >&2
    exit 1
  fi
  mv "${TRACE_PATH}.part" "${TRACE_PATH}"
}

verify_trace () {
  if [[ ! -s "${TRACE_PATH}" ]]; then
    echo "[WARN] trace missing or empty: ${TRACE_PATH}"
    return 1
  fi
  if ! command -v xz >/dev/null 2>&1; then
    echo "[ERROR] xz not found; cannot verify .xz integrity" >&2
    exit 1
  fi
  if ! xz -t "${TRACE_PATH}" >/dev/null 2>&1; then
    echo "[WARN] xz integrity check failed: ${TRACE_PATH}"
    return 1
  fi
  return 0
}

# 下载 + 完整性检验
if verify_trace; then
  echo "[INFO] trace OK, skip download: ${TRACE_PATH}"
  term "[PROGRESS] trace=${TRACE_NAME} phase=verify_trace ok"
else
  echo "[INFO] re-download trace: ${TRACE_NAME}"
  term "[PROGRESS] trace=${TRACE_NAME} phase=download_trace"
  rm -f "${TRACE_PATH}" "${TRACE_PATH}.part"
  download_trace
  verify_trace
  echo "[INFO] trace verified: ${TRACE_PATH}"
  term "[PROGRESS] trace=${TRACE_NAME} phase=verify_trace ok"
fi

# 为该 trace 准备独立 config（按你的要求：复制并重命名）
if [[ ! -f "${CONFIG_SRC}" ]]; then
  echo "[ERROR] config source not found: ${CONFIG_SRC}" >&2
  exit 1
fi
cp -f "${CONFIG_SRC}" "${CONFIG_DST}"
echo "[INFO] per-trace config: ${CONFIG_DST}"
term "[PROGRESS] trace=${TRACE_NAME} phase=prepare_config ok"

# 每个 trace 单独输出目录（你现在要求必须这么做）
echo "[INFO] output dir: ${OUTDIR}"
term "[PROGRESS] trace=${TRACE_NAME} phase=experiments starting"

calc_action_count () {
  python3 - "$1" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
  data = json.load(handle)

count = 1
for head in data.get("heads", []):
  count *= len(head.get("choices", []))

print(count)
PY
}

monitor_progress () {
  local steps="$1"
  local action_count="$2"
  local outdir="$3"
  local trace_name="$4"

  local rl_total="${steps}"
  local baseline_total=$(( action_count * steps ))
  local grid_total=$(( action_count * steps ))

  local last_msg=""
  while true; do
    local phase=""
    local done=""
    local total=""

    shopt -s nullglob
    if [[ -f "${outdir}/experiment_summary.json" ]]; then
      phase="summary"
    elif [[ -d "${outdir}/per_step_grid" ]]; then
      phase="grid"
      local grid_files=( "${outdir}/per_step_grid"/step*_*.json )
      done="${#grid_files[@]}"
      total="${grid_total}"
    elif [[ -d "${outdir}/baseline" ]]; then
      phase="baseline"
      local baseline_files=( "${outdir}/baseline"/*/iter_*_stats.json )
      done="${#baseline_files[@]}"
      total="${baseline_total}"
    elif [[ -d "${outdir}/rl" ]]; then
      phase="rl"
      local rl_files=( "${outdir}/rl"/iter_*_stats.json )
      done="${#rl_files[@]}"
      total="${rl_total}"
    else
      phase="init"
    fi
    shopt -u nullglob

    local msg=""
    case "${phase}" in
      rl)
        msg="[PROGRESS] trace=${trace_name} phase=rl step=${done}/${total}"
        ;;
      baseline)
        msg="[PROGRESS] trace=${trace_name} phase=baseline window=${done}/${total}"
        ;;
      grid)
        msg="[PROGRESS] trace=${trace_name} phase=per_step_grid window=${done}/${total}"
        ;;
      summary)
        msg="[PROGRESS] trace=${trace_name} phase=summary writing"
        ;;
      init)
        msg="[PROGRESS] trace=${trace_name} phase=init"
        ;;
    esac

    if [[ "${msg}" != "${last_msg}" ]]; then
      term "${msg}"
      last_msg="${msg}"
    fi

    [[ "${phase}" == "summary" ]] && break
    sleep 30
  done
}

ACTION_COUNT="$(calc_action_count "${CONFIG_DST}")"
monitor_progress 100 "${ACTION_COUNT}" "${OUTDIR}" "${TRACE_NAME}" &
MONITOR_PID=$!

# ===== 按你给的固定参数格式直接跑（仅替换 config 与 output）=====
PY_RC=0
python3 -m rl_controller.experiments \
  --config "${CONFIG_DST}" \
  --trace "${TRACE_PATH}" \
  --warmup 1000000 \
  --window 200000 \
  --resume-warmup 100 \
  --steps 100 \
  --epsilon 0.1 \
  --seed 0 \
  --output "${OUTDIR}" || PY_RC=$?

exit "${PY_RC}"
