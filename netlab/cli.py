from __future__ import annotations

import os
import sys
import subprocess
import time
import shutil
import signal
import json
from pathlib import Path
from subprocess import TimeoutExpired

import click

from netlab import __version__
from netlab import events
from netlab import topology
from netlab import state
from netlab.scenarios import list_scenarios, get_scenario
from netlab.scenarios.base import ScenarioContext
from netlab.defenses import list_defenses, get_defense
from netlab.defenses.base import DefenseContext
from netlab.output import make_output, TeeOutput, FileOutput


def require_root():
    if os.geteuid() != 0:
        click.echo("[!] netlab requires root. Run with sudo.", err=True)
        sys.exit(1)


@click.group()
@click.option("-q", "--quiet", is_flag=True, default=False, help="Suppress info output")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Verbose output")
@click.pass_context
def main(ctx, quiet, verbose):
    ctx.ensure_object(dict)
    ctx.obj["quiet"] = quiet
    ctx.obj["verbose"] = verbose


@main.command()
def list():
    """List available scenarios"""
    rows = []
    for name in list_scenarios():
        try:
            sc = get_scenario(name)
            desc = sc.description
            severity = sc.expected_duration_seconds
        except Exception:
            desc = "<error loading>"
            severity = ""
        rows.append((name, desc, str(severity)))

    if not rows:
        click.echo("No scenarios registered")
        return

    click.echo(f"{'NAME':20} {'DESCRIPTION':50} {'DURATION':8}")
    for r in rows:
        click.echo(f"{r[0]:20} {r[1]:50} {r[2]:8}")


@main.command()
def dashboard():
    """Show a compact UI-style snapshot of the lab"""
    active = state.read_active()
    fully_up = topology.is_fully_up()
    clean = topology.is_clean()
    residual = topology.residual_state()

    click.echo(click.style("netlab dashboard", bold=True))
    click.echo(f"Version: {__version__}")
    click.echo(f"Lab state: {click.style('fully up', fg='green', bold=True) if fully_up else click.style('not fully up', fg='red', bold=True)}")
    click.echo(f"Clean state: {click.style('clean', fg='green', bold=True) if clean else click.style('dirty', fg='red', bold=True)}")

    click.echo(click.style("Active run", bold=True))
    if active:
        click.echo(f"  scenario: {active.get('scenario')}")
        click.echo(f"  pid: {active.get('pid')}")
        click.echo(f"  started_at: {active.get('started_at')}")
    else:
        click.echo("  none")

    click.echo(click.style("Residual state", bold=True))
    if residual:
        for item in residual:
            click.echo(f"  - {item}")
    else:
        click.echo("  none")

    click.echo(click.style("Scenarios", bold=True))
    for name in list_scenarios():
        try:
            sc = get_scenario(name)
            desc = sc.description
            duration = sc.expected_duration_seconds
        except Exception:
            desc = "<error loading>"
            duration = ""
        click.echo(f"  {name:12} {desc} ({duration}s)")


@main.command()
@click.argument("scenario_name")
def describe(scenario_name: str):
    """Show scenario manifest details"""
    require_root()
    try:
        sc = get_scenario(scenario_name)
    except KeyError:
        click.echo(f"Unknown scenario: {scenario_name}", err=True)
        sys.exit(1)

    click.echo(f"name: {sc.name}")
    click.echo(f"description: {sc.description}")
    click.echo(f"required_tools: {sc.required_tools}")
    click.echo(f"required_namespaces: {sc.required_namespaces}")
    click.echo(f"expected_duration_seconds: {sc.expected_duration_seconds}")
    click.echo("parameters:")
    for k, v in sc.parameters.items():
        click.echo(f"  - {k}: {v}")


@main.command()
@click.argument("scenario_name")
@click.option("--output", type=click.Choice(["stdout", "file", "http_post"]), default="stdout")
@click.option("--output-url", default=None)
@click.option("--output-file", default=None)
@click.option("--auth-header", default=None,
              help="Authorization header for http_post output (e.g. 'Authorization: Bearer token').")
