from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from threading import Thread

from netlab.defenses.base import Defense, DefenseContext
from netlab.defenses import register


REPO_ROOT = Path(__file__).resolve().parents[3]
DETECT_PY = REPO_ROOT / "defenses" / "01-arp-defense" / "detect.py"


class IdsDefense(Defense):
    """Detection-only IDS: monitors br-lab bridge for ARP anomalies without locking anything."""

    def __init__(self):
        super().__init__(
            name="ids",
            description="Passive Scapy IDS on br-lab — detects ARP anomalies without locking.",
            mitigates=["arp_spoof", "mitm", "dns_poison"],
            required_tools=["ip"],
            concurrent_capable=True,
            expected_alerts_for={
                "arp_spoof": ["ARP spoof suspected"],
                "mitm": ["ARP spoof suspected"],
                "dns_poison": ["ARP spoof suspected"],
            },
            parameters={
                "iface": {"default": "br-lab", "type": str, "description": "Interface to monitor"},
                "threshold": {"default": 8, "type": int, "description": "ARP reply count to trigger alert"},
                "window": {"default": 10, "type": int, "description": "Detection time window in seconds"},
            },
        )
        self._detect_proc: subprocess.Popen | None = None
        self._alert_thread: Thread | None = None

    def apply(self, ctx: DefenseContext) -> None:
        params = self._merge_params(ctx)

        ctx.emit_event("netlab.defense.applied", "info", {
            "defense": self.name,
            "step": "detector_starting",
            "details": {"iface": params["iface"], "mode": "passive"},
        })

        # Monitor br-lab on the host — no namespace exec needed
        cmd = [
            sys.executable, "-u", str(DETECT_PY),
            "--fallback",
            "--iface", str(params["iface"]),
            "--threshold", str(params["threshold"]),
            "--window", str(params["window"]),
        ]
        self._detect_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        self._alert_thread = Thread(target=self._read_alerts, args=(ctx,), daemon=True)
        self._alert_thread.start()

        ctx.emit_event("netlab.defense.applied", "info", {
            "defense": self.name,
            "step": "detector_started",
            "details": {"iface": params["iface"], "threshold": params["threshold"]},
        })

    def _read_alerts(self, ctx: DefenseContext) -> None:
        if self._detect_proc is None or self._detect_proc.stdout is None:
            return
        for line in self._detect_proc.stdout:
            line = line.strip()
            if not line:
                continue
            if "[ALERT]" in line:
                self.alerts.append(line)
                ctx.emit_event("netlab.defense.alert", "high", {
                    "defense": self.name,
                    "message": line.replace("[ALERT]", "").strip(),
                })

    def remove(self, ctx: DefenseContext) -> None:
        if self._detect_proc and self._detect_proc.poll() is None:
            self._detect_proc.terminate()
            try:
                self._detect_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._detect_proc.kill()

        ctx.emit_event("netlab.defense.removed", "info", {
            "defense": self.name,
            "alert_count": len(self.alerts),
        })


register("ids", IdsDefense)
