#!/usr/bin/env python3
"""Live TUI for netlab using Textual."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import ComposeResult, RenderResult
from textual.containers import Container, Vertical, Horizontal
from textual.reactive import reactive
from textual.widgets import Header, Footer, Static
from textual.app import App
from textual.binding import Binding

from netlab import topology, state
from netlab.scenarios import list_scenarios, get_scenario


class LabStatus(Static):
    """Real-time lab status widget."""

    fully_up: reactive[bool] = reactive(False)
    clean: reactive[bool] = reactive(False)
    residual: reactive[list] = reactive([])
    active: reactive[dict | None] = reactive(None)

    def render(self) -> RenderResult:
        up_str = "[green]✓ fully up[/green]" if self.fully_up else "[red]✗ not up[/red]"
        clean_str = "[green]✓ clean[/green]" if self.clean else "[red]✗ dirty[/red]"
        
        lines = [
            "[bold]Lab Status[/bold]",
            f"  Topology: {up_str}",
            f"  State: {clean_str}",
        ]
        
        if self.residual:
            lines.append("[bold]Residual:[/bold]")
            for item in self.residual:
                lines.append(f"    - {item}")
        
        if self.active:
            lines.append(f"[bold]Active Scenario[/bold]")
            lines.append(f"  scenario: {self.active.get('scenario')}")
            lines.append(f"  pid: {self.active.get('pid')}")
        else:
            lines.append("[dim]No active scenario[/dim]")
        
        return "\n".join(lines)


class ScenarioList(Static):
    """List of available scenarios."""

    scenarios: reactive[list] = reactive([])

    def render(self) -> RenderResult:
        lines = ["[bold]Scenarios[/bold]"]
        
        if not self.scenarios:
            lines.append("[dim]Loading...[/dim]")
            return "\n".join(lines)
        
        for i, (name, desc, duration) in enumerate(self.scenarios, 1):
            lines.append(f"  [{i}] {name:12} {desc} ({duration}s)")
        
        lines.append("")
        lines.append("[dim]Press [Q] to quit | [R] to refresh[/dim]")
        
        return "\n".join(lines)


class NetLabApp(App):
    """Live Netlab TUI application."""

    TITLE = "netlab - Live Dashboard"
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def compose(self) -> ComposeResult:
        """Create the app layout."""
        yield Header()
        
        # Main content container
        with Vertical(id="main"):
            with Horizontal(id="top"):
                yield LabStatus(id="lab_status")
            
            with Horizontal(id="bottom"):
                yield ScenarioList(id="scenarios")
        
        yield Footer()

    def on_mount(self) -> None:
        """Start the refresh loop."""
        self.set_interval(1.0, self._update_state)

    def _update_state(self) -> None:
        """Poll lab state and update widgets."""
        lab_status = self.query_one(LabStatus)
        scenario_list = self.query_one(ScenarioList)
        
        # Update lab status
        lab_status.fully_up = topology.is_fully_up()
        lab_status.clean = topology.is_clean()
        lab_status.residual = topology.residual_state()
        lab_status.active = state.read_active()
        
        # Update scenario list
        scenarios = []
        for name in list_scenarios():
            try:
                sc = get_scenario(name)
                desc = getattr(sc, "description", "")
                duration = getattr(sc, "expected_duration_seconds", "")
            except Exception:
                desc = "<error loading>"
                duration = ""
            scenarios.append((name, desc, str(duration)))
        
        scenario_list.scenarios = scenarios

    def action_refresh(self) -> None:
        """Manually refresh state."""
        self._update_state()


def run_tui() -> None:
    """Launch the TUI application."""
    app = NetLabApp()
    app.run()


if __name__ == "__main__":
    run_tui()
