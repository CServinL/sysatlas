"""AST-only scanner. Reads a Python source tree without importing it."""
from __future__ import annotations

import ast
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from sysatlas._reflection.external import external_roots
from sysatlas._reflection.resolve import resolve_import
from sysatlas._reflection.scopes import absolute_from, env_reads, scope_maps, walk_runtime


class ClassLink(BaseModel):
    """A class and the in-tree abstract class it directly extends."""
    model_config = ConfigDict(extra="forbid")

    cls: str
    base_module: str
    base: str


class Module(BaseModel):
    """One scanned .py file."""
    model_config = ConfigDict(extra="forbid")

    name: str
    """Dotted module name relative to scan root (e.g. 'sysatlas._ontology.architecture')."""
    language: str = "python"
    """Language of the source file; set by the parser that produced the module."""
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
    external: list[str] = Field(default_factory=list)
    """Top-level names of non-stdlib, out-of-tree imports (plus a few stdlib modules that mean an external system), sorted."""
    entry_points: list[str] = Field(default_factory=list)
    """How the system is entered from here: 'main', 'route GET /x', 'cli fn', 'task fn'. Sorted."""
    models: list[str] = Field(default_factory=list)
    """Public data-model classes (pydantic / ORM / dataclass / TypedDict), sorted."""
    env_vars: list[str] = Field(default_factory=list)
    """Environment variable names read with a literal key, sorted."""
    undocumented: list[str] = Field(default_factory=list)
    """Public top-level classes / functions that have no docstring, sorted."""
    implements: list[ClassLink] = Field(default_factory=list)
    """Public concrete classes that directly extend an abstract class defined in the scanned tree."""
    fluent_classes: list[str] = Field(default_factory=list)
    """Public classes with at least three public methods that only ever `return self`, sorted."""


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

    parsed = {p: read_and_parse(p) for p in files}
    prefix = _namespace_prefix(scan_root, [tree for _, tree in parsed.values() if tree is not None])
    names = {p: _module_name(p, scan_root, prefix) for p in files}
    in_tree_names = set(names.values())
    in_tree_tops = {n.split(".")[0] for n in in_tree_names}
    scan_of = {p: _scan_source(p, names[p], *parsed[p]) for p in files}
    canonical = {}
    for p in files:
        if names[p] not in canonical or _preference(p, scan_of[p].loc) > _preference(*canonical[names[p]]):
            canonical[names[p]] = (p, scan_of[p].loc)
    by_module = {name: scan_of[p] for name, (p, _) in canonical.items()}
    models_of = _resolve_models(by_module)
    links_of = _resolve_implementations(by_module)
    modules: list[Module] = []
    for p in files:
        modname = names[p]
        src = scan_of[p]
        resolved = [
            r for r in (resolve_import(i, modname, in_tree_names) for i in src.imports) if r
        ]
        modules.append(
            Module(
                name=modname,
                path=str(p),
                package=modname.split(".")[0],
                imports=sorted(set(resolved)),
                doc=src.doc,
                classes=sorted(src.classes),
                functions=sorted(src.functions),
                loc=src.loc,
                unparsed=src.unparsed,
                external=external_roots(src.imports, in_tree_tops),
                entry_points=sorted(set(src.entry_points)),
                models=sorted(set(src.classes) & set(models_of[modname])),
                env_vars=sorted(set(src.env_vars)),
                undocumented=sorted(src.undocumented),
                implements=links_of[modname],
                fluent_classes=sorted(src.fluent_classes),
            )
        )
    return ProjectGraph(root=str(scan_root), modules=modules)


def _preference(path: Path | str, loc: int) -> tuple[bool, int, str]:
    """Which of two files with the same module name is the module: a package's `__init__.py`
    (as Python imports it), else the larger file."""
    return Path(path).name == "__init__.py", loc, str(path)


def module_preference(module: "Module") -> tuple[bool, int, str]:
    """Sort key for choosing between two modules with the same name; the larger key is the module."""
    return _preference(module.path, module.loc)


def read_and_parse(path: Path) -> tuple[str, ast.Module | None]:
    """Source text and its AST; the AST is None when the file does not parse.

    The bytes are parsed, so a UTF-8 BOM or a `# coding:` declaration is honoured as
    the interpreter would. If that fails on the encoding alone, the lenient text is tried.
    Source too deeply nested for the parser (`RecursionError`, `MemoryError`) gives None.
    """
    data = path.read_bytes()
    text = data.decode("utf-8-sig", errors="replace")
    for source in (data, text):
        try:
            return text, ast.parse(source)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            continue
    return text, None


