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
    doc: str = ""
    """First non-empty line of the module docstring, stripped, capped at 200 chars."""
    classes: list[str] = Field(default_factory=list)
    """Top-level public class names, sorted. Empty for languages without symbol extraction."""
    functions: list[str] = Field(default_factory=list)
    """Top-level public function names, sorted. Empty for languages without symbol extraction."""
    loc: int = 0
    """Physical lines that are not blank and not comment-only."""
    unparsed: bool = False
    """True when the source could not be parsed (SyntaxError / null bytes); imports and symbols are then empty."""


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
        raw_imports, doc, classes, functions, loc, unparsed = _scan_source(p, modname)
        resolved = [
            r for r in (resolve_import(i, modname, in_tree_names) for i in raw_imports) if r
        ]
        modules.append(
            Module(
                name=modname,
                path=str(p),
                package=modname.split(".")[0],
                imports=sorted(set(resolved)),
                doc=doc,
                classes=sorted(classes),
                functions=sorted(functions),
                loc=loc,
                unparsed=unparsed,
            )
        )
    return ProjectGraph(root=str(scan_root), modules=modules)


def _module_name(path: Path, scan_root: Path) -> str:
    rel = path.relative_to(scan_root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    # If scan_root is itself a package (has __init__.py), prefix with its name
    # so imports of "pkg.x" resolve. Otherwise scan_root is a container like
    # "src/" — use the package directory under it as the top-level instead.
    if (scan_root / "__init__.py").exists():
        return ".".join([scan_root.name, *parts]) if parts else scan_root.name
    return ".".join(parts) if parts else ""


def _scan_source(
    path: Path, modname: str
) -> tuple[list[str], str, list[str], list[str], int, bool]:
    """One pass over a source file: raw imports, docstring line, symbols, LOC, parse-ok.

    'from x.y import z' yields raw imports 'x.y.z' and 'x.y'. On a parse failure
    (SyntaxError, embedded null bytes) imports/doc/symbols come back empty and
    the last element is True, but LOC is still counted from the raw text so the
    module stays visible.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    loc = sum(
        1 for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return [], "", [], [], loc, True

    imports: list[str] = []
    for node in _walk_runtime(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _absolute_from(node, modname)
            if base is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    imports.append(base)
                else:
                    imports.append(f"{base}.{alias.name}" if base else alias.name)
                    imports.append(base)

    raw_doc = ast.get_docstring(tree, clean=True) or ""
    doc = next((ln.strip() for ln in raw_doc.splitlines() if ln.strip()), "")[:200]

    classes = [
        n.name for n in tree.body
        if isinstance(n, ast.ClassDef) and not n.name.startswith("_")
    ]
    functions = [
        n.name for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not n.name.startswith("_")
    ]
    return imports, doc, classes, functions, loc, False


def _walk_runtime(tree: ast.AST):
    """Like ast.walk, but skips the body of `if TYPE_CHECKING:` guards.

    Type-only imports are not runtime dependencies, so counting them would
    invent import cycles the code was deliberately written to avoid.
    """
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.If) and _is_type_checking(node.test):
            for sub in node.orelse:
                yield sub
                yield from _walk_runtime(sub)
            continue
        yield node
        yield from _walk_runtime(node)


def _is_type_checking(test: ast.expr) -> bool:
    return (
        (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
        or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
    )


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
    # Empty base means the import resolves to the package root (e.g.
    # `from . import x` inside pkg/__init__.py where modname == "pkg").
    # Treat that as the current package itself so the edge is captured.
    if not base:
        return parts[0] if parts else ""
    return ".".join(base)
