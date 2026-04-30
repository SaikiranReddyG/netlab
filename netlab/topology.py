import subprocess
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = REPO_ROOT / "lab" / "setup.sh"
TEARDOWN_SCRIPT = REPO_ROOT / "lab" / "teardown.sh"
STATUS_SCRIPT = REPO_ROOT / "lab" / "status.sh"

EXPECTED_NAMESPACES = ["ns-atk", "ns-def", "ns-srv", "ns-dns"]
BRIDGE = "br-lab"


def is_clean() -> bool:
	result = subprocess.run(["ip", "netns", "list"], capture_output=True, text=True)
	namespaces = {line.split()[0] for line in result.stdout.splitlines() if line.strip()}
	if any(ns in namespaces for ns in EXPECTED_NAMESPACES):
		return False
	bridge_check = subprocess.run(["ip", "link", "show", BRIDGE], capture_output=True, text=True)
	if bridge_check.returncode == 0:
		return False
	return True


def is_fully_up() -> bool:
	result = subprocess.run(["ip", "netns", "list"], capture_output=True, text=True)
	namespaces = {line.split()[0] for line in result.stdout.splitlines() if line.strip()}
	if not all(ns in namespaces for ns in EXPECTED_NAMESPACES):
		return False
	bridge_check = subprocess.run(["ip", "link", "show", BRIDGE], capture_output=True, text=True)
	return bridge_check.returncode == 0


def setup() -> None:
	subprocess.run(["bash", str(SETUP_SCRIPT)], check=True)


def teardown(timeout: int = 30) -> None:
	try:
		subprocess.run(["bash", str(TEARDOWN_SCRIPT)], check=False, timeout=timeout)
	except subprocess.TimeoutExpired:
		# caller will mark dirty
		raise


def residual_state() -> List[str]:
	leftovers: List[str] = []
	result = subprocess.run(["ip", "netns", "list"], capture_output=True, text=True)
	namespaces = {line.split()[0] for line in result.stdout.splitlines() if line.strip()}
	for ns in EXPECTED_NAMESPACES:
		if ns in namespaces:
			leftovers.append(f"namespace:{ns}")
	bridge_check = subprocess.run(["ip", "link", "show", BRIDGE], capture_output=True, text=True)
	if bridge_check.returncode == 0:
		leftovers.append(f"bridge:{BRIDGE}")
	return leftovers