def _namespace_prefix(scan_root: Path, trees: list[ast.Module]) -> str:
    """Name to prefix module names with when scan_root is a package without __init__.py.

    A directory such as `prisma/` with no `__init__.py` is a namespace package:
    its code still imports itself as `prisma.x`. The evidence is an import statement
    that names a module which exists under scan_root (`from prisma.server import x`
    with `server/` or `server.py` present). A bare `import code` or a name that
    happens to match the directory is not evidence: it may be the standard library.
    """
    name = scan_root.name
    if (scan_root / "__init__.py").exists() or not name.isidentifier():
        return ""
    if (scan_root / name).is_dir():
        return ""  # a checkout `pkg/` that contains the package `pkg/pkg/`: scan_root is only a container

    def exists(parts: list[str]) -> bool:
        target = scan_root.joinpath(*parts)
        return bool(parts) and (target.is_dir() or target.with_suffix(".py").is_file())

    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(
                    a.name.split(".")[0] == name and exists(a.name.split(".")[1:]) for a in node.names
                ):
                    return name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                head, *rest = node.module.split(".")
                if head != name:
                    continue
                if rest and exists(rest):
                    return name
                if not rest and any(exists([a.name]) for a in node.names):
                    return name
    return ""


def _module_name(path: Path, scan_root: Path, prefix: str = "") -> str:
    rel = path.relative_to(scan_root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    # If scan_root is itself a package (has __init__.py, or is a namespace
    # package that imports itself by name), prefix with its name so imports of
    # "pkg.x" resolve. Otherwise scan_root is a container like "src/" — use
    # the package directory under it as the top-level instead.
    if (scan_root / "__init__.py").exists():
        return ".".join([scan_root.name, *parts]) if parts else scan_root.name
    if prefix:
        return ".".join([prefix, *parts])
    return ".".join(parts) if parts else ""


class _SourceScan(BaseModel):
    """Raw facts from one source file, before in-tree resolution."""
    model_config = ConfigDict(extra="forbid")

    imports: list[str] = Field(default_factory=list)
    doc: str = ""
    classes: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    loc: int = 0
    unparsed: bool = False
    entry_points: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    undocumented: list[str] = Field(default_factory=list)
    class_bases: dict[str, list[str]] = Field(default_factory=dict)
    """Every top-level class -> its base expressions ('Name' or 'alias.Name')."""
    direct_models: list[str] = Field(default_factory=list)
    """Top-level classes that are models by their own bases or decorators."""
    import_aliases: dict[str, str] = Field(default_factory=dict)
    """Local name -> absolute dotted target, for `import a.b as c` and `from a import b`."""
    abstract_classes: list[str] = Field(default_factory=list)
    fluent_classes: list[str] = Field(default_factory=list)


_ROUTE_ATTRS = frozenset({"get", "post", "put", "delete", "patch", "head", "options", "route", "websocket"})
_CLI_ATTRS = frozenset({"command", "group"})
_TASK_NAMES = frozenset({"task", "shared_task"})
_WEB_ROOTS = frozenset({
    "fastapi", "flask", "starlette", "quart", "sanic", "bottle", "aiohttp", "tornado", "django", "falcon",
    "litestar", "blacksheep",
})
_CLI_ROOTS = frozenset({"click", "typer"})
_TASK_ROOTS = frozenset({"celery", "dramatiq", "rq", "huey", "arq", "taskiq"})
_MODEL_BASES = frozenset({"BaseModel", "BaseSettings", "SQLModel", "DeclarativeBase", "TypedDict", "NamedTuple"})
_ORM_BASES = frozenset({"Base", "Model"})
_ORM_ROOTS = frozenset({"sqlalchemy", "sqlmodel", "django", "peewee", "tortoise", "flask_sqlalchemy"})
_ABSTRACT_BASES = frozenset({"ABC", "Protocol"})
_FLUENT_MIN_METHODS = 3
_NOT_CHAINED = frozenset({"property", "staticmethod", "classmethod", "cached_property", "setter", "getter", "deleter"})


def _scan_source(
    path: Path, modname: str, text: str, tree: ast.Module | None
) -> _SourceScan:
    """One pass over a source file: raw imports, docstring line, symbols, LOC, parse-ok,
    plus the architecture facts the atlas reports (entry points, models, env vars).

    'from x.y import z' yields raw imports 'x.y.z' and 'x.y'. On a parse failure
    (SyntaxError, embedded null bytes) everything but LOC comes back empty and
    `unparsed` is True, so the module stays visible.
    """
    loc = sum(
        1 for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if tree is None:
        return _SourceScan(loc=loc, unparsed=True)
    try:
        return _analyze(
            tree, modname, path.name == "__init__.py", loc,
            mentions_env="environ" in text or "getenv" in text,
            mentions_global="global" in text,
        )
    except RecursionError:  # source nested deeper than the interpreter can walk: keep the module visible
        return _SourceScan(loc=loc, unparsed=True)


def _analyze(
    tree: ast.Module, modname: str, is_package: bool, loc: int, mentions_env: bool, mentions_global: bool
) -> _SourceScan:
    module_aliases, enclosing = scope_maps(tree, modname, is_package, mentions_global)

    def scope(node: ast.AST) -> dict[str, str]:
        """Import bindings visible where `node` (a def or class) is defined."""
        return enclosing.get(id(node), module_aliases)

    nodes = list(walk_runtime(tree))
    imports: list[str] = []
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = absolute_from(node, modname, is_package)
            if base is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    imports.append(base)
                    continue
                imports.append(f"{base}.{alias.name}" if base else alias.name)
                if base != modname:
                    imports.append(base)

    roots = {i.split(".")[0] for i in imports}
    entry_points: list[str] = []
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                entry = _decorator_entry(dec, node.name, roots, scope(node))
                if entry:
                    entry_points.append(entry)
    if any(isinstance(n, ast.If) and _is_main_guard(n.test) for n in tree.body):
        entry_points.append("main")

    raw_doc = ast.get_docstring(tree, clean=True) or ""
    doc = next((ln.strip() for ln in raw_doc.splitlines() if ln.strip()), "")[:200]

    top_classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    public_classes = [n for n in top_classes if not n.name.startswith("_")]
    public_functions = [
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not n.name.startswith("_")
    ]
    model_bases = _MODEL_BASES | (_ORM_BASES if roots & _ORM_ROOTS else frozenset())
    return _SourceScan(
        imports=imports,
        doc=doc,
        classes=[n.name for n in public_classes],
        functions=[n.name for n in public_functions],
        loc=loc,
        entry_points=entry_points,
        env_vars=env_reads(tree) if mentions_env else [],
        undocumented=[
            n.name for n in (*public_classes, *public_functions)
            if not ast.get_docstring(n)
        ],
        class_bases={n.name: [_base_text(b) for b in n.bases] for n in top_classes},
        direct_models=[
            n.name for n in top_classes
            if {_name_of(b, scope(n)) for b in n.bases} & model_bases
            or any(_name_of(d, scope(n)) == "dataclass" for d in n.decorator_list)
        ],
        import_aliases=module_aliases,
        abstract_classes=[n.name for n in top_classes if _is_abstract(n, scope)],
        fluent_classes=[
            n.name for n in public_classes if _fluent_method_count(n, scope) >= _FLUENT_MIN_METHODS
        ],
    )


def _is_abstract(cls: ast.ClassDef, scope) -> bool:
    """ABC / Protocol base, ABCMeta metaclass, or any @abstractmethod."""
    aliases = scope(cls)
    if {_name_of(b, aliases) for b in cls.bases} & _ABSTRACT_BASES:
        return True
    if any(k.arg == "metaclass" and _name_of(k.value, aliases) == "ABCMeta" for k in cls.keywords):
        return True
    return any(
        isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_name_of(d, scope(m)) in ("abstractmethod", "abstractproperty") for d in m.decorator_list)
        for m in cls.body
    )


def _returns_of(fn: ast.AST) -> list[ast.Return]:
    """Return statements of `fn` itself, not of functions or classes nested in it."""
    found: list[ast.Return] = []
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(node, ast.Return):
            found.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return found


def _is_return_self(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _fluent_method_count(cls: ast.ClassDef, scope) -> int:
    """Public instance methods that always return `self`: the last statement is
    `return self` and no other `return` returns anything else."""
    count = 0
    for m in cls.body:
        if not isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) or m.name.startswith("_"):
            continue
        if any(_name_of(d, scope(m)) in _NOT_CHAINED for d in m.decorator_list):
            continue
        if m.body and _is_return_self(m.body[-1]) and all(_is_return_self(r) for r in _returns_of(m)):
            count += 1
    return count


def _name_of(node: ast.expr, aliases: dict[str, str] | None = None) -> str | None:
    """Last identifier of a Name / Attribute / Call(func=...) / Subscript(value=...) expression.

    A bare name imported under another name (`from pydantic import BaseModel as
    Schema`) is reported as the name it was imported as (`BaseModel`).
    """
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Name):
        if aliases and node.id in aliases:
            return aliases[node.id].rpartition(".")[2]
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _base_text(node: ast.expr) -> str:
    """Dotted text of a base-class expression (`Name`, `a.b.Name`; type arguments dropped); '' for anything else."""
    if isinstance(node, ast.Subscript):
        node = node.value
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _resolve_models(scans: dict[str, _SourceScan]) -> dict[str, list[str]]:
    """Public model classes per module, following inheritance across modules.

    A class is a model if it is one directly, or if a base resolves (in this
    module or through an import) to a model class in the scanned tree.
    """
    models = {(mod, cls) for mod, s in scans.items() for cls in s.direct_models}
    changed = True
    while changed:
        changed = False
        for mod in sorted(scans):
            s = scans[mod]
            for cls in sorted(s.class_bases):
                if (mod, cls) in models:
                    continue
                if any(_base_is_model(b, mod, s, models, scans) for b in s.class_bases[cls]):
                    models.add((mod, cls))
                    changed = True
    return {
        mod: sorted(c for c in s.classes if (mod, c) in models)
        for mod, s in scans.items()
    }


