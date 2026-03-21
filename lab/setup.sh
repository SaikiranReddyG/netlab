#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNTIME_DIR="${ROOT_DIR}/.netlab-runtime"

NS_ATK="ns-atk"
NS_DEF="ns-def"
NS_SRV="ns-srv"
NS_DNS="ns-dns"
BRIDGE="br-lab"

ATK_IP="10.0.0.2/24"
DEF_IP="10.0.0.3/24"
SRV_IP="10.0.0.10/24"
DNS_IP="10.0.0.53/24"
BRIDGE_IP="10.0.0.1/24"
GW_IP="10.0.0.1"

SENTINEL_PATH_DEFAULT="/home/sai/codex-workspace/sentinel"

require_root() {
  if [[ ${EUID} -ne 0 ]]; then
    echo "[!] Run as root (use sudo)."
    exit 1
  fi
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

print_install_hint() {
  echo "[i] Install dependencies with: sudo ./lab/install-deps.sh"

  if command_exists apt-get; then
    echo "[i] Detected apt-get. Manual install:"
    echo "    sudo apt-get update && sudo apt-get install -y iproute2 bridge-utils tcpdump dnsmasq hping3 nftables curl dnsutils python3 python3-pip python3-scapy python3-yaml"
  elif command_exists pacman; then
    echo "[i] Detected pacman. Manual install:"
    echo "    sudo pacman -Sy --noconfirm iproute2 bridge-utils tcpdump dnsmasq hping nftables curl bind python python-pip python-scapy python-yaml"
  fi
}

check_prereqs() {
  local missing=0
  local tools=(ip python3 tcpdump dnsmasq nft hping3)

  for tool in "${tools[@]}"; do
    if ! command_exists "${tool}"; then
      echo "[!] Missing required tool: ${tool}"
      missing=1
    fi
  done

  if ! command_exists bridge && ! command_exists brctl; then
    echo "[!] Missing bridge tooling: install iproute2 (bridge) or bridge-utils (brctl)"
    missing=1
  fi

  if ! python3 -c 'import scapy.all' >/dev/null 2>&1; then
    echo "[!] Missing Python dependency: scapy (pip install scapy)"
    missing=1
  fi

  if [[ ! -d "${SENTINEL_PATH:-${SENTINEL_PATH_DEFAULT}}" ]]; then
    echo "[!] Sentinel path not found at ${SENTINEL_PATH:-${SENTINEL_PATH_DEFAULT}}"
    echo "    Set SENTINEL_PATH=/path/to/sentinel if needed."
  fi

  if [[ ${missing} -ne 0 ]]; then
    print_install_hint
    exit 1
  fi
}

cleanup_stale() {
  for ns in "${NS_ATK}" "${NS_DEF}" "${NS_SRV}" "${NS_DNS}"; do
    if ip netns list | awk '{print $1}' | grep -qx "${ns}"; then
      ip netns del "${ns}" || true
    fi
  done

  if ip link show "${BRIDGE}" >/dev/null 2>&1; then
    ip link del "${BRIDGE}" || true
  fi

  rm -rf "${RUNTIME_DIR}"
}

create_namespaces() {
  ip netns add "${NS_ATK}"
  ip netns add "${NS_DEF}"
  ip netns add "${NS_SRV}"
  ip netns add "${NS_DNS}"
}

create_bridge() {
  ip link add name "${BRIDGE}" type bridge
  ip addr add "${BRIDGE_IP}" dev "${BRIDGE}"
  ip link set "${BRIDGE}" up
}

create_veth_pair() {
  local role="$1"
  local ns="$2"
  local ip_cidr="$3"
  local veth_ns="veth-${role}"
  local veth_br="veth-${role}-br"

  ip link add "${veth_ns}" type veth peer name "${veth_br}"
  ip link set "${veth_ns}" netns "${ns}"

  ip netns exec "${ns}" ip link set lo up
  ip netns exec "${ns}" ip addr add "${ip_cidr}" dev "${veth_ns}"
  ip netns exec "${ns}" ip link set "${veth_ns}" up
  ip netns exec "${ns}" ip route add default via "${GW_IP}" dev "${veth_ns}"

  ip link set "${veth_br}" master "${BRIDGE}"
  ip link set "${veth_br}" up
}

enable_forwarding() {
  ip netns exec "${NS_ATK}" sysctl -w net.ipv4.ip_forward=1 >/dev/null
  ip netns exec "${NS_DEF}" sysctl -w net.ipv4.ip_forward=1 >/dev/null
}

start_services() {
  mkdir -p "${RUNTIME_DIR}"

  local http_log="${RUNTIME_DIR}/http-server.log"
  local dns_log="${RUNTIME_DIR}/dnsmasq.log"
  local dns_conf="${SCRIPT_DIR}/services/dns-server.conf"
  local http_srv="${SCRIPT_DIR}/services/http-server.py"

  ip netns exec "${NS_SRV}" python3 "${http_srv}" --host 10.0.0.10 --port 80 >"${http_log}" 2>&1 &
  echo "$!" >"${RUNTIME_DIR}/http-server.pid"

  ip netns exec "${NS_DNS}" dnsmasq --conf-file="${dns_conf}" --keep-in-foreground >"${dns_log}" 2>&1 &
  echo "$!" >"${RUNTIME_DIR}/dnsmasq.pid"
}

print_summary() {
  cat <<EOF
[+] Netlab setup complete
    Namespaces: ${NS_ATK}, ${NS_DEF}, ${NS_SRV}, ${NS_DNS}
    Bridge: ${BRIDGE} (${BRIDGE_IP})
    Service logs: ${RUNTIME_DIR}

Quick checks:
  sudo ./lab/status.sh
  sudo ip netns exec ${NS_ATK} curl -s http://10.0.0.10
  sudo ip netns exec ${NS_ATK} nslookup target.lab 10.0.0.53
EOF
}

main() {
  require_root
  check_prereqs
  cleanup_stale
  create_namespaces
  create_bridge

  create_veth_pair "atk" "${NS_ATK}" "${ATK_IP}"
  create_veth_pair "def" "${NS_DEF}" "${DEF_IP}"
  create_veth_pair "srv" "${NS_SRV}" "${SRV_IP}"
  create_veth_pair "dns" "${NS_DNS}" "${DNS_IP}"

  enable_forwarding
  
  # Wait for interfaces to settle before starting services (esp. dnsmasq binding)
  sleep 1
  
  start_services
  print_summary
}

main "$@"