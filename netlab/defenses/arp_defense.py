from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from threading import Thread

from netlab.defenses.base import Defense, DefenseContext
from netlab.defenses import register


REPO_ROOT = Path(__file__).resolve().parents[3]
STATIC_ARP_SH = REPO_ROOT / "defenses" / "01-arp-defense" / "static-arp.sh"
DETECT_PY = REPO_ROOT / "defenses" / "01-arp-defense" / "detect.py"


class ArpDefense(Defense):
    def __init__(self):
        super().__init__(
            name="arp_defense",
            description="Static ARP locking + Scapy ARP spoof detector in ns-def.",
            mitigates=["arp_spoof", "mitm", "dns_poison"],
            required_tools=["ip"],
            concurrent_capable=True,
            expected_alerts_for={
                "arp_spoof": ["ARP spoof suspected"],
                "mitm": ["ARP spoof suspected"],
                "dns_poison": ["ARP spoof suspected"],
            },
            parameters={
                "ns": {"default": "ns-srv", "type": str, "description": "Namespace to lock ARP in"},
                "iface": {"default": "veth-srv", "type": str, "description": "Interface in protected namespace"},
                "detector_iface": {"default": "veth-def", "type": str, "description": "Interface for ARP monitoring"},
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
            "step": "applying_static_arp",
            "details": {"ns": params["ns"], "iface": params["iface"]},
        })

        try:
            subprocess.run(
                ["bash", str(STATIC_ARP_SH), params["ns"], params["iface"]],
                check=True,
                capture_output=True,
            )
            ctx.emit_event("netlab.defense.applied", "info", {
                "defense": self.name,
                "step": "static_arp_locked",
                "details": {"ns": params["ns"]},
            })
        except subprocess.CalledProcessError as exc:
            ctx.emit_event("netlab.defense.applied", "medium", {
                "defense": self.name,
                "step": "static_arp_failed",
                "details": {"error": exc.stderr.decode(errors="replace") if exc.stderr else str(exc)},
            })

        cmd = [
            "ip", "netns", "exec", "ns-def",
            sys.executable, "-u", str(DETECT_PY),
            "--fallback",
            "--iface", str(params["detector_iface"]),
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
            "details": {"iface": params["detector_iface"], "threshold": params["threshold"]},
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


register("arp_defense", ArpDefense)
