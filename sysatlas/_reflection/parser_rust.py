"""tree-sitter Rust scanner. Reads a Rust source tree without compiling it."""
from __future__ import annotations

from pathlib import Path

from sysatlas._reflection.parser import Module, ProjectGraph
from sysatlas._reflection.resolve import resolve_import

_KEYWORDS = {"crate", "self", "super"}


def scan_rust(root: str | Path) -> ProjectGraph:
    """Walk root, parse every .rs with tree-sitter, return module + in-crate use deps."""
    try:
        import tree_sitter_rust as _tsrust
        from tree_sitter import Language, Parser
    except ImportError as exc:
        raise ImportError(
            "Rust reflection requires optional extras: "
            "pip install 'sysatlas[reflect-rust]'"
        ) from exc

    parser = Parser(Language(_tsrust.language()))

    root_path = Path(root).resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"reflection root not found: {root_path}")

    if root_path.is_file():
        src_root = root_path.parent
        files = [root_path]
    else:
        src_root = root_path / "src" if (root_path / "src").is_dir() else root_path
        files = sorted(p for p in src_root.rglob("*.rs"))

    in_tree_names = {_module_name(p, src_root) for p in files}
    modules: list[Module] = []
    for p in files:
        modname = _module_name(p, src_root)
        source = p.read_bytes()
        tree = parser.parse(source)
        raw = _use_paths(tree.root_node)
        resolved = [
            r
            for raw_path in raw
            for r in [_resolve(raw_path, modname, in_tree_names)]
            if r
        ]
        modules.append(
            Module(
                name=modname,
                path=str(p),
                package="crate",
                imports=sorted(set(resolved)),
            )
        )
    return ProjectGraph(root=str(src_root), modules=modules)


def _module_name(path: Path, src_root: Path) -> str:
    """Convert a .rs path to a dotted crate-relative name.

    src/main.rs    → crate
    src/lib.rs     → crate
    src/foo.rs     → crate.foo
    src/foo/mod.rs → crate.foo
    src/foo/bar.rs → crate.foo.bar
    """
    parts = list(path.relative_to(src_root).with_suffix("").parts)
    if not parts or parts in (["main"], ["lib"]):
        return "crate"
    if parts[-1] == "mod":
        parts = parts[:-1]
    if not parts:
        return "crate"
    return "crate." + ".".join(parts)


def _use_paths(root_node) -> list[str]:
    """Return all raw use paths extracted from a parsed source file."""
    paths: list[str] = []
    for node in _walk(root_node):
        if node.type == "use_declaration":
            for child in node.children:
                if child.type not in ("use", ";"):
                    paths.extend(_collect(child))
    return paths


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _collect(node) -> list[str]:
    """Recursively collect all complete :: -separated paths from a use tree node."""
    t = node.type
    if t in _KEYWORDS or t == "identifier":
        return [node.text.decode()]
    if t == "scoped_identifier":
        path_n = node.child_by_field_name("path")
        name_n = node.child_by_field_name("name")
        prefixes = _collect(path_n) if path_n else [""]
        names = _collect(name_n) if name_n else []
        return [f"{p}::{n}" for p in prefixes for n in names] if names else prefixes
    if t == "scoped_use_list":
        path_n = node.child_by_field_name("path")
        list_n = node.child_by_field_name("list")
        prefixes = _collect(path_n) if path_n else [""]
        suffixes = _collect(list_n) if list_n else []
        return [f"{p}::{s}" for p in prefixes for s in suffixes] if suffixes else prefixes
    if t == "use_list":
        out: list[str] = []
        for child in node.children:
            if child.type not in ("{", "}", ","):
                out.extend(_collect(child))
        return out
    if t == "use_wildcard":
        # children: [path_node, "::", "*"] — return the path prefix
        for child in node.children:
            if child.type not in ("::", "*"):
                return _collect(child)
        return []
    if t == "use_as_clause":
        # `use foo::Bar as Baz` — take the original path, ignore the alias
        return _collect(node.children[0])
    return []


def _resolve(raw_path: str, from_module: str, in_tree: set[str]) -> str | None:
    """Convert a raw :: path to an in-tree dotted module name, or None if external."""
    if raw_path.startswith("crate::"):
        dotted = "crate." + raw_path[len("crate::"):].replace("::", ".")
    elif raw_path == "crate":
        dotted = "crate"
    elif raw_path.startswith("self::"):
        dotted = from_module + "." + raw_path[len("self::"):].replace("::", ".")
    elif raw_path == "self":
        return None
    elif raw_path.startswith("super::"):
        parts = from_module.split(".")
        if len(parts) <= 1:
            return None
        dotted = ".".join(parts[:-1]) + "." + raw_path[len("super::"):].replace("::", ".")
    else:
        return None
    return resolve_import(dotted, from_module, in_tree)
