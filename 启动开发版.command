#!/bin/zsh

set -u

PROJECT_DIR="${0:A:h}"
LOCAL_PYTHON="${PROJECT_DIR}/.venv/bin/python"
CONFIGURED_PYTHON="${GENETIC_IMPROVE_PYTHON:-}"

if [[ -n "${CONFIGURED_PYTHON}" && -x "${CONFIGURED_PYTHON}" ]]; then
    PYTHON_BIN="${CONFIGURED_PYTHON}"
elif [[ -x "${LOCAL_PYTHON}" ]]; then
    PYTHON_BIN="${LOCAL_PYTHON}"
else
    echo "没有找到项目 Python 环境。"
    echo "请先在项目目录创建 .venv，或设置环境变量："
    echo "GENETIC_IMPROVE_PYTHON=/path/to/python"
    read -r "?按回车键关闭..."
    exit 1
fi

export MPLCONFIGDIR="${TMPDIR:-/private/tmp}/genetic-improve-matplotlib"
mkdir -p "${MPLCONFIGDIR}"

cd "${PROJECT_DIR}" || exit 1
exec "${PYTHON_BIN}" main.py