@click.option("--batch-size", default=1, type=int, help="Events per HTTP POST batch (http_post output only).")
@click.option("--no-setup", is_flag=True, default=False)
@click.option("--no-teardown", is_flag=True, default=False)
@click.option("--params", multiple=True, help="KEY=VALUE parameters")
@click.option("--dry-run", is_flag=True, default=False, help="Preflight check only; do not run the scenario.")
def run(scenario_name, output, output_url, output_file, auth_header, batch_size, no_setup, no_teardown, params, dry_run):
    """Execute a scenario end-to-end"""
    require_root()

    out = make_output(output, url=output_url, path=output_file, auth_header=auth_header, batch_size=batch_size)
    state.clear_tui_log()
    out = TeeOutput(out, FileOutput(str(state.tui_log_path())))
    events.set_output(out)

    try:
        sc = get_scenario(scenario_name)
    except KeyError:
        click.echo(f"Unknown scenario: {scenario_name}", err=True)
        sys.exit(1)

    parsed_params = {}
    for p in params:
        if "=" not in p:
            click.echo(f"Invalid param '{p}', expected KEY=VALUE", err=True)
            sys.exit(1)
        k, v = p.split("=", 1)
        parsed_params[k] = v

    missing = []
    for tool in sc.required_tools:
        if shutil.which(tool) is None:
            missing.append(tool)

    if dry_run:
        ok = True
        click.echo(click.style("Preflight check", bold=True))
        click.echo(f"  scenario:    {sc.name}")
        click.echo(f"  description: {sc.description}")
        click.echo(f"  duration:    {sc.expected_duration_seconds}s")
        click.echo(f"  params:      {parsed_params or '(defaults)'}")
        if missing:
            click.echo(click.style(f"  tools:       MISSING — {', '.join(missing)}", fg="red"))
            ok = False
        else:
            click.echo(click.style(f"  tools:       ok ({', '.join(sc.required_tools) or 'none required'})", fg="green"))
        if not no_setup and not topology.is_clean():
            click.echo(click.style("  topology:    dirty (run 'netlab clean' first)", fg="red"))
            ok = False
        else:
            click.echo(click.style("  topology:    clean", fg="green"))
        if state.read_active() is not None:
            click.echo(click.style("  active run:  another run is active", fg="red"))
            ok = False
        else:
            click.echo(click.style("  active run:  none", fg="green"))
        try:
            from netlab.scenarios.base import ScenarioContext
            dummy_ctx = ScenarioContext(params=parsed_params, emit_event=lambda *a: None, aborted_check=lambda: False)
            sc._merge_params(dummy_ctx)
            click.echo(click.style("  params:      valid", fg="green"))
        except ValueError as exc:
            click.echo(click.style(f"  params:      INVALID — {exc}", fg="red"))
            ok = False
        click.echo(click.style("Result: READY" if ok else "Result: NOT READY", bold=True, fg="green" if ok else "red"))
        sys.exit(0 if ok else 1)

    if missing:
        click.echo(f"Missing required tools: {', '.join(missing)}", err=True)
        sys.exit(1)

    if state.read_active() is not None:
        click.echo("Another netlab run appears active; aborting.", err=True)
        sys.exit(1)

    if not no_setup and not topology.is_clean():
        click.echo("Lab is not clean; run 'netlab clean' or use --no-setup if intentional.", err=True)
        sys.exit(1)

    aborted = {"flag": False}

    def _handle_signal(signum, frame):
        aborted["flag"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGHUP, _handle_signal)

    def aborted_check() -> bool:
        return aborted["flag"]

    payload = state.make_active_payload(os.getpid(), scenario_name, sc.required_namespaces, topology.BRIDGE)
    try:
        state.write_active(payload)
    except Exception:
        click.echo("Failed to write active state file; check permissions.", err=True)
        sys.exit(1)

    try:
        if not no_setup:
            subprocess.run(["bash", str(Path(__file__).resolve().parents[1] / "lab" / "setup.sh")], check=True)
    except subprocess.CalledProcessError as e:
        events.emit_event("netlab.scenario.aborted", "high", {"scenario": scenario_name, "reason": "setup_failed"})
        # attempt teardown
        try:
            topology.teardown()
        except Exception:
            pass
        state.remove_active()
        sys.exit(1)

    events.emit_event("netlab.scenario.started", "info", {"scenario": scenario_name, "params": parsed_params})

    time.sleep(1)
    events.emit_event("netlab.lifecycle.warming_up", "info", {"scenario": scenario_name})

    success = False
    reason = ""
    start_ts = None
    try:
        start_ts = time.time()
        ctx = ScenarioContext(
            params=parsed_params, emit_event=events.emit_event, aborted_check=aborted_check
        )
        sc.run(ctx)
        if aborted_check():
            reason = "aborted by signal"
        else:
            success = True
    except Exception as exc:  # scenario crashed
        reason = str(exc)
        events.emit_event("netlab.scenario.event", "high", {"scenario": scenario_name, "step": "exception", "details": {"error": reason}})
    finally:
        duration = None
        if start_ts is not None:
            duration = time.time() - start_ts

    if success:
        events.emit_event("netlab.scenario.completed", "info", {"scenario": scenario_name, "duration_seconds": duration})
    else:
        events.emit_event("netlab.scenario.aborted", "high", {"scenario": scenario_name, "reason": reason or "aborted"})

    events.emit_event("netlab.lifecycle.tearing_down", "info", {"scenario": scenario_name})
    dirty = False
    if not no_teardown:
        try:
            topology.teardown()
        except TimeoutExpired:
            click.echo("Teardown timed out; marking dirty", err=True)
            dirty = True
        except Exception:
            dirty = True

    residual = topology.residual_state()
    if residual:
        dirty = True

    if dirty:
        events.emit_event("netlab.lifecycle.dirty", "critical", {"scenario": scenario_name, "residual": residual})
    else:
        events.emit_event("netlab.lifecycle.clean", "info", {"scenario": scenario_name, "duration_seconds": duration})

    state.remove_active()
    events.flush()

    if dirty:
        sys.exit(2)
    if not success:
        sys.exit(1)
    sys.exit(0)


