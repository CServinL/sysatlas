"""AST-only scanner. Reads a Python source tree without importing it."""
from __future__ import annotations

import ast
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from sysatlas._reflection.resolve import resolve_import


class Module(BaseModel):
    """One scanned .py file."""
    model_config = ConfigDict(extra="forbid")

    name: str
    """Dotted module name relative to scan root (e.g. 'sysatlas._ontology.architecture')."""
    path: str
    """Absolute path on disk."""
    package: str
    """Top-level package or first-segment (e.g. 'sysatlas', '_ontology')."""
    imports: list[str] = Field(default_factory=list)
    """In-tree dotted module names this module imports. Stdlib / third-party filtered out."""


class ProjectGraph(BaseModel):
    """Result of scanning a source tree."""
    model_config = ConfigDict(extra="forbid")

    root: str
    modules: list[Module]

    def by_name(self) -> dict[str, Module]:
        return {m.name: m for m in self.modules}


def scan(root: str | Path) -> ProjectGraph:
    """Walk root, parse every .py with ast, return module + in-tree imports."""
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"reflection root not found: {root_path}")
    if root_path.is_file():
        scan_root = root_path.parent
        files = [root_path]
    else:
        scan_root = root_path
        files = sorted(p for p in scan_root.rglob("*.py") if "__pycache__" not in p.parts)

    in_tree_names = {_module_name(p, scan_root) for p in files}
    modules: list[Module] = []
    for p in files:
        modname = _module_name(p, scan_root)
        imports = _extract_imports(p, modname)
        resolved = [r for r in (resolve_import(i, modname, in_tree_names) for i in imports) if r]
        modules.append(
            Module(
                name=modname,
                path=str(p),
                package=modname.split(".")[0],
                imports=sorted(set(resolved)),
            )
        )
    return ProjectGraph(root=str(scan_root), modules=modules)


def _module_name(path: Path, scan_root: Path) -> str:
    rel = path.relative_to(scan_root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([scan_root.name, *parts]) if parts else scan_root.name


def _extract_imports(path: Path, modname: str) -> list[str]:
    """Return raw import strings (unresolved). 'from x.y import z' yields 'x.y.z' and 'x.y'."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _absolute_from(node, modname)
            if base is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    out.append(base)
                else:
                    out.append(f"{base}.{alias.name}" if base else alias.name)
                    out.append(base)
    return out


def _absolute_from(node: ast.ImportFrom, modname: str) -> str | None:
    """Resolve a 'from .x import y' relative import to an absolute dotted prefix."""
    if node.level == 0:
        return node.module or ""
    parts = modname.split(".")
    if node.level > len(parts):
        return None
    base = parts[: len(parts) - node.level]
    if node.module:
        base = base + node.module.split(".")
    return ".".join(base) if base else None
