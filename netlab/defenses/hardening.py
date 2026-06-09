from __future__ import annotations

import subprocess
from pathlib import Path

from netlab.defenses.base import Defense, DefenseContext
from netlab.defenses import register


REPO_ROOT = Path(__file__).resolve().parents[3]
SYSCTL_SH = REPO_ROOT / "defenses" / "04-hardening" / "sysctl.sh"


class HardeningDefense(Defense):
    def __init__(self):
        super().__init__(
            name="hardening",
            description="Kernel hardening: rp_filter, arp_ignore, tcp_syncookies, redirect controls.",
            mitigates=["arp_spoof", "mitm", "syn_flood"],
            required_tools=["ip", "sysctl"],
            concurrent_capable=False,
            expected_alerts_for={},
            parameters={
                "target": {"default": "ns-srv", "type": str, "description": "Namespace to harden (or '--all')"},
            },
        )

    def apply(self, ctx: DefenseContext) -> None:
        params = self._merge_params(ctx)

        ctx.emit_event("netlab.defense.applied", "info", {
            "defense": self.name,
            "step": "applying_hardening",
            "details": {"target": params["target"]},
        })

        try:
            subprocess.run(
                ["bash", str(SYSCTL_SH), params["target"]],
                check=True,
                capture_output=True,
            )
            ctx.emit_event("netlab.defense.applied", "info", {
                "defense": self.name,
                "step": "hardening_applied",
                "details": {
                    "target": params["target"],
                    "params": ["rp_filter=1", "arp_ignore=2", "arp_announce=2", "tcp_syncookies=1"],
                },
            })
        except subprocess.CalledProcessError as exc:
            ctx.emit_event("netlab.defense.applied", "high", {
                "defense": self.name,
                "step": "hardening_failed",
                "details": {"error": exc.stderr.decode(errors="replace") if exc.stderr else str(exc)},
            })
            raise

    def remove(self, ctx: DefenseContext) -> None:
        # Sysctl changes live in the namespace — teardown removes it entirely, so no rollback needed
        ctx.emit_event("netlab.defense.removed", "info", {"defense": self.name})


register("hardening", HardeningDefense)