@main.command()
def clean():
    """Tear down any leftover lab state"""
    require_root()
    click.echo("Running teardown script...")
    try:
        topology.teardown()
    except subprocess.TimeoutExpired:
        click.echo("Teardown timed out", err=True)
    state.remove_active()
    click.echo("Clean complete (best-effort)")


@main.command()
@click.option("--json", "as_json", is_flag=True, default=False, help="Output machine-readable JSON.")
def status(as_json):
    """Report lab and scenario state"""
    require_root()
    if as_json:
        data = {
            "topology": {
                "fully_up": topology.is_fully_up(),
                "clean": topology.is_clean(),
                "residual": topology.residual_state(),
            },
            "active": state.read_active(),
        }
        click.echo(json.dumps(data, indent=2))
        return
    try:
        subprocess.run([str(Path(__file__).resolve().parents[1] / "lab" / "status.sh")], check=False)
    except Exception:
        pass
    active = state.read_active()
    if active:
        click.echo(f"Active scenario: {active.get('scenario')} (pid {active.get('pid')})")
    else:
        click.echo("No active scenario")


@main.command()
def version():
    """Print version + git commit"""
    git_hash = "unknown"
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        if res.returncode == 0:
            git_hash = res.stdout.strip()
    except Exception:
        pass
    click.echo(f"netlab {__version__} ({git_hash})")


@main.command()
def defenses():
    """List available defenses"""
    rows = []
    for name in list_defenses():
        try:
            d = get_defense(name)
            rows.append((name, d.description, ", ".join(d.mitigates)))
        except Exception:
            rows.append((name, "<error loading>", ""))

    if not rows:
        click.echo("No defenses registered")
        return

    click.echo(f"{'NAME':15} {'DESCRIPTION':55} {'MITIGATES'}")
    for r in rows:
        click.echo(f"{r[0]:15} {r[1]:55} {r[2]}")


