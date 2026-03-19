#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNTIME_DIR="${ROOT_DIR}/.netlab-runtime"

NS=(ns-atk ns-def ns-srv ns-dns)
BRIDGE="br-lab"

print_header() {
  echo "===================="
  echo "Netlab Status"
  echo "===================="
}

print_namespaces() {
  printf "\n[Namespaces]\n"
  ip netns list || true
}

print_ns_network() {
  local ns="$1"
  if ! ip netns list | awk '{print $1}' | grep -qx "${ns}"; then
    printf "\n[%s] not found\n" "${ns}"
    return
  fi

  printf "\n[%s]\n" "${ns}"
  ip netns exec "${ns}" ip -br addr show || true
  ip netns exec "${ns}" ip route show || true
}

print_bridge() {
  printf "\n[Bridge %s]\n" "${BRIDGE}"
  if ip link show "${BRIDGE}" >/dev/null 2>&1; then
    ip -br addr show dev "${BRIDGE}" || true
    bridge link show master "${BRIDGE}" || true
  else
    echo "Bridge ${BRIDGE} not found"
  fi
}

print_service() {
  local name="$1"
  local pid_file="$2"

  if [[ -f "${pid_file}" ]]; then
    local pid
    pid="$(cat "${pid_file}")"
    if kill -0 "${pid}" >/dev/null 2>&1; then
      echo "  ${name}: running (pid ${pid})"
      return
    fi
  fi
  echo "  ${name}: not running"
}

print_services() {
  printf "\n[Services]\n"
  print_service "http-server" "${RUNTIME_DIR}/http-server.pid"
  print_service "dnsmasq" "${RUNTIME_DIR}/dnsmasq.pid"
}

main() {
  print_header
  print_namespaces
  local ns
  for ns in "${NS[@]}"; do
    print_ns_network "${ns}"
  done
  print_bridge
  print_services
}

main "$@"