#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CAP_DIR="${ROOT_DIR}/captures"
LOG_DIR="${ROOT_DIR}/.netlab-runtime"
mkdir -p "${CAP_DIR}" "${LOG_DIR}"

require_root() {
  if [[ ${EUID} -ne 0 ]]; then
    echo "[!] Run as root: sudo ./lab/validate_phase2.sh"
    exit 1
  fi
}

section() {
  printf "\n==== %s ====\n" "$1"
}

baseline_checks() {
  section "Baseline"
  "${ROOT_DIR}/lab/status.sh"
  ip netns exec ns-atk curl -s http://10.0.0.10 >"${LOG_DIR}/baseline-http.html"
  ip netns exec ns-atk nslookup target.lab 10.0.0.53 >"${LOG_DIR}/baseline-dns.txt" || true
  echo "[+] Baseline HTTP saved: ${LOG_DIR}/baseline-http.html"
  echo "[+] Baseline DNS saved:  ${LOG_DIR}/baseline-dns.txt"
}

arp_attack_validation() {
  section "ARP Spoof (Scapy)"

  ip netns exec ns-srv ip neigh flush 10.0.0.1 dev veth-srv || true
  ip netns exec ns-srv ping -c 1 -W 1 10.0.0.1 >/dev/null 2>&1 || true

  echo "[before]" | tee "${LOG_DIR}/arp-neigh.txt"
  ip netns exec ns-srv ip neigh show 10.0.0.1 dev veth-srv | tee -a "${LOG_DIR}/arp-neigh.txt"

  rm -f "${CAP_DIR}/01-arp-spoof.pcap"
  timeout 12 ip netns exec ns-srv tcpdump -ni veth-srv arp -w "${CAP_DIR}/01-arp-spoof.pcap" >/dev/null 2>&1 &
  local tp=$!

  ip netns exec ns-atk timeout 5 python3 "${ROOT_DIR}/attacks/01-arp-spoof/attack.py" \
    --iface veth-atk \
    --target-ip 10.0.0.10 \
    --gateway-ip 10.0.0.1 \
    --interval 0.3 >/dev/null 2>&1 &
  local ap=$!

  sleep 2

  echo "[during]" | tee -a "${LOG_DIR}/arp-neigh.txt"
  ip netns exec ns-srv ip neigh show 10.0.0.1 dev veth-srv | tee -a "${LOG_DIR}/arp-neigh.txt"

  wait "${ap}" || true
  wait "${tp}" || true
  ip netns exec ns-srv ping -c 1 -W 1 10.0.0.1 >/dev/null 2>&1 || true

  echo "[after]" | tee -a "${LOG_DIR}/arp-neigh.txt"
  ip netns exec ns-srv ip neigh show 10.0.0.1 dev veth-srv | tee -a "${LOG_DIR}/arp-neigh.txt"

  ls -lh "${CAP_DIR}/01-arp-spoof.pcap"
  tcpdump -nn -r "${CAP_DIR}/01-arp-spoof.pcap" | head -n 20 >"${LOG_DIR}/arp-pcap-head.txt" || true
  echo "[+] ARP neighbor evidence: ${LOG_DIR}/arp-neigh.txt"
  echo "[+] ARP PCAP preview:      ${LOG_DIR}/arp-pcap-head.txt"
}

arp_defense_validation() {
  section "ARP Defense"
  "${ROOT_DIR}/defenses/01-arp-defense/static-arp.sh" ns-srv veth-srv
  ip netns exec ns-srv ip neigh show 10.0.0.1 dev veth-srv >"${LOG_DIR}/arp-static-after.txt"
  echo "[+] Static ARP evidence: ${LOG_DIR}/arp-static-after.txt"
}

main() {
  require_root
  baseline_checks
  arp_attack_validation
  arp_defense_validation

  section "Done"
  echo "Validation artifacts are in:"
  echo "  - ${LOG_DIR}"
  echo "  - ${CAP_DIR}"
}

main "$@"