@main.command()
@click.argument("defense_name")
@click.option("--output", type=click.Choice(["stdout", "file", "http_post"]), default="stdout")
@click.option("--output-url", default=None)
@click.option("--output-file", default=None)
@click.option("--auth-header", default=None)
@click.option("--no-setup", is_flag=True, default=False)
@click.option("--no-teardown", is_flag=True, default=False)
@click.option("--params", multiple=True, help="KEY=VALUE parameters")
def defend(defense_name, output, output_url, output_file, auth_header, no_setup, no_teardown, params):
    """Apply a defense and hold it until Ctrl+C"""
    require_root()

    out = make_output(output, url=output_url, path=output_file, auth_header=auth_header)
    state.clear_tui_log()
    out = TeeOutput(out, FileOutput(str(state.tui_log_path())))
    events.set_output(out)

    try:
        d = get_defense(defense_name)
    except KeyError:
        click.echo(f"Unknown defense: {defense_name}", err=True)
        sys.exit(1)

    parsed_params = {}
    for p in params:
        if "=" not in p:
            click.echo(f"Invalid param '{p}', expected KEY=VALUE", err=True)
            sys.exit(1)
        k, v = p.split("=", 1)
        parsed_params[k] = v

    missing = [t for t in d.required_tools if shutil.which(t) is None]
    if missing:
        click.echo(f"Missing required tools: {', '.join(missing)}", err=True)
        sys.exit(1)

    if not no_setup and not topology.is_fully_up():
        try:
            subprocess.run(["bash", str(Path(__file__).resolve().parents[1] / "lab" / "setup.sh")], check=True)
        except subprocess.CalledProcessError:
            click.echo("Lab setup failed", err=True)
            sys.exit(1)

    aborted = {"flag": False}

    def _handle_signal(signum, frame):
        aborted["flag"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGHUP, _handle_signal)

    ctx = DefenseContext(
        params=parsed_params,
        emit_event=events.emit_event,
        aborted_check=lambda: aborted["flag"],
    )

    try:
        d.apply(ctx)
        click.echo(f"Defense '{defense_name}' active — press Ctrl+C to stop")
        while not aborted["flag"]:
            time.sleep(0.5)
    except Exception as exc:
        click.echo(f"Defense error: {exc}", err=True)
    finally:
        d.remove(ctx)
        events.flush()

    if not no_teardown:
        try:
            topology.teardown()
        except Exception:
            pass
        state.remove_active()


@main.command()
@click.argument("scenario_name")
@click.argument("defense_name")
@click.option("--output", type=click.Choice(["stdout", "file", "http_post"]), default="stdout")
@click.option("--output-url", default=None)
@click.option("--output-file", default=None)
@click.option("--auth-header", default=None)
@click.option("--batch-size", default=1, type=int)
@click.option("--no-setup", is_flag=True, default=False)
@click.option("--no-teardown", is_flag=True, default=False)
@click.option("--scenario-params", multiple=True, help="KEY=VALUE for the scenario")
@click.option("--defense-params", multiple=True, help="KEY=VALUE for the defense")
@click.option("--mode", type=click.Choice(["pre-apply", "concurrent"]), default="pre-apply",
              help="pre-apply: defense starts before attack (default). concurrent: both start simultaneously.")
