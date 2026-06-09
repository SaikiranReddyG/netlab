import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DEFAULT_RUN_DIRS = [Path("/run/netlab"), Path("/var/run/netlab")]


def _choose_run_dir() -> Path:
	for p in DEFAULT_RUN_DIRS:
		try:
			p.mkdir(parents=True, exist_ok=True)
			return p
		except PermissionError:
			continue
	# fallback to cwd
	p = Path.cwd() / ".netlab-run"
	p.mkdir(parents=True, exist_ok=True)
	return p


def active_path() -> Path:
	return _choose_run_dir() / "active.json"


def write_active(data: dict) -> None:
	p = active_path()
	with open(p, "w", encoding="utf-8") as f:
		json.dump(data, f, indent=2)


def read_active() -> Optional[dict]:
	p = active_path()
	if not p.exists():
		return None
	try:
		with open(p, "r", encoding="utf-8") as f:
			return json.load(f)
	except Exception:
		return None


def remove_active() -> None:
	p = active_path()
	try:
		if p.exists():
			p.unlink()
	except Exception:
		pass


def tui_log_path() -> Path:
    return _choose_run_dir() / "events.jsonl"


def clear_tui_log() -> None:
    try:
        tui_log_path().write_text("")
    except Exception:
        pass


def make_active_payload(pid: int, scenario: str, namespaces: list, bridge: str) -> dict:
	return {
		"pid": pid,
		"scenario": scenario,
		"started_at": datetime.now(timezone.utc).astimezone().isoformat(),
		"namespaces": namespaces,
		"bridge": bridge,
	}

