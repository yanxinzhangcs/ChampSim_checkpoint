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
else
  echo "[INFO] re-download trace: ${TRACE_NAME}"
  rm -f "${TRACE_PATH}" "${TRACE_PATH}.part"
  download_trace
  verify_trace
  echo "[INFO] trace verified: ${TRACE_PATH}"
fi

# 为该 trace 准备独立 config（按你的要求：复制并重命名）
if [[ ! -f "${CONFIG_SRC}" ]]; then
  echo "[ERROR] config source not found: ${CONFIG_SRC}" >&2
  exit 1
fi
cp -f "${CONFIG_SRC}" "${CONFIG_DST}"
echo "[INFO] per-trace config: ${CONFIG_DST}"

# 每个 trace 单独输出目录（你现在要求必须这么做）
mkdir -p "${OUTDIR}"
echo "[INFO] output dir: ${OUTDIR}"

# ===== 按你给的固定参数格式直接跑（仅替换 config 与 output）=====
python3 -m rl_controller.experiments \
  --config "${CONFIG_DST}" \
  --trace "${TRACE_PATH}" \
  --warmup 1000000 \
  --window 200000 \
  --resume-warmup 100 \
  --steps 100 \
  --epsilon 0.1 \
  --seed 0 \
  --output "${OUTDIR}"
