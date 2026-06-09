from typing import Dict, Type

from netlab.defenses.base import Defense


REGISTRY: Dict[str, Type[Defense]] = {}


def register(name: str, cls: Type[Defense]) -> None:
    REGISTRY[name] = cls


def list_defenses() -> list[str]:
    return sorted(REGISTRY.keys())


def get_defense(name: str) -> Defense:
    cls = REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"Unknown defense: {name}")
    return cls()


# Import defense modules so they register themselves
from . import arp_defense  # noqa: F401
from . import firewall     # noqa: F401
from . import hardening    # noqa: F401
from . import ids          # noqa: F401
