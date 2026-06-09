import json
import socket
import sys
from io import StringIO

import pytest

import netlab.events as events_module
from netlab import __version__
from netlab.output import StdoutOutput, FileOutput


@pytest.fixture(autouse=True)
def reset_output():
    """Reset the global output handler before and after each test."""
    events_module.set_output(None)
    yield
    events_module.set_output(None)


def test_emit_event_structure(capsys):
    event_type = "netlab.scenario.started"
    payload = {"scenario": "arp_spoof"}
    events_module.emit_event(event_type, "info", payload)

    captured = capsys.readouterr()
    event = json.loads(captured.out.strip())

    assert event["schema_version"] == "1.0"
    assert event["source"] == "netlab"
    assert event["source_version"] == __version__
    assert event["host"] == socket.gethostname()
    assert event["event_type"] == event_type
    assert event["severity"] == "info"
    assert event["payload"] == payload
    assert "timestamp" in event


def test_emit_event_all_valid_severities(capsys):
    for sev in ("info", "low", "medium", "high", "critical"):
        events_module.emit_event("netlab.test", sev, {})

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 5
    severities = [json.loads(l)["severity"] for l in lines]
    assert severities == ["info", "low", "medium", "high", "critical"]


def test_emit_event_invalid_severity_raises():
    with pytest.raises(ValueError, match="invalid severity"):
        events_module.emit_event("netlab.test", "urgent", {})


def test_emit_event_uses_configured_output():
    collected = []

    class CapturingOutput:
        def emit(self, event):
            collected.append(event)
        def flush(self):
            pass

    events_module.set_output(CapturingOutput())
    events_module.emit_event("netlab.test", "info", {"key": "val"})

    assert len(collected) == 1
    assert collected[0]["event_type"] == "netlab.test"
    assert collected[0]["payload"] == {"key": "val"}


def test_emit_event_defaults_to_stdout_when_output_none(capsys):
    # _output is None by default after reset_output fixture
    events_module.emit_event("netlab.test", "low", {})
    out = capsys.readouterr().out
    assert "netlab.test" in out


def test_flush_with_no_output_does_not_raise():
    events_module.flush()  # should not raise


def test_flush_calls_output_flush():
    flushed = []

    class TrackingOutput:
        def emit(self, event): pass
        def flush(self): flushed.append(True)

    events_module.set_output(TrackingOutput())
    events_module.flush()

    assert flushed == [True]


def test_timestamp_format():
    collected = []

    class Cap:
        def emit(self, e): collected.append(e)
        def flush(self): pass

    events_module.set_output(Cap())
    events_module.emit_event("netlab.test", "info", {})

    ts = collected[0]["timestamp"]
    # Should be parseable ISO format with milliseconds
    from datetime import datetime
    dt = datetime.fromisoformat(ts)
    assert dt is not None
