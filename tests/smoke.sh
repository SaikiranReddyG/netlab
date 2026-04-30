#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "smoke.sh must be run as root"
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

NETLAB_CMD=${NETLAB_CMD:-netlab}

# Ensure clean start
${NETLAB_CMD} clean

# Verify CLI
${NETLAB_CMD} version
${NETLAB_CMD} list
${NETLAB_CMD} describe arp_spoof
${NETLAB_CMD} status

# Run each scenario, verify clean state after
for scenario in arp_spoof mitm dns_poison syn_flood; do
  echo "==== Running scenario: ${scenario} ===="
  ${NETLAB_CMD} run "${scenario}" --output stdout
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
${NETLAB_CMD} run arp_spoof --output stdout &
RUN_PID=$!
sleep 3
kill -INT ${RUN_PID}
wait ${RUN_PID} || true
sleep 2
${NETLAB_CMD} clean
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
${NETLAB_CMD} run arp_spoof --output stdout &
RUN_PID=$!
sleep 3
kill -KILL ${RUN_PID}
wait ${RUN_PID} || true
sleep 2
${NETLAB_CMD} clean
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
