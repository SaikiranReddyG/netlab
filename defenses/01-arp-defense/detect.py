#!/usr/bin/env python3
"""ARP defense detection entrypoint.

Runs Sentinel with lab-tuned rules when available, otherwise falls back to a
simple Scapy-based ARP reply-rate detector.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from collections import defaultdict, deque
from pathlib import Path

try:
    from scapy.all import ARP, sniff  # type: ignore
except Exception:  # pragma: no cover - optional fallback import
    ARP = None
    sniff = None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Netlab ARP spoof detector")
    p.add_argument("--iface", default="veth-def")
    p.add_argument(
        "--sentinel-path",
        default=os.environ.get("SENTINEL_PATH", "/home/reddy/codex-workspace/sentinel"),
        help="Path to sentinel repository",
    )
    p.add_argument(
        "--rules",
        default="/home/reddy/codex-workspace/netlab/defenses/03-ids/sentinel-rules.yaml",
        help="Sentinel rules YAML for the lab",
    )
    p.add_argument("--fallback", action="store_true", help="Force Scapy fallback detector")
    p.add_argument("--threshold", type=int, default=8, help="Fallback ARP reply threshold")
    p.add_argument("--window", type=int, default=10, help="Fallback time window in seconds")
    return p.parse_args()


def run_sentinel(sentinel_path: Path, iface: str, rules_file: Path) -> int:
    main_py = sentinel_path / "src" / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(f"Sentinel entry not found: {main_py}")

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml") as tmp:
        tmp.write(
            "\n".join(
                [
                    f"interface: {iface}",
                    f"rules_file: {rules_file}",
                    f"log_file: {sentinel_path}/logs/netlab-alerts.log",
                    "thresholds:",
                    "  port_scan:",
                    "    ports: 15",
                    "    window: 60",
                    "  syn_flood:",
                    "    rate: 60",
                    "    window: 5",
                    "  arp_spoof:",
                    "    enabled: true",
                    "    cooldown: 5",
                    "alerts:",
                    "  dedup_cooldown: 5",
                    "dashboard:",
                    "  refresh_rate: 1",
                    "  show_top_talkers: 5",
                ]
            )
        )
        temp_cfg = tmp.name

    cmd = ["python3", str(main_py), "-c", temp_cfg, "-i", iface, "--no-dashboard"]
    print(f"[detect] running sentinel: {' '.join(cmd)}")
    try:
        return subprocess.call(cmd, cwd=str(sentinel_path))
    finally:
        try:
            os.unlink(temp_cfg)
        except OSError:
            pass


def run_fallback(iface: str, threshold: int, window: int) -> int:
    if sniff is None or ARP is None:
        print("[detect] Scapy is not available for fallback mode")
        return 1

    events: dict[str, deque[float]] = defaultdict(deque)
    print(f"[detect] fallback ARP detector on iface={iface}")

    def on_packet(pkt) -> None:
        if not pkt.haslayer(ARP):
            return
        arp = pkt[ARP]
        if int(arp.op) != 2:  # ARP reply
            return

        now = time.time()
        src_mac = str(arp.hwsrc)
        q = events[src_mac]
        q.append(now)
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= threshold:
            print(f"[ALERT] ARP spoof suspected src_mac={src_mac} count={len(q)} window={window}s")

    sniff(iface=iface, store=False, prn=on_packet)
    return 0


def main() -> int:
    args = parse_args()
    sentinel_path = Path(args.sentinel_path).resolve()
    rules_file = Path(args.rules).resolve()

    if not args.fallback and sentinel_path.exists() and rules_file.exists():
        return run_sentinel(sentinel_path, args.iface, rules_file)

    print("[detect] Sentinel path/rules unavailable or fallback requested, using local detector")
    return run_fallback(args.iface, args.threshold, args.window)


if __name__ == "__main__":
    sys.exit(main())
