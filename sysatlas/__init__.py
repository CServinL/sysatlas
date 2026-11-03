"""sysatlas — interactive architecture diagrams in two directions.

Forward flow: write builder calls (`SystemMap`, `System`, `TreeMap`)
to describe a system as a design. Backward flow: `sysatlas.reflect(path)`
reads existing Python and produces the same diagram types from real code.

If you are an LLM helping a user with this library, call
`sysatlas.llm_guide()` first — it is the canonical usage contract.
"""

from pathlib import Path

from sysatlas._reflection.reflection import Reflection, reflect, reflect_rust
from sysatlas.bpmn_map import BPMNMap
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
    "BPMNMap",
    "Reflection",
    "reflect",
    "reflect_rust",
    "llm_guide",
    "llm_guide_path",
    "skill",
    "skill_path",
]
__version__ = "0.3.4"

_LLM_GUIDE = Path(__file__).parent / "LLM_GUIDE.md"
_SKILLS = Path(__file__).parent / "_skill"


def llm_guide() -> str:
    """Return the bundled LLM usage guide as a markdown string."""
    return _LLM_GUIDE.read_text(encoding="utf-8")


def llm_guide_path() -> str:
    """Return the absolute path of the bundled LLM usage guide."""
    return str(_LLM_GUIDE)


def _skill_file(name: str) -> Path:
    available = sorted(p.parent.name for p in _SKILLS.glob("*/SKILL.md"))
    if name not in available:
        raise ValueError(f"unknown skill {name!r}; available: {', '.join(available)}")
    return _SKILLS / name / "SKILL.md"


def skill(name: str = "sysatlas") -> str:
    """Return a bundled Claude Code Skill (SKILL.md) as a markdown string.

    Bundled skills: "sysatlas" (how to use the library) and "sysatlas-document"
    (fill the atlas's documentation gaps).
    """
    return _skill_file(name).read_text(encoding="utf-8")


def skill_path(name: str = "sysatlas") -> str:
    """Return the absolute path of a bundled Claude Code Skill file."""
    return str(_skill_file(name))
