from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, Any
import time
import subprocess


@dataclass
class ScenarioContext:
	params: Dict[str, Any]
	emit_event: Callable[[str, str, dict], None]
	aborted_check: Callable[[], bool]


def wait_for_duration(duration_seconds: float | None, ctx: ScenarioContext, procs: list[subprocess.Popen] | None = None, timeout_terminate: int = 5) -> None:
	"""
	Wait for a duration while monitoring for abort or process termination.
	
	Args:
		duration_seconds: How long to wait (seconds). If None, waits until process exits or abort.
		ctx: ScenarioContext with aborted_check callback.
		procs: Optional list of processes to monitor. If any terminates, break early.
		timeout_terminate: Seconds to wait before killing a terminated process.
	"""
	start = time.time()
	try:
		while True:
			if ctx.aborted_check():
				break
			if procs and any(p.poll() is not None for p in procs):
				break
			if duration_seconds is not None and (time.time() - start >= duration_seconds):
				break
			time.sleep(0.5)
	finally:
		if procs:
			for p in procs:
				if p.poll() is None:
					p.terminate()
					try:
						p.wait(timeout=timeout_terminate)
					except subprocess.TimeoutExpired:
						p.kill()


def start_arp_spoof(attack_script_path: str, target_ip: str, gateway_ip: str) -> subprocess.Popen:
	"""Start an ARP spoofing process."""
	cmd = [
		"ip",
		"netns",
		"exec",
		"ns-atk",
		"python3",
		attack_script_path,
		"--iface",
		"veth-atk",
		"--target-ip",
		target_ip,
		"--gateway-ip",
		gateway_ip,
		"--interval",
		"1",
	]
	return subprocess.Popen(cmd)


@dataclass
class Scenario(ABC):
	name: str
	description: str
	required_tools: list[str] = field(default_factory=list)
	required_namespaces: list[str] = field(default_factory=lambda: ["ns-atk", "ns-def", "ns-srv", "ns-dns"])
	expected_duration_seconds: int = 30
	parameters: dict = field(default_factory=dict)
	expected_steps: list[str] = field(default_factory=list)

	def _merge_params(self, ctx: ScenarioContext) -> dict:
		"""Merge default parameters with context-provided overrides, coercing types."""
		params = {k: v["default"] for k, v in self.parameters.items()}
		params.update(ctx.params or {})
		for k, spec in self.parameters.items():
			expected_type = spec.get("type")
			if expected_type is not None and k in params:
				try:
					params[k] = expected_type(params[k])
				except (ValueError, TypeError) as exc:
					raise ValueError(
						f"Parameter '{k}': cannot convert {params[k]!r} to {expected_type.__name__}: {exc}"
					)
		return params

	@abstractmethod
	def run(self, ctx: ScenarioContext) -> None:
		"""Execute the scenario. Must honor ctx.aborted_check() in loops."""
		raise NotImplementedError()

