#!/usr/bin/env python3
"""netlab live TUI — side-by-side attack and defense event feed."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Label, RichLog, Static

from netlab import state as state_module
from netlab import topology
from netlab.scenarios import list_scenarios, get_scenario
from netlab.defenses import list_defenses, get_defense


_SEVERITY_STYLE = {
    "info":     "dim",
    "low":      "white",
    "medium":   "yellow",
    "high":     "bold red",
    "critical": "bold red on dark_red",
}

_ATTACK_PREFIXES = (
    "netlab.scenario.",
    "netlab.lifecycle.",
    "netlab.pair.",
)


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
            label = f"  ⚠ static ARP failed"
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


class StatusBar(Static):
    """Single-line header showing lab state and active run."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active: dict | None = None
        self._up: bool = False
        self._start_ts: float | None = None

    def update_state(self, active: dict | None, fully_up: bool) -> None:
        if active != self._active:
            self._active = active
            self._start_ts = time.time() if active else None
        self._up = fully_up
        self.refresh()

    def render(self) -> str:
        lab = "[green]● UP[/green]" if self._up else "[red]● DOWN[/red]"

        if self._active:
            sc = self._active.get("scenario", "?")
            elapsed = int(time.time() - self._start_ts) if self._start_ts else 0
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            timer = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
            run_info = f"[bold]{sc}[/bold]  elapsed: [cyan]{timer}[/cyan]"
        else:
            run_info = "[dim]no active run[/dim]"

        return f" {lab}    {run_info}"


class BottomGrid(Static):
    """Scenario and defense names as a quick-reference grid."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._scenarios: list[str] = []
        self._defenses: list[dict] = []

    def update_items(self, scenarios: list[str], defenses: list[dict]) -> None:
        self._scenarios = scenarios
        self._defenses = defenses
        self.refresh()

    def render(self) -> str:
        sc_names = "  ".join(self._scenarios) if self._scenarios else "—"
        def_names = "  ".join(d["name"] for d in self._defenses) if self._defenses else "—"
        return f" [dim]scenarios:[/dim]  {sc_names}\n [dim]defenses:[/dim]   {def_names}"


class NetLabApp(App):
    CSS = """
    Screen {
        background: $surface;
    }

    StatusBar {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
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

    BottomGrid {
        height: 3;
        background: $panel;
        padding: 0 1;
        border-top: tall $primary-darken-2;
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

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status-bar")
        with Horizontal(id="panels"):
            with Vertical(id="attack-pane"):
                yield Label("ATTACK", id="attack-label", classes="pane-label")
                yield RichLog(id="attack-log", highlight=False, markup=True, wrap=True)
            with Vertical(id="defense-pane"):
                yield Label("DEFENSE", id="defense-label", classes="pane-label")
                yield RichLog(id="defense-log", highlight=False, markup=True, wrap=True)
        yield BottomGrid(id="bottom-grid")
        yield Footer()

    def on_mount(self) -> None:
        self._file_pos = 0
        self._last_active: dict | None = None
        self.set_interval(0.5, self._poll)

    def _poll(self) -> None:
        self._update_status()
        self._read_events()

    def _update_status(self) -> None:
        active = state_module.read_active()
        fully_up = topology.is_fully_up()

        status = self.query_one(StatusBar)
        status.update_state(active, fully_up)

        # Reset log position and clear panels when a new run starts
        if active != self._last_active and active is not None and self._last_active is None:
            self._file_pos = 0
            self.query_one("#attack-log", RichLog).clear()
            self.query_one("#defense-log", RichLog).clear()
        self._last_active = active

        bottom = self.query_one(BottomGrid)
        sc_names = []
        for name in list_scenarios():
            try:
                sc_names.append(name)
            except Exception:
                pass
        def_items = []
        for name in list_defenses():
            try:
                d = get_defense(name)
                def_items.append({"name": name, "mitigates": d.mitigates})
            except Exception:
                pass
        bottom.update_items(sc_names, def_items)

    def _read_events(self) -> None:
        log_path = state_module.tui_log_path()
        if not log_path.exists():
            return
        try:
            with open(log_path, "r") as f:
                # If file was truncated (new run started), reset cursor
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
        self._update_status()

    def action_clear_logs(self) -> None:
        self.query_one("#attack-log", RichLog).clear()
        self.query_one("#defense-log", RichLog).clear()
        self._file_pos = 0


def run_tui() -> None:
    app = NetLabApp()
    app.run()


if __name__ == "__main__":
    run_tui()
