import json
import socket
from datetime import datetime, timezone
from typing import Optional

from netlab import __version__

_output = None


def set_output(output) -> None:
	global _output
	_output = output


def _now_iso() -> str:
	return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def emit_event(event_type: str, severity: str, payload: dict) -> None:
	if severity not in ("info", "low", "medium", "high", "critical"):
		raise ValueError(f"invalid severity: {severity}")

	event = {
		"schema_version": "1.0",
		"timestamp": _now_iso(),
		"source": "netlab",
		"source_version": __version__,
		"host": socket.gethostname(),
		"event_type": event_type,
		"severity": severity,
		"payload": payload or {},
	}

	if _output is None:
		# default to stdout
		print(json.dumps(event), flush=True)
		return

	_output.emit(event)


def flush() -> None:
	if _output is not None:
		try:
			_output.flush()
		except Exception:
			pass

