#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_ROOT="/hdd/chichau/current_projects"
ENV_ROOT="/home/chichau/miniconda3"
ENV_NAME="f713ctl"
CFG_DIR="${HOME}/.config/f713-control-plane"
CODEX_DIR="${HOME}/.codex"

mkdir -p "${REMOTE_ROOT}" "${CFG_DIR}" "${CODEX_DIR}"

source "${ENV_ROOT}/etc/profile.d/conda.sh"

if ! conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  conda create -n "${ENV_NAME}" python=3.11 nodejs git openssl -y
fi

conda activate "${ENV_NAME}"
npm install -g @openai/codex
pip install -e "${REPO_ROOT}"

echo "bootstrap complete"
