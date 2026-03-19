#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNTIME_DIR="${ROOT_DIR}/.netlab-runtime"

NS=(ns-atk ns-def ns-srv ns-dns)
BRIDGE="br-lab"

require_root() {
  if [[ ${EUID} -ne 0 ]]; then
    echo "[!] Run as root (use sudo)."
    exit 1
  fi
}

stop_pid_file() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]]; then
    local pid
    pid="$(cat "${pid_file}")"
    if kill -0 "${pid}" >/dev/null 2>&1; then
      kill "${pid}" >/dev/null 2>&1 || true
      sleep 0.2
      kill -9 "${pid}" >/dev/null 2>&1 || true
    fi
    rm -f "${pid_file}"
  fi
}

stop_services() {
  stop_pid_file "${RUNTIME_DIR}/http-server.pid"
  stop_pid_file "${RUNTIME_DIR}/dnsmasq.pid"

  # Fallback cleanup for stale process invocations.
  pkill -f 'lab/services/http-server.py' >/dev/null 2>&1 || true
  pkill -f 'dnsmasq --conf-file=.*/lab/services/dns-server.conf' >/dev/null 2>&1 || true
}

delete_namespaces() {
  local ns
  for ns in "${NS[@]}"; do
    if ip netns list | awk '{print $1}' | grep -qx "${ns}"; then
      ip netns del "${ns}" || true
    fi
  done
}

delete_bridge() {
  if ip link show "${BRIDGE}" >/dev/null 2>&1; then
    ip link del "${BRIDGE}" || true
  fi
}

main() {
  require_root
  stop_services
  delete_namespaces
  delete_bridge
  rm -rf "${RUNTIME_DIR}"
  echo "[+] Netlab teardown complete"
}

main "$@"