def pair(scenario_name, defense_name, output, output_url, output_file, auth_header,
         batch_size, no_setup, no_teardown, scenario_params, defense_params, mode):
    """Apply a defense then run an attack against it"""
    require_root()

    out = make_output(output, url=output_url, path=output_file, auth_header=auth_header, batch_size=batch_size)
    state.clear_tui_log()
    out = TeeOutput(out, FileOutput(str(state.tui_log_path())))
    events.set_output(out)

    try:
        sc = get_scenario(scenario_name)
    except KeyError:
        click.echo(f"Unknown scenario: {scenario_name}", err=True)
        sys.exit(1)

    try:
        d = get_defense(defense_name)
    except KeyError:
        click.echo(f"Unknown defense: {defense_name}", err=True)
        sys.exit(1)

    def _parse_params(raw):
        result = {}
        for p in raw:
            if "=" not in p:
                click.echo(f"Invalid param '{p}', expected KEY=VALUE", err=True)
                sys.exit(1)
            k, v = p.split("=", 1)
            result[k] = v
        return result

    parsed_sc_params = _parse_params(scenario_params)
    parsed_def_params = _parse_params(defense_params)

    missing = [t for t in sc.required_tools + d.required_tools if shutil.which(t) is None]
    if missing:
        click.echo(f"Missing required tools: {', '.join(set(missing))}", err=True)
        sys.exit(1)

    if state.read_active() is not None:
        click.echo("Another netlab run appears active; aborting.", err=True)
        sys.exit(1)

    if not no_setup and not topology.is_clean():
        click.echo("Lab is not clean; run 'netlab clean' first.", err=True)
        sys.exit(1)

    aborted = {"flag": False}

    def _handle_signal(signum, frame):
        aborted["flag"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGHUP, _handle_signal)

    def_ctx = DefenseContext(
        params=parsed_def_params,
        emit_event=events.emit_event,
        aborted_check=lambda: aborted["flag"],
    )
    sc_ctx = ScenarioContext(
        params=parsed_sc_params,
        emit_event=events.emit_event,
        aborted_check=lambda: aborted["flag"],
    )

    payload = state.make_active_payload(os.getpid(), scenario_name, sc.required_namespaces, topology.BRIDGE)
    try:
        state.write_active(payload)
    except Exception:
        click.echo("Failed to write active state file; check permissions.", err=True)
        sys.exit(1)

    events.emit_event("netlab.pair.started", "info", {
        "scenario": scenario_name,
        "defense": defense_name,
    })

    if not no_setup:
        try:
            subprocess.run(["bash", str(Path(__file__).resolve().parents[1] / "lab" / "setup.sh")], check=True)
        except subprocess.CalledProcessError:
            events.emit_event("netlab.scenario.aborted", "high", {"scenario": scenario_name, "reason": "setup_failed"})
            try:
                topology.teardown()
            except Exception:
                pass
            state.remove_active()
            events.flush()
            sys.exit(1)

    events.emit_event("netlab.lifecycle.warming_up", "info", {"scenario": scenario_name})

    # Apply defense (mode controls startup timing vs attack)
    _defense_apply_error = None
    try:
        d.apply(def_ctx)
    except Exception as exc:
        _defense_apply_error = str(exc)
        events.emit_event("netlab.defense.applied", "high", {
            "defense": defense_name,
            "step": "apply_failed",
            "details": {"error": _defense_apply_error},
        })

    if mode == "pre-apply":
        # Give the defense a moment to initialize before the attack starts
        time.sleep(1)
    # concurrent mode: attack starts immediately after apply() returns

    # Run attack
    success = False
    reason = ""
    start_ts = None
    try:
        start_ts = time.time()
        events.emit_event("netlab.scenario.started", "info", {
            "scenario": scenario_name,
            "defense": defense_name,
            "mode": mode,
            "params": parsed_sc_params,
        })
        sc.run(sc_ctx)
        if aborted["flag"]:
            reason = "aborted by signal"
        else:
            success = True
    except Exception as exc:
        reason = str(exc)
        events.emit_event("netlab.scenario.event", "high", {
            "scenario": scenario_name,
            "step": "exception",
            "details": {"error": reason},
        })
    finally:
        duration = time.time() - start_ts if start_ts else None

    if success:
        events.emit_event("netlab.scenario.completed", "info", {
            "scenario": scenario_name,
            "duration_seconds": duration,
        })
    else:
        events.emit_event("netlab.scenario.aborted", "high", {
            "scenario": scenario_name,
            "reason": reason or "aborted",
        })

    # Remove defense after attack
    d.remove(def_ctx)

    # Emit pair summary
    events.emit_event("netlab.pair.summary", "info", {
        "scenario": scenario_name,
        "defense": defense_name,
        "duration_seconds": duration,
        "attack_success": success,
        "defense_alerts": len(d.alerts),
        "alert_messages": d.alerts,
    })

    events.emit_event("netlab.lifecycle.tearing_down", "info", {"scenario": scenario_name})
    dirty = False
    if not no_teardown:
        try:
            topology.teardown()
        except TimeoutExpired:
            dirty = True
        except Exception:
            dirty = True

    residual = topology.residual_state()
    if residual:
        dirty = True

    if dirty:
        events.emit_event("netlab.lifecycle.dirty", "critical", {
            "scenario": scenario_name,
            "residual": residual,
        })
    else:
        events.emit_event("netlab.lifecycle.clean", "info", {
            "scenario": scenario_name,
            "duration_seconds": duration,
        })

    state.remove_active()
    events.flush()
    sys.exit(0 if success else 1)


class _AssertionCollector:
    """Wraps emit_event to capture steps and alerts for post-run assertion checking."""

    def __init__(self, inner_emit):
        self._inner = inner_emit
        self.steps: list[str] = []
        self.alerts: list[str] = []

    def emit_event(self, event_type: str, severity: str, payload: dict) -> None:
        self._inner(event_type, severity, payload)
        if event_type == "netlab.scenario.event":
            step = payload.get("step", "")
            if step:
                self.steps.append(step)
        elif event_type == "netlab.defense.alert":
            msg = payload.get("message", "")
            if msg:
                self.alerts.append(msg)

    def check_scenario(self, sc) -> tuple[bool, list[str]]:
        missing = [s for s in sc.expected_steps if s not in self.steps]
        return len(missing) == 0, missing

    def check_defense(self, d, scenario_name: str) -> tuple[bool, list[str], bool]:
        patterns = d.expected_alerts_for.get(scenario_name, [])
        if not patterns:
            return True, [], False
        missing = [p for p in patterns if not any(p in a for a in self.alerts)]
        return len(missing) == 0, missing, True


