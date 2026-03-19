#!/usr/bin/env bash
set -euo pipefail

NS="${1:-ns-srv}"
IFACE="${2:-veth-srv}"
GW_IP="${3:-10.0.0.1}"
DNS_IP="${4:-10.0.0.53}"

if [[ ${EUID} -ne 0 ]]; then
  echo "[!] Run as root (use sudo)."
  exit 1
fi

resolve_mac() {
  local ns="$1"
  local iface="$2"
  local ip="$3"

  ip netns exec "${ns}" ping -c 1 -W 1 "${ip}" >/dev/null 2>&1 || true
  ip netns exec "${ns}" ip neigh show "${ip}" dev "${iface}" | awk '{print $5; exit}'
}

set_static() {
  local ip="$1"
  local mac="$2"
  ip netns exec "${NS}" ip neigh replace "${ip}" lladdr "${mac}" nud permanent dev "${IFACE}"
}

main() {
  local gw_mac
  local dns_mac
  gw_mac="$(resolve_mac "${NS}" "${IFACE}" "${GW_IP}")"
  dns_mac="$(resolve_mac "${NS}" "${IFACE}" "${DNS_IP}")"

  if [[ -z "${gw_mac}" || -z "${dns_mac}" ]]; then
    echo "[!] Could not resolve required MAC addresses. Ensure lab is up and reachable."
    exit 1
  fi

  set_static "${GW_IP}" "${gw_mac}"
  set_static "${DNS_IP}" "${dns_mac}"

  echo "[+] Static ARP entries applied in ${NS}:${IFACE}"
  ip netns exec "${NS}" ip neigh show
}

main "$@"