_MAX_REEXPORT_HOPS = 3


def _base_targets(
    base: str, mod: str, s: _SourceScan, scans: dict[str, _SourceScan]
) -> list[tuple[str, str]]:
    """(module, class) places a base-class expression can refer to, including
    the origin of a class re-exported through a package `__init__`."""
    if not base:
        return []
    if "." in base:
        parts = base.split(".")
        target = s.import_aliases.get(parts[0])
        first = [(".".join([target, *parts[1:-1]]), parts[-1])] if target else []
        first.append((".".join(parts[:-1]), parts[-1]))  # `import a.b` then `a.b.Name`
    else:
        first = [(mod, base)]
        target = s.import_aliases.get(base)
        if target and "." in target:
            owner, _, name = target.rpartition(".")
            first.append((owner, name))
    out: list[tuple[str, str]] = []
    for place in first:
        for _ in range(_MAX_REEXPORT_HOPS + 1):
            if place not in out:
                out.append(place)
            owner, name = place
            nxt = scans[owner].import_aliases.get(name) if owner in scans else None
            if not nxt or "." not in nxt:
                break
            place = (nxt.rpartition(".")[0], nxt.rpartition(".")[2])
    return out


def _base_is_model(
    base: str, mod: str, s: _SourceScan, models: set[tuple[str, str]], scans: dict[str, _SourceScan]
) -> bool:
    return any(t in models for t in _base_targets(base, mod, s, scans))


