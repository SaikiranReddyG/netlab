#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-ns-srv}"

if [[ ${EUID} -ne 0 ]]; then
  echo "[!] Run as root (use sudo)."
  exit 1
fi

apply_to_ns() {
  local ns="$1"
  echo "[+] applying hardening in ${ns}"
  ip netns exec "${ns}" sysctl -w net.ipv4.conf.all.rp_filter=1 >/dev/null
  ip netns exec "${ns}" sysctl -w net.ipv4.conf.default.rp_filter=1 >/dev/null
  ip netns exec "${ns}" sysctl -w net.ipv4.conf.all.arp_ignore=2 >/dev/null
  ip netns exec "${ns}" sysctl -w net.ipv4.conf.all.arp_announce=2 >/dev/null
  ip netns exec "${ns}" sysctl -w net.ipv4.tcp_syncookies=1 >/dev/null
  ip netns exec "${ns}" sysctl -w net.ipv4.conf.all.log_martians=1 >/dev/null
  ip netns exec "${ns}" sysctl -w net.ipv4.conf.all.accept_redirects=0 >/dev/null
  ip netns exec "${ns}" sysctl -w net.ipv4.conf.all.send_redirects=0 >/dev/null
}

if [[ "${TARGET}" == "--all" ]]; then
  for ns in ns-atk ns-def ns-srv ns-dns; do
    apply_to_ns "${ns}"
  done
else
  apply_to_ns "${TARGET}"
fi

echo "[+] hardening complete"
