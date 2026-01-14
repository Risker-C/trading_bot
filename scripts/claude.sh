#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLAUDE_DATA_DIR="${REPO_ROOT}/.claude-data"

mkdir -p "${CLAUDE_DATA_DIR}"

export CLAUDE_CONFIG_DIR="${CLAUDE_DATA_DIR}"
DEFAULT_PERMISSION_MODE="${CLAUDE_CODE_PERMISSION_MODE:-default}"
export CLAUDE_CODE_PERMISSION_MODE="${DEFAULT_PERMISSION_MODE}"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  for arg in "$@"; do
    if [[ "${arg}" == "--dangerously-skip-permissions" ]]; then
      echo "Error: --dangerously-skip-permissions cannot be used when running as root." >&2
      echo "Use the default permission flow instead." >&2
      exit 1
    fi
  done
fi

permission_mode_set=false
for arg in "$@"; do
  if [[ "${arg}" == "--permission-mode" ]]; then
    permission_mode_set=true
    break
  elif [[ "${arg}" == --permission-mode=* ]]; then
    permission_mode_set=true
    break
  fi
done

if [[ "${permission_mode_set}" == false ]]; then
  set -- --permission-mode "${DEFAULT_PERMISSION_MODE}" "$@"
fi

exec claude "$@"