def _resolve_implementations(scans: dict[str, _SourceScan]) -> dict[str, list[ClassLink]]:
    """Public concrete classes that directly extend an abstract class in the tree."""
    abstract = {(mod, cls) for mod, s in scans.items() for cls in s.abstract_classes}
    out: dict[str, list[ClassLink]] = {}
    for mod in sorted(scans):
        s = scans[mod]
        links: list[ClassLink] = []
        for cls in sorted(s.class_bases):
            if cls.startswith("_") or cls in s.abstract_classes:
                continue
            seen: set[tuple[str, str]] = set()
            for base in s.class_bases[cls]:
                hit = next((t for t in _base_targets(base, mod, s, scans) if t in abstract), None)
                if hit and hit not in seen:
                    seen.add(hit)
                    links.append(ClassLink(cls=cls, base_module=hit[0], base=hit[1]))
        out[mod] = links
    return out


def _decorator_entry(
    dec: ast.expr, fn_name: str, roots: set[str], aliases: dict[str, str]
) -> str | None:
    """Classify a decorator as a web route / CLI command / background task.

    A decorator only counts when the module imports a framework of that kind,
    so `@pytest.mark.group` or a dict's `.get("/x")` are not entry points. The
    decorator may be a method (`@app.get`), or a function imported by name
    (`@get`, `@command`), called or not.
    """
    name = _name_of(dec, aliases)
    if name is None:
        return None
    if isinstance(dec, ast.Call) and name in _ROUTE_ATTRS and roots & _WEB_ROOTS:
        path = dec.args[0] if dec.args else next(
            (k.value for k in dec.keywords if k.arg in ("path", "rule")), None
        )
        if isinstance(path, ast.Constant) and isinstance(path.value, str) and path.value.startswith("/"):
            verb = "" if name == "route" else f"{name.upper()} "
            return f"route {verb}{path.value}"
        return None
    if name in _CLI_ATTRS and roots & _CLI_ROOTS:
        return f"cli {fn_name}"
    if name in _TASK_NAMES and roots & _TASK_ROOTS:
        return f"task {fn_name}"
    return None


def _is_main_guard(test: ast.expr) -> bool:
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
        return False
    pair = [test.left, test.comparators[0]]
    has_name = any(isinstance(n, ast.Name) and n.id == "__name__" for n in pair)
    has_main = any(isinstance(n, ast.Constant) and n.value == "__main__" for n in pair)
    return has_name and has_main