def _test_run(netlab_bin: str, args: list[str]) -> int:
    """Run a netlab subcommand silently, return exit code."""
    return subprocess.run(
        [netlab_bin] + args + ["--output", "file", "--output-file", "/dev/null"],
        capture_output=True,
    ).returncode


def _read_tui_log_events() -> list[dict]:
    """Read all events from the current TUI log file."""
    log = state.tui_log_path()
    events_list = []
    if not log.exists():
        return events_list
    try:
        with open(log) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events_list.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except OSError:
        pass
    return events_list


def _steps_from_events(evts: list[dict]) -> list[str]:
    return [e["payload"].get("step", "") for e in evts
            if e.get("event_type") == "netlab.scenario.event" and e.get("payload", {}).get("step")]


def _alerts_from_events(evts: list[dict]) -> list[str]:
    return [e["payload"].get("message", "") for e in evts
            if e.get("event_type") == "netlab.defense.alert" and e.get("payload", {}).get("message")]


@main.command(name="test")
@click.option("--filter", "filter_", default=None, metavar="SCENARIO",
              help="Only run tests for this scenario.")
@click.option("--with-suricata", is_flag=True, default=False,
              help="Validate Suricata rules against pre-recorded pcaps (requires suricata).")
def test_cmd(filter_, with_suricata):
    """Run the regression test suite — checks scenario steps and defense alerts."""
    require_root()

    import sys as _sys
    netlab_bin = str(Path(_sys.executable).parent / "netlab")

    scenarios_to_test = [n for n in list_scenarios()
                         if filter_ is None or n == filter_]
    if not scenarios_to_test:
        click.echo(f"No scenarios match filter: {filter_}", err=True)
        sys.exit(1)

    # Build pair test cases: only pairs with declared expected alerts
    pair_tests = []
    for sc_name in scenarios_to_test:
        for def_name in list_defenses():
            d = get_defense(def_name)
            if d.expected_alerts_for.get(sc_name):
                pair_tests.append((sc_name, def_name))

    total = len(scenarios_to_test) + len(pair_tests)
    passed = 0
    failed = 0
    skipped = 0
    idx = 0

    WIDTH = 42

    click.echo(click.style("netlab test suite", bold=True))
    click.echo("─" * 60)

    # --- Standalone scenario tests ---
    for sc_name in scenarios_to_test:
        sc = get_scenario(sc_name)
        idx += 1
        label = f"[{idx}/{total}]  {sc_name}"
        click.echo(f"{label:<{WIDTH}} running...", nl=False)

        # Use short durations for test runs
        sc_params = ["--params", "duration=12"] if sc_name != "syn_flood" else ["--params", "count=300", "--params", "pps=200"]
        rc = _test_run(netlab_bin, ["run", sc_name] + sc_params)

        evts = _read_tui_log_events()
        steps = _steps_from_events(evts)

        sc_passed, missing = (True, []) if not sc.expected_steps else (
            all(s in steps for s in sc.expected_steps),
            [s for s in sc.expected_steps if s not in steps],
        )
        run_ok = rc in (0,)

        if not run_ok:
            result = click.style("FAIL", fg="red", bold=True)
            detail = f"exit code {rc}"
            failed += 1
        elif not sc_passed:
            result = click.style("FAIL", fg="red", bold=True)
            detail = f"missing steps: {', '.join(missing)}"
            failed += 1
        else:
            result = click.style("PASS", fg="green", bold=True)
            detail = "steps: " + ", ".join(f"{s} ✓" for s in sc.expected_steps) if sc.expected_steps else "completed"
            passed += 1

        click.echo(f"\r{label:<{WIDTH}} {result}  {detail}")

    # --- Pair tests ---
    for sc_name, def_name in pair_tests:
        d = get_defense(def_name)
        idx += 1
        label = f"[{idx}/{total}]  {sc_name} × {def_name}"
        click.echo(f"{label:<{WIDTH}} running...", nl=False)

        sc_params = ["--scenario-params", "duration=12"] if sc_name != "syn_flood" else ["--scenario-params", "count=300"]
        rc = _test_run(netlab_bin, ["pair", sc_name, def_name] + sc_params)

        evts = _read_tui_log_events()
        steps = _steps_from_events(evts)
        alerts = _alerts_from_events(evts)

        patterns = d.expected_alerts_for.get(sc_name, [])
        missing_alerts = [p for p in patterns if not any(p in a for a in alerts)]
        run_ok = rc in (0,)

        if not run_ok:
            result = click.style("FAIL", fg="red", bold=True)
            detail = f"exit code {rc}"
            failed += 1
        elif missing_alerts:
            result = click.style("FAIL", fg="red", bold=True)
            detail = f"alerts not fired: {', '.join(missing_alerts)}"
            failed += 1
        else:
            result = click.style("PASS", fg="green", bold=True)
            fired = len(alerts)
            detail = f"{fired} alert(s) fired"
            passed += 1

        click.echo(f"\r{label:<{WIDTH}} {result}  {detail}")

    # --- Suricata rule validation ---
    if with_suricata:
        suricata_bin = shutil.which("suricata")
        repo_root = Path(__file__).resolve().parents[1]
        rules_file = repo_root / "defenses" / "03-ids" / "suricata-custom.rules"
        captures_dir = repo_root / "captures"

        pcap_map = {
            "01-arp-spoof.pcap": [2000001],
            "02-mitm.pcap":      [2000001],
            "03-dns-poison.pcap": [2000001, 2000003],
            "04-syn-flood.pcap": [2000002],
        }

        if not suricata_bin:
            click.echo("\nSuricata:  " + click.style("SKIP", fg="yellow") + "  not installed")
        else:
            click.echo("\n" + click.style("Suricata rule validation", bold=True))
            click.echo("─" * 60)
            suricata_cfg = None
            for candidate in ["/etc/suricata/suricata.yaml", "/usr/share/suricata/suricata.yaml"]:
                if Path(candidate).exists():
                    suricata_cfg = candidate
                    break

            if not suricata_cfg:
                click.echo("  " + click.style("SKIP", fg="yellow") + "  no suricata.yaml found in /etc/suricata or /usr/share/suricata")
            else:
                import tempfile
                for pcap_name, expected_sids in pcap_map.items():
                    if filter_ and not any(filter_ in pcap_name for _ in [None]):
                        pass  # respect filter roughly
                    pcap = captures_dir / pcap_name
                    if not pcap.exists():
                        click.echo(f"  {pcap_name:<30} " + click.style("SKIP", fg="yellow") + "  pcap not found")
                        continue
                    with tempfile.TemporaryDirectory() as tmpdir:
                        res = subprocess.run(
                            [suricata_bin, "-r", str(pcap), "-S", str(rules_file),
                             "-l", tmpdir, "-c", suricata_cfg, "--set", "default-rule-path=/"],
                            capture_output=True, timeout=30,
                        )
                        fast_log = Path(tmpdir) / "fast.log"
                        fired_sids = set()
                        if fast_log.exists():
                            for line in fast_log.read_text().splitlines():
                                for sid in expected_sids:
                                    if f"[{sid}:" in line or f"[{sid}]" in line:
                                        fired_sids.add(sid)
                        missing_sids = [s for s in expected_sids if s not in fired_sids]
                        if missing_sids:
                            click.echo(f"  {pcap_name:<30} " + click.style("FAIL", fg="red", bold=True) + f"  SIDs not fired: {missing_sids}")
                        else:
                            click.echo(f"  {pcap_name:<30} " + click.style("PASS", fg="green", bold=True) + f"  SIDs fired: {expected_sids}")

    click.echo("─" * 60)
    summary = (
        click.style(f"{passed} passed", fg="green", bold=True) + "  " +
        (click.style(f"{failed} failed", fg="red", bold=True) if failed else f"{failed} failed") +
        f"  {skipped} skipped"
    )
    click.echo(summary)
    sys.exit(0 if failed == 0 else 1)


@main.command()
def tui():
    """Launch the live TUI dashboard"""
    try:
        from netlab.tui import run_tui
        run_tui()
    except ImportError as e:
        click.echo("Textual not installed. Install with: pip install textual", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"TUI error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

