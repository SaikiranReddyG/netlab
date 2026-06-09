from __future__ import annotations

import subprocess
from pathlib import Path

from netlab.defenses.base import Defense, DefenseContext
from netlab.defenses import register


REPO_ROOT = Path(__file__).resolve().parents[3]
APPLY_SH = REPO_ROOT / "defenses" / "02-firewall" / "apply.sh"


class FirewallDefense(Defense):
    def __init__(self):
        super().__init__(
            name="firewall",
            description="nftables ruleset with SYN rate limiting and anti-spoof rules.",
            mitigates=["syn_flood", "arp_spoof"],
            required_tools=["nft", "ip"],
            concurrent_capable=False,
            expected_alerts_for={},
            parameters={
                "ns": {"default": "ns-def", "type": str, "description": "Namespace to apply firewall in"},
            },
        )

    def apply(self, ctx: DefenseContext) -> None:
        params = self._merge_params(ctx)

        ctx.emit_event("netlab.defense.applied", "info", {
            "defense": self.name,
            "step": "applying_firewall",
            "details": {"ns": params["ns"]},
        })

        try:
            subprocess.run(
                ["bash", str(APPLY_SH), params["ns"]],
                check=True,
                capture_output=True,
            )
            ctx.emit_event("netlab.defense.applied", "info", {
                "defense": self.name,
                "step": "firewall_loaded",
                "details": {"ns": params["ns"]},
            })
        except subprocess.CalledProcessError as exc:
            ctx.emit_event("netlab.defense.applied", "high", {
                "defense": self.name,
                "step": "firewall_failed",
                "details": {"error": exc.stderr.decode(errors="replace") if exc.stderr else str(exc)},
            })
            raise

    def remove(self, ctx: DefenseContext) -> None:
        # Flush nftables rules from the namespace (best-effort; teardown removes the namespace anyway)
        params = self._merge_params(ctx)
        try:
            subprocess.run(
                ["ip", "netns", "exec", params["ns"], "nft", "flush", "ruleset"],
                check=False,
                capture_output=True,
            )
        except Exception:
            pass
        ctx.emit_event("netlab.defense.removed", "info", {"defense": self.name})


register("firewall", FirewallDefense)
