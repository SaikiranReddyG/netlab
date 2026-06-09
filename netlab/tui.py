#!/usr/bin/env python3
"""netlab live TUI — topology hero layout with side-by-side event feeds."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Label, RichLog, Static

from netlab import state as state_module
from netlab import topology


_SEVERITY_STYLE = {
    "info":     "dim",
    "low":      "white",
    "medium":   "yellow",
    "high":     "bold red",
    "critical": "bold red on dark_red",
}


def _ts(event: dict) -> str:
    raw = event.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(raw)
        return dt.strftime("%H:%M:%S")
    except Exception:
        return raw[:8] if raw else "--:--:--"


def _format_attack(event: dict) -> str:
    etype = event.get("event_type", "")
    sev = event.get("severity", "info")
    style = _SEVERITY_STYLE.get(sev, "white")
    ts = _ts(event)
    payload = event.get("payload", {})

    short = etype.replace("netlab.", "")

    if etype == "netlab.scenario.started":
        sc = payload.get("scenario", "")
        df = payload.get("defense", "")
        label = f"▶ {sc}" + (f" vs {df}" if df else "")
    elif etype == "netlab.scenario.completed":
        dur = payload.get("duration_seconds")
        label = f"✓ completed ({dur:.1f}s)" if dur is not None else "✓ completed"
    elif etype == "netlab.scenario.aborted":
        label = f"✗ aborted: {payload.get('reason', '')}"
    elif etype == "netlab.scenario.event":
        step = payload.get("step", "")
        details = payload.get("details", {})
        label = f"  {step}"
        if details:
            detail_str = "  ".join(f"{k}={v}" for k, v in details.items() if k != "scenario")
            if detail_str:
                label += f"\n    {detail_str}"
    elif etype == "netlab.lifecycle.warming_up":
        label = "  warming up..."
    elif etype == "netlab.lifecycle.tearing_down":
        label = "  tearing down..."
    elif etype in ("netlab.lifecycle.clean", "netlab.lifecycle.dirty"):
        label = "  clean" if etype.endswith("clean") else "  ⚠ dirty state"
    elif etype == "netlab.pair.started":
        sc = payload.get("scenario", "")
        df = payload.get("defense", "")
        label = f"▶ pair  {sc} → {df}"
    elif etype == "netlab.pair.summary":
        alerts = payload.get("defense_alerts", 0)
        dur = payload.get("duration_seconds")
        ok = "✓" if payload.get("attack_success") else "✗"
        label = f"{ok} summary  {alerts} alert(s)"
        if dur:
            label += f"  {dur:.1f}s"
    else:
        label = f"  {short}"

    return f"[{style}]{ts}  {label}[/{style}]"


def _format_defense(event: dict) -> str:
    etype = event.get("event_type", "")
    sev = event.get("severity", "info")
    style = _SEVERITY_STYLE.get(sev, "white")
    ts = _ts(event)
    payload = event.get("payload", {})

    if etype == "netlab.defense.applied":
        step = payload.get("step", "")
        details = payload.get("details", {})
        if step == "applying_static_arp":
            label = f"▶ locking ARP in {details.get('ns', '')}"
        elif step == "static_arp_locked":
            label = f"  static ARP locked in {details.get('ns', '')}"
        elif step == "static_arp_failed":
            label = "  ⚠ static ARP failed"
        elif step == "detector_starting":
            label = f"▶ starting detector on {details.get('iface', '')}"
        elif step == "detector_started":
            label = f"  monitoring {details.get('iface', '')}  threshold={details.get('threshold', '')}"
        elif step == "firewall_loaded":
            label = f"  firewall active in {details.get('ns', '')}"
        elif step == "hardening_applied":
            params = ", ".join(details.get("params", []))
            label = f"  hardening: {params}"
        elif step == "apply_failed":
            label = f"  ✗ apply failed: {details.get('error', '')}"
        else:
            label = f"▶ {step}"
    elif etype == "netlab.defense.alert":
        msg = payload.get("message", "")
        label = f"⚠ ALERT  {msg}"
        style = "bold red"
    elif etype == "netlab.defense.removed":
        count = payload.get("alert_count", 0)
        label = f"◼ removed  ({count} alert(s) fired)"
    else:
        label = f"  {etype.replace('netlab.defense.', '')}"

    return f"[{style}]{ts}  {label}[/{style}]"


class TopologyPanel(Static):
    """Topology diagram showing namespace layout and live attack/defense state."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active: dict | None = None
        self._fully_up: bool = False
        self._start_ts: float | None = None

    def update_state(self, active: dict | None, fully_up: bool) -> None:
        if active != self._active:
            if active is not None and self._active is None:
                self._start_ts = time.time()
            elif active is None:
                self._start_ts = None
        self._active = active
        self._fully_up = fully_up
        self.refresh()

    def render(self) -> str:
        active = self._active or {}
        sc = active.get("scenario", "")
        defense = active.get("defense", "")
        mode = active.get("mode", "pre-apply")
        up = self._fully_up

        # Per-node colors
        c_atk = "bold red"    if sc      else ("green" if up else "dim")
        c_srv = "yellow"       if sc      else ("green" if up else "dim")
        c_def = "bold cyan"    if defense else ("green" if up else "dim")
        c_dns = "green"        if up      else "dim"
        c_br  = "bold green"   if up      else "dim"

        # Attack arrow (ns-atk → br-lab)
        if sc:
            atk_arrow = "[bold red]──⚡──▶[/]"
        else:
            atk_arrow = "[dim]──────▶[/]"

        # Lab status indicator
        lab_dot = "[bold green]● UP[/]" if up else "[bold red]● DOWN[/]"

        # Elapsed timer
        elapsed_str = ""
        if self._start_ts and (sc or defense):
            secs = int(time.time() - self._start_ts)
            m, s = divmod(secs, 60)
            elapsed_str = f"  [cyan]{m:02d}:{s:02d}[/cyan]"

        # Active run info line
        if sc and defense:
            run_line = (
                f"  [{c_atk}]{sc}[/] [dim]──────────────────────────────▶[/dim]"
                f" [{c_def}]{defense}[/]  [dim]({mode})[/dim]{elapsed_str}"
            )
        elif sc:
            run_line = f"  [{c_atk}]{sc}[/]  [dim]running[/dim]{elapsed_str}"
        else:
            run_line = "  [dim]no active run[/dim]"

        lines = [
            f"  {lab_dot}",
            "",
            f"  [{c_atk}]┌─ ns-atk ──┐[/]        [{c_br}]┌─────────┐[/]      [{c_srv}]┌─ ns-srv ───┐[/]",
            f"  [{c_atk}]│ ATTACKER  │[/]{atk_arrow} [{c_br}]│ br-lab  │[/] [dim]◀────[/dim]  [{c_srv}]│  TARGET    │[/]",
            f"  [{c_atk}]│ 10.0.0.2  │[/]        [{c_br}]│10.0.0.1 │[/]      [{c_srv}]│ 10.0.0.10  │[/]",
            f"  [{c_atk}]└───────────┘[/]        [{c_br}]└────┬────┘[/]      [{c_srv}]└────────────┘[/]",
            f"  [{c_def}]┌─ ns-def ──┐[/]             [dim]│[/dim]            [{c_dns}]┌─ ns-dns ───┐[/]",
            f"  [{c_def}]│ DEFENDER  │[/][dim]────────────┘[/dim]            [{c_dns}]│    DNS     │[/]",
            f"  [{c_def}]│ 10.0.0.3  │[/]                         [{c_dns}]│ 10.0.0.53  │[/]",
            f"  [{c_def}]└───────────┘[/]                         [{c_dns}]└────────────┘[/]",
            "",
            run_line,
        ]

        return "\n".join(lines)


