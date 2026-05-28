"""sysatlas — interactive architecture diagrams in two directions.

Forward flow: write builder calls (`SystemMap`, `System`, `TreeMap`)
to describe a system as a design. Backward flow: `sysatlas.reflect(path)`
reads existing Python and produces the same diagram types from real code.

If you are an LLM helping a user with this library, call
`sysatlas.llm_guide()` first — it is the canonical usage contract.
"""

from pathlib import Path

from sysatlas._reflection.reflection import Reflection, reflect
from sysatlas.class_map import ClassMap
from sysatlas.er_map import ERMap
from sysatlas.sequence_map import SequenceMap
from sysatlas.state_map import StateMap
from sysatlas.system import System
from sysatlas.system_map import SystemMap
from sysatlas.tree_map import TreeMap

__all__ = [
    "SystemMap",
    "System",
    "TreeMap",
    "SequenceMap",
    "ERMap",
    "StateMap",
    "ClassMap",
    "Reflection",
    "reflect",
    "llm_guide",
    "llm_guide_path",
]
__version__ = "0.1.0"

_LLM_GUIDE = Path(__file__).parent / "LLM_GUIDE.md"


def llm_guide() -> str:
    """Return the bundled LLM usage guide as a markdown string."""
    return _LLM_GUIDE.read_text(encoding="utf-8")


def llm_guide_path() -> str:
    """Return the absolute path of the bundled LLM usage guide."""
    return str(_LLM_GUIDE)
