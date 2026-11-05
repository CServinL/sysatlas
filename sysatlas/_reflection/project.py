"""Project metadata that lives next to the source: console scripts from pyproject.toml."""
from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10: no stdlib TOML reader
    tomllib = None

_SCRIPT_TABLES = ("scripts", "gui-scripts")
_MAX_PARENTS = 2


def console_scripts(root: Path) -> dict[str, list[str]]:
    """Map dotted module name -> script names declared in the nearest pyproject.toml.

    Looks in `root` and up to two parents. Returns {} when there is no readable
    pyproject.toml, and always on Python 3.10, which has no stdlib TOML reader.
    A script `tool = "pkg.cli:main"` maps `pkg.cli` -> ['tool'].
    """
    if tomllib is None:
        return {}
    for directory in (root, *list(root.parents)[:_MAX_PARENTS]):
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return _read_scripts(candidate)
    return {}


def _read_scripts(path: Path) -> dict[str, list[str]]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):  # unreadable, not UTF-8, not TOML (TOMLDecodeError is a ValueError)
        return {}
    project = data.get("project")
    if not isinstance(project, dict):
        return {}
    out: dict[str, list[str]] = {}
    for table in _SCRIPT_TABLES:
        scripts = project.get(table)
        if not isinstance(scripts, dict):
            continue
        for script, target in sorted(scripts.items()):
            if not isinstance(target, str):
                continue
            module = target.split(":")[0].split("[")[0].strip()
            if module:
                out.setdefault(module, []).append(script)
    return out
