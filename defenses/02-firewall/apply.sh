#!/usr/bin/env bash
set -euo pipefail

NS="${1:-ns-def}"
RULESET="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/firewall.nft"

if [[ ${EUID} -ne 0 ]]; then
  echo "[!] Run as root (use sudo)."
  exit 1
fi

if ! command -v nft >/dev/null 2>&1; then
  echo "[!] nft command not found"
  exit 1
fi

echo "[+] applying firewall to namespace ${NS}"
ip netns exec "${NS}" nft -f "${RULESET}"
ip netns exec "${NS}" nft list ruleset
