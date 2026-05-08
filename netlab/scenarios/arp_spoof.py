from __future__ import annotations

import subprocess
import time
from pathlib import Path

from netlab.scenarios.base import Scenario, ScenarioContext, wait_for_duration
from netlab.scenarios import register


REPO_ROOT = Path(__file__).resolve().parents[2]
ATTACK_SCRIPT = REPO_ROOT / "attacks" / "01-arp-spoof" / "attack.py"


class ArpSpoofScenario(Scenario):
    def __init__(self):
        super().__init__(
            name="arp_spoof",
            description="ARP cache poisoning from ns-atk against ns-srv (10.0.0.10).",
            required_tools=["python3", "ip"],
            expected_duration_seconds=15,
            parameters={
                "target_ip": {"default": "10.0.0.10", "type": str, "description": "Victim IP"},
                "gateway_ip": {"default": "10.0.0.1", "type": str, "description": "Gateway IP to spoof"},
                "interval": {"default": 0.5, "type": float, "description": "Seconds between poison packets"},
                "duration": {"default": 10, "type": int, "description": "Total seconds to run attack"},
            },
        )

    def run(self, ctx: ScenarioContext) -> None:
        params = self._merge_params(ctx)

        ctx.emit_event("netlab.scenario.event", "low", {
            "scenario": self.name,
            "step": "starting_attack",
            "details": params,
        })

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
            str(params["target_ip"]),
            "--gateway-ip",
            str(params["gateway_ip"]),
            "--interval",
            str(params["interval"]),
        ]

        proc = subprocess.Popen(cmd)
        wait_for_duration(float(params["duration"]), ctx, [proc])

        ctx.emit_event("netlab.scenario.event", "low", {
            "scenario": self.name,
            "step": "attack_complete",
        })


register("arp_spoof", ArpSpoofScenario)
