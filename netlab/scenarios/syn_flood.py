from __future__ import annotations

import subprocess
import time
from pathlib import Path

from netlab.scenarios.base import Scenario, ScenarioContext, wait_for_duration
from netlab.scenarios import register


REPO_ROOT = Path(__file__).resolve().parents[2]
FLOOD_SCRIPT = REPO_ROOT / "attacks" / "04-syn-flood" / "flood.py"


class SynFloodScenario(Scenario):
    def __init__(self):
        super().__init__(
            name="syn_flood",
            description="SYN flood from attacker namespace to server.",
            required_tools=["python3", "ip"],
            expected_duration_seconds=30,
            parameters={
                "target_ip": {"default": "10.0.0.10", "type": str, "description": "Target IP"},
                "count": {"default": 1000, "type": int, "description": "Packet count"},
                "pps": {"default": 200, "type": int, "description": "Packets per second"},
            },
            expected_steps=["starting", "complete"],
        )

    def run(self, ctx: ScenarioContext) -> None:
        params = self._merge_params(ctx)

        ctx.emit_event("netlab.scenario.event", "low", {"scenario": self.name, "step": "starting", "details": params})

        cmd = [
            "ip",
            "netns",
            "exec",
            "ns-atk",
            "python3",
            str(FLOOD_SCRIPT),
            "--target-ip",
            str(params["target_ip"]),
            "--count",
            str(params["count"]),
            "--pps",
            str(params["pps"]),
        ]

        proc = subprocess.Popen(cmd)
        wait_for_duration(None, ctx, [proc])

        ctx.emit_event("netlab.scenario.event", "low", {"scenario": self.name, "step": "complete"})


register("syn_flood", SynFloodScenario)
