from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Dict, List

from netlab.scenarios.base import Scenario, ScenarioContext
from netlab.scenarios import register


REPO_ROOT = Path(__file__).resolve().parents[2]
ATTACK_SCRIPT = REPO_ROOT / "attacks" / "01-arp-spoof" / "attack.py"
POISON_SCRIPT = REPO_ROOT / "attacks" / "03-dns-poison" / "poison.py"


class DnsPoisonScenario(Scenario):
    def __init__(self):
        super().__init__(
            name="dns_poison",
            description="DNS response spoofing via MITM position.",
            required_tools=["python3", "ip"],
            expected_duration_seconds=30,
            parameters={
                "domain": {"default": "target.lab", "type": str, "description": "Domain to spoof"},
                "spoof_ip": {"default": "10.0.0.2", "type": str, "description": "IP to return"},
                "duration": {"default": 20, "type": int, "description": "Seconds to run"},
            },
        )

    def _start_arp(self, target_ip: str, gateway_ip: str) -> subprocess.Popen:
        cmd = [
            "ip",
            "netns",
            "exec",
            "ns-atk",
            "python3",
            str(ATTACK_SCRIPT),
            "--iface",
            "veth-atk",
            "--target-ip",
            target_ip,
            "--gateway-ip",
            gateway_ip,
            "--interval",
            "1",
        ]
        return subprocess.Popen(cmd)

    def run(self, ctx: ScenarioContext) -> None:
        params: Dict = {k: v["default"] for k, v in self.parameters.items()}
        params.update(ctx.params or {})

        ctx.emit_event("netlab.scenario.event", "low", {"scenario": self.name, "step": "starting"})

        procs: List[subprocess.Popen] = []
        # MITM ARP setup
        procs.append(self._start_arp("10.0.0.10", "10.0.0.1"))
        procs.append(self._start_arp("10.0.0.1", "10.0.0.10"))

        # start poison
        poison_cmd = [
            "ip",
            "netns",
            "exec",
            "ns-atk",
            "python3",
            str(POISON_SCRIPT),
            "--iface",
            "veth-atk",
            "--domain",
            str(params["domain"]),
            "--spoof-ip",
            str(params["spoof_ip"]),
        ]
        poison_proc = subprocess.Popen(poison_cmd)
        procs.append(poison_proc)

        try:
            start = time.time()
            while time.time() - start < float(params["duration"]):
                if ctx.aborted_check():
                    break
                for p in procs:
                    if p.poll() is not None:
                        break
                time.sleep(0.5)
        finally:
            for p in procs:
                if p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        p.kill()

        ctx.emit_event("netlab.scenario.event", "low", {"scenario": self.name, "step": "complete"})


register("dns_poison", DnsPoisonScenario)
