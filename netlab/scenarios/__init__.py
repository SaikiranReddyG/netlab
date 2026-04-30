from typing import Dict, Type

from netlab.scenarios.base import Scenario


REGISTRY: Dict[str, Type[Scenario]] = {}


def register(name: str, cls: Type[Scenario]) -> None:
	REGISTRY[name] = cls


def list_scenarios() -> list[str]:
	return sorted(REGISTRY.keys())


def get_scenario(name: str) -> Scenario:
	cls = REGISTRY.get(name)
	if cls is None:
		raise KeyError(f"Unknown scenario: {name}")
	return cls()


# Import scenario modules so they register themselves
from . import arp_spoof  # noqa: F401
from . import mitm  # noqa: F401
from . import dns_poison  # noqa: F401
from . import syn_flood  # noqa: F401

