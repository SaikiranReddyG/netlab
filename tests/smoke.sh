#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "smoke.sh must be run as root"
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# Ensure clean start
.venv/bin/netlab clean

# Verify CLI
.venv/bin/netlab version
.venv/bin/netlab list
.venv/bin/netlab describe arp_spoof
.venv/bin/netlab status

# Run each scenario, verify clean state after
for scenario in arp_spoof mitm dns_poison syn_flood; do
  echo "==== Running scenario: ${scenario} ===="
  .venv/bin/netlab run "${scenario}" --output stdout
  # Verify no bridge or namespaces remain
  if ip link show br-lab >/dev/null 2>&1; then
    echo "[!] FAIL: residual bridge after ${scenario}"
    exit 1
  fi
  if ip netns list | grep -q "ns-atk\|ns-def\|ns-srv\|ns-dns"; then
    echo "[!] FAIL: residual namespaces after ${scenario}"
    exit 1
  fi
  echo "[+] ${scenario} clean"
done

# SIGINT recovery test
echo "==== SIGINT recovery test ===="
.venv/bin/netlab run arp_spoof --output stdout &
RUN_PID=$!
sleep 3
kill -INT ${RUN_PID}
wait ${RUN_PID} || true
sleep 2
.venv/bin/netlab clean
if ip link show br-lab >/dev/null 2>&1; then
  echo "[!] FAIL: dirty state after SIGINT (bridge present)"
  exit 1
fi
if ip netns list | grep -q "ns-atk\|ns-def\|ns-srv\|ns-dns"; then
  echo "[!] FAIL: dirty state after SIGINT (namespaces present)"
  exit 1
fi
echo "[+] SIGINT recovery clean"

# SIGKILL recovery test
echo "==== SIGKILL recovery test ===="
.venv/bin/netlab run arp_spoof --output stdout &
RUN_PID=$!
sleep 3
kill -KILL ${RUN_PID}
wait ${RUN_PID} || true
sleep 2
.venv/bin/netlab clean
if ip link show br-lab >/dev/null 2>&1; then
  echo "[!] FAIL: dirty state after SIGKILL (bridge present)"
  exit 1
fi
if ip netns list | grep -q "ns-atk\|ns-def\|ns-srv\|ns-dns"; then
  echo "[!] FAIL: dirty state after SIGKILL (namespaces present)"
  exit 1
fi
echo "[+] SIGKILL recovery clean"

echo "[+] smoke test passed"
