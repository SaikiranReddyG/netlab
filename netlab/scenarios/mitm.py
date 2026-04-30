from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Dict, List

from netlab.scenarios.base import Scenario, ScenarioContext
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
        # Start two ARP poisoners (bidirectional)
        procs.append(self._start_arp("10.0.0.10", "10.0.0.1"))
        procs.append(self._start_arp("10.0.0.1", "10.0.0.10"))

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

        try:
            start = time.time()
            while time.time() - start < float(params["duration"]):
                if ctx.aborted_check():
                    break
                # if any process died, break
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


register("mitm", MitmScenario)
