from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, Any


@dataclass
class DefenseContext:
    params: Dict[str, Any]
    emit_event: Callable[[str, str, dict], None]
    aborted_check: Callable[[], bool]


@dataclass
class Defense(ABC):
    name: str
    description: str
    mitigates: list[str]
    required_tools: list[str] = field(default_factory=list)
    required_namespaces: list[str] = field(default_factory=lambda: ["ns-atk", "ns-def", "ns-srv", "ns-dns"])
    parameters: dict = field(default_factory=dict)
    concurrent_capable: bool = False
    expected_alerts_for: dict = field(default_factory=dict)
    alerts: list = field(default_factory=list, init=False)

    def _merge_params(self, ctx: DefenseContext) -> dict:
        params = {k: v["default"] for k, v in self.parameters.items()}
        params.update(ctx.params or {})
        for k, spec in self.parameters.items():
            expected_type = spec.get("type")
            if expected_type is not None and k in params:
                try:
                    params[k] = expected_type(params[k])
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"Defense parameter '{k}': cannot convert {params[k]!r} to {expected_type.__name__}: {exc}"
                    )
        return params

    @abstractmethod
    def apply(self, ctx: DefenseContext) -> None:
        raise NotImplementedError()

    @abstractmethod
    def remove(self, ctx: DefenseContext) -> None:
        raise NotImplementedError()
