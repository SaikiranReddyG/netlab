import os
import sys
import subprocess
from pathlib import Path
from typing import Dict

import click

from netlab import __version__
from netlab import events
from netlab import topology
from netlab import state
from netlab.scenarios import list_scenarios, get_scenario


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
            desc = getattr(sc, "description", "")
            severity = getattr(sc, "expected_duration_seconds", "")
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
    click.echo(f"required_tools: {getattr(sc, 'required_tools', [])}")
    click.echo(f"required_namespaces: {getattr(sc, 'required_namespaces', [])}")
    click.echo(f"expected_duration_seconds: {getattr(sc, 'expected_duration_seconds', '')}")
    click.echo("parameters:")
    for k, v in getattr(sc, "parameters", {}).items():
        click.echo(f"  - {k}: {v}")


@main.command()
@click.argument("scenario_name")
@click.option("--output", type=click.Choice(["stdout", "file", "http_post"]), default="stdout")
@click.option("--output-url", default=None)
@click.option("--output-file", default=None)
@click.option("--no-setup", is_flag=True, default=False)
@click.option("--no-teardown", is_flag=True, default=False)
@click.option("--params", multiple=True, help="KEY=VALUE parameters")
def run(scenario_name, output, output_url, output_file, no_setup, no_teardown, params):
    """Execute a scenario end-to-end"""
    require_root()
    import shutil
    import signal
    import json
    from subprocess import TimeoutExpired

    # prepare output
    from netlab.output import make_output

    out = make_output(output, url=output_url, path=output_file)
    events.set_output(out)

    # resolve scenario
    try:
        sc = get_scenario(scenario_name)
    except KeyError:
        click.echo(f"Unknown scenario: {scenario_name}", err=True)
        sys.exit(1)

    # parse params KEY=VALUE
    parsed_params = {}
    for p in params:
        if "=" not in p:
            click.echo(f"Invalid param '{p}', expected KEY=VALUE", err=True)
            sys.exit(1)
        k, v = p.split("=", 1)
        parsed_params[k] = v

    # preflight checks
    missing = []
    for tool in getattr(sc, "required_tools", []):
        if shutil.which(tool) is None:
            missing.append(tool)

    if missing:
        click.echo(f"Missing required tools: {', '.join(missing)}", err=True)
        sys.exit(1)

    if state.read_active() is not None:
        click.echo("Another netlab run appears active; aborting.", err=True)
        sys.exit(1)

    if not no_setup and not topology.is_clean():
        click.echo("Lab is not clean; run 'netlab clean' or use --no-setup if intentional.", err=True)
        sys.exit(1)

    # abort flag and signal handlers
    aborted = {"flag": False}

    def _handle_signal(signum, frame):
        aborted["flag"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGHUP, _handle_signal)

    def aborted_check() -> bool:
        return aborted["flag"]

    # write active state
    payload = state.make_active_payload(os.getpid(), scenario_name, getattr(sc, "required_namespaces", []), topology.BRIDGE)
    try:
        state.write_active(payload)
    except Exception:
        click.echo("Failed to write active state file; check permissions.", err=True)
        sys.exit(1)

    # bring up topology
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

    __import__("time").sleep(1)
    events.emit_event("netlab.lifecycle.warming_up", "info", {"scenario": scenario_name})

    # run scenario
    success = False
    reason = ""
    start_ts = None
    try:
        start_ts = __import__("time").time()
        ctx = getattr(__import__("netlab.scenarios.base", fromlist=["ScenarioContext"]), "ScenarioContext")(
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
        try:
            if start_ts is not None:
                duration = __import__("time").time() - start_ts
        except Exception:
            duration = None

    # completion events
    if success:
        events.emit_event("netlab.scenario.completed", "info", {"scenario": scenario_name, "duration_seconds": duration})
    else:
        events.emit_event("netlab.scenario.aborted", "high", {"scenario": scenario_name, "reason": reason or "aborted"})

    # teardown
    events.emit_event("netlab.lifecycle.tearing_down", "info", {"scenario": scenario_name})
    dirty = False
    try:
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

    # remove active
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
def status():
    """Report lab and scenario state"""
    require_root()
    # call lab/status.sh if present
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
    # no root required
    git_hash = "unknown"
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        if res.returncode == 0:
            git_hash = res.stdout.strip()
    except Exception:
        pass
    click.echo(f"netlab {__version__} ({git_hash})")


if __name__ == "__main__":
    main()

