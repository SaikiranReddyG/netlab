#!/usr/bin/env bash
set -euo pipefail

require_root() {
  if [[ ${EUID} -ne 0 ]]; then
    echo "[!] Run as root (use sudo)."
    exit 1
  fi
}

install_with_apt() {
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    iproute2 \
    bridge-utils \
    tcpdump \
    dnsmasq \
    hping3 \
    nftables \
    curl \
    dnsutils \
    python3 \
    python3-pip \
    python3-scapy \
    python3-yaml
}

install_with_pacman() {
  pacman -Sy --noconfirm \
    iproute2 \
    bridge-utils \
    tcpdump \
    dnsmasq \
    hping \
    nftables \
    curl \
    bind \
    python \
    python-pip \
    python-scapy \
    python-yaml
}

main() {
  require_root

  if command -v apt-get >/dev/null 2>&1; then
    echo "[+] Detected apt-get (Debian/Ubuntu). Installing dependencies..."
    install_with_apt
  elif command -v pacman >/dev/null 2>&1; then
    echo "[+] Detected pacman (Arch Linux). Installing dependencies..."
    install_with_pacman
  else
    echo "[!] Unsupported package manager. Install these tools manually:"
    echo "    iproute2 bridge-utils tcpdump dnsmasq hping3/hping nftables curl dnsutils/bind python3 python-pip scapy pyyaml"
    exit 1
  fi

  echo "[+] Dependency installation complete."
}

main "$@"