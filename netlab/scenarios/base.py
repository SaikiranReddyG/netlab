from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, Any


@dataclass
class ScenarioContext:
	params: Dict[str, Any]
	emit_event: Callable[[str, str, dict], None]
	aborted_check: Callable[[], bool]


@dataclass
class Scenario(ABC):
	name: str
	description: str
	required_tools: list[str] = field(default_factory=list)
	required_namespaces: list[str] = field(default_factory=lambda: ["ns-atk", "ns-def", "ns-srv", "ns-dns"])
	expected_duration_seconds: int = 30
	parameters: dict = field(default_factory=dict)

	@abstractmethod
	def run(self, ctx: ScenarioContext) -> None:
		"""Execute the scenario. Must honor ctx.aborted_check() in loops."""
		raise NotImplementedError()

