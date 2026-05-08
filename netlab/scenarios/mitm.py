from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import List

from netlab.scenarios.base import Scenario, ScenarioContext, wait_for_duration, start_arp_spoof
from netlab.scenarios import register


REPO_ROOT = Path(__file__).resolve().parents[2]
ATTACK_SCRIPT = REPO_ROOT / "attacks" / "01-arp-spoof" / "attack.py"
INTERCEPTOR = REPO_ROOT / "attacks" / "02-mitm" / "intercept.py"


class MitmScenario(Scenario):
    def __init__(self):
        super().__init__(
            name="mitm",
            description="Man-in-the-middle interception with ARP poison and HTTP interceptor.",
            required_tools=["python3", "ip"],
            expected_duration_seconds=30,
            parameters={
                "duration": {"default": 20, "type": int, "description": "Seconds to run"},
                "active_modify": {"default": False, "type": bool, "description": "Enable payload modify"},
            },
        )

    def run(self, ctx: ScenarioContext) -> None:
        params = self._merge_params(ctx)

        ctx.emit_event("netlab.scenario.event", "low", {"scenario": self.name, "step": "starting"})

        procs: List[subprocess.Popen] = []
        # Start two ARP poisoners (bidirectional)
        procs.append(start_arp_spoof(str(ATTACK_SCRIPT), "10.0.0.10", "10.0.0.1"))
        procs.append(start_arp_spoof(str(ATTACK_SCRIPT), "10.0.0.1", "10.0.0.10"))

        # start interceptor
        interceptor_cmd = [
            "ip",
            "netns",
            "exec",
            "ns-atk",
            "python3",
            str(INTERCEPTOR),
            "--iface",
            "veth-atk",
        ]
        if params.get("active_modify"):
            interceptor_cmd.append("--active-modify")
        interceptor_proc = subprocess.Popen(interceptor_cmd)
        procs.append(interceptor_proc)

        wait_for_duration(float(params["duration"]), ctx, procs)

        ctx.emit_event("netlab.scenario.event", "low", {"scenario": self.name, "step": "complete"})


register("mitm", MitmScenario)