class NetLabApp(App):
    CSS = """
    Screen {
        background: $surface;
    }

    TopologyPanel {
        height: 14;
        background: $panel;
        padding: 0 1;
        border-bottom: tall $primary-darken-2;
    }

    #panels {
        height: 1fr;
    }

    #attack-pane, #defense-pane {
        width: 1fr;
    }

    #attack-pane {
        border-right: tall $primary-darken-2;
    }

    .pane-label {
        height: 1;
        background: $primary-darken-2;
        color: $text-muted;
        text-align: center;
        text-style: bold;
        padding: 0 1;
    }

    #attack-label {
        color: $warning;
    }

    #defense-label {
        color: $success;
    }

    RichLog {
        height: 1fr;
        background: $surface;
        padding: 0 1;
        scrollbar-size: 1 1;
    }

    Footer {
        height: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "action_refresh", "Refresh"),
        Binding("tab", "focus_next", "Switch panel"),
        Binding("c", "clear_logs", "Clear"),
    ]

    TITLE = "netlab"

    def compose(self) -> ComposeResult:
        yield TopologyPanel(id="topology")
        with Horizontal(id="panels"):
            with Vertical(id="attack-pane"):
                yield Label("ATTACK", id="attack-label", classes="pane-label")
                yield RichLog(id="attack-log", highlight=False, markup=True, wrap=True)
            with Vertical(id="defense-pane"):
                yield Label("DEFENSE", id="defense-label", classes="pane-label")
                yield RichLog(id="defense-log", highlight=False, markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self._file_pos = 0
        self._last_active: dict | None = None
        self.set_interval(0.5, self._poll)

    def _poll(self) -> None:
        self._update_topology()
        self._read_events()

    def _update_topology(self) -> None:
        active = state_module.read_active()
        fully_up = topology.is_fully_up()

        topo = self.query_one(TopologyPanel)
        topo.update_state(active, fully_up)

        if active != self._last_active and active is not None and self._last_active is None:
            self._file_pos = 0
            self.query_one("#attack-log", RichLog).clear()
            self.query_one("#defense-log", RichLog).clear()
        self._last_active = active

    def _read_events(self) -> None:
        log_path = state_module.tui_log_path()
        if not log_path.exists():
            return
        try:
            with open(log_path, "r") as f:
                f.seek(0, 2)
                size = f.tell()
                if size < self._file_pos:
                    self._file_pos = 0
                    self.query_one("#attack-log", RichLog).clear()
                    self.query_one("#defense-log", RichLog).clear()

                f.seek(self._file_pos)
                for raw_line in f:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        event = json.loads(raw_line)
                        self._route_event(event)
                    except json.JSONDecodeError:
                        pass
                self._file_pos = f.tell()
        except OSError:
            pass

    def _route_event(self, event: dict) -> None:
        etype = event.get("event_type", "")
        if etype.startswith("netlab.defense."):
            line = _format_defense(event)
            self.query_one("#defense-log", RichLog).write(line)
        else:
            line = _format_attack(event)
            self.query_one("#attack-log", RichLog).write(line)

    def action_refresh(self) -> None:
        self._update_topology()

    def action_clear_logs(self) -> None:
        self.query_one("#attack-log", RichLog).clear()
        self.query_one("#defense-log", RichLog).clear()
        self._file_pos = 0


def run_tui() -> None:
    app = NetLabApp()
    app.run()


if __name__ == "__main__":
    run_tui()
