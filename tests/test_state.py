import json
import os
from pathlib import Path

import pytest

import netlab.state as state_module


@pytest.fixture(autouse=True)
def isolated_run_dir(tmp_path, monkeypatch):
    """Route all state file I/O to a temp directory."""
    run_dir = tmp_path / "netlab-run"
    run_dir.mkdir()
    monkeypatch.setattr(state_module, "_choose_run_dir", lambda: run_dir)
    yield run_dir


# --- write_active / read_active roundtrip ---

def test_write_and_read_active(isolated_run_dir):
    payload = {"pid": 1234, "scenario": "arp_spoof", "started_at": "2026-01-01T00:00:00+00:00", "namespaces": [], "bridge": "br-lab"}
    state_module.write_active(payload)
    result = state_module.read_active()
    assert result == payload


def test_read_active_returns_none_when_missing():
    result = state_module.read_active()
    assert result is None


def test_read_active_returns_none_on_corrupt_json(isolated_run_dir):
    p = isolated_run_dir / "active.json"
    p.write_text("not valid json {{{")
    result = state_module.read_active()
    assert result is None


def test_read_active_returns_none_on_empty_file(isolated_run_dir):
    p = isolated_run_dir / "active.json"
    p.write_text("")
    result = state_module.read_active()
    assert result is None


# --- remove_active ---

def test_remove_active_deletes_file(isolated_run_dir):
    payload = {"pid": 1, "scenario": "test"}
    state_module.write_active(payload)
    assert (isolated_run_dir / "active.json").exists()
    state_module.remove_active()
    assert not (isolated_run_dir / "active.json").exists()


def test_remove_active_does_not_raise_when_missing():
    state_module.remove_active()  # no file — should not raise


# --- make_active_payload ---

def test_make_active_payload_fields():
    payload = state_module.make_active_payload(
        pid=42,
        scenario="mitm",
        namespaces=["ns-atk", "ns-srv"],
        bridge="br-lab",
    )
    assert payload["pid"] == 42
    assert payload["scenario"] == "mitm"
    assert payload["namespaces"] == ["ns-atk", "ns-srv"]
    assert payload["bridge"] == "br-lab"
    assert "started_at" in payload


def test_make_active_payload_started_at_is_iso():
    from datetime import datetime
    payload = state_module.make_active_payload(1, "test", [], "br-lab")
    dt = datetime.fromisoformat(payload["started_at"])
    assert dt is not None


# --- write_active produces valid JSON file ---

def test_write_active_creates_valid_json_file(isolated_run_dir):
    payload = state_module.make_active_payload(99, "dns_poison", ["ns-atk"], "br-lab")
    state_module.write_active(payload)
    content = (isolated_run_dir / "active.json").read_text()
    parsed = json.loads(content)
    assert parsed["pid"] == 99
    assert parsed["scenario"] == "dns_poison"
