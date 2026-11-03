"""AST-only scanner. Reads a Python source tree without importing it."""
from __future__ import annotations

import ast
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from sysatlas._reflection.external import external_roots
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
    in_tree_tops = {n.split(".")[0] for n in in_tree_names}
    scan_of = {p: _scan_source(p, _module_name(p, scan_root)) for p in files}
    models_of = _resolve_models({_module_name(p, scan_root): s for p, s in scan_of.items()})
    modules: list[Module] = []
    for p in files:
        modname = _module_name(p, scan_root)
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


_ROUTE_ATTRS = frozenset({"get", "post", "put", "delete", "patch", "head", "options", "route", "websocket"})
_CLI_ATTRS = frozenset({"command", "group"})
_TASK_NAMES = frozenset({"task", "shared_task"})
_WEB_ROOTS = frozenset({
    "fastapi", "flask", "starlette", "quart", "sanic", "bottle", "aiohttp", "tornado", "django", "falcon",
})
_CLI_ROOTS = frozenset({"click", "typer"})
_TASK_ROOTS = frozenset({"celery", "dramatiq", "rq", "huey", "arq", "taskiq"})
_MODEL_BASES = frozenset({"BaseModel", "BaseSettings", "SQLModel", "DeclarativeBase", "TypedDict", "NamedTuple"})
_ORM_BASES = frozenset({"Base", "Model"})
_ORM_ROOTS = frozenset({"sqlalchemy", "sqlmodel", "django", "peewee", "tortoise", "flask_sqlalchemy"})


def _scan_source(path: Path, modname: str) -> _SourceScan:
    """One pass over a source file: raw imports, docstring line, symbols, LOC, parse-ok,
    plus the architecture facts the atlas reports (entry points, models, env vars).

    'from x.y import z' yields raw imports 'x.y.z' and 'x.y'. On a parse failure
    (SyntaxError, embedded null bytes) everything but LOC comes back empty and
    `unparsed` is True, so the module stays visible.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    loc = sum(
        1 for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return _SourceScan(loc=loc, unparsed=True)

    nodes = list(_walk_runtime(tree))
    imports: list[str] = []
    aliases: dict[str, str] = {}
    os_env: dict[str, set[str]] = {"environ": set(), "getenv": set()}
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
                if alias.asname:
                    aliases[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom):
            base = _absolute_from(node, modname)
            if base is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    imports.append(base)
                    continue
                imports.append(f"{base}.{alias.name}" if base else alias.name)
                imports.append(base)
                aliases[alias.asname or alias.name] = f"{base}.{alias.name}" if base else alias.name
                if node.level == 0 and base == "os" and alias.name in os_env:
                    os_env[alias.name].add(alias.asname or alias.name)

    roots = {i.split(".")[0] for i in imports}
    entry_points: list[str] = []
    env_vars: list[str] = []
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                entry = _decorator_entry(dec, node.name, roots)
                if entry:
                    entry_points.append(entry)
        else:
            var = _env_var(node, os_env)
            if var:
                env_vars.append(var)
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
        env_vars=env_vars,
        undocumented=[
            n.name for n in (*public_classes, *public_functions)
            if not ast.get_docstring(n)
        ],
        class_bases={n.name: [_base_text(b) for b in n.bases] for n in top_classes},
        direct_models=[
            n.name for n in top_classes
            if {_name_of(b) for b in n.bases} & model_bases
            or any(_name_of(d) == "dataclass" for d in n.decorator_list)
        ],
        import_aliases=aliases,
    )


def _name_of(node: ast.expr) -> str | None:
    """Last identifier of a Name / Attribute / Call(func=...) expression."""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _base_text(node: ast.expr) -> str:
    """'Name' or 'head.Name' for a base-class expression; '' for anything else."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
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
                if any(_base_is_model(b, mod, s, models) for b in s.class_bases[cls]):
                    models.add((mod, cls))
                    changed = True
    return {
        mod: sorted(c for c in s.classes if (mod, c) in models)
        for mod, s in scans.items()
    }


def _base_is_model(base: str, mod: str, s: _SourceScan, models: set[tuple[str, str]]) -> bool:
    if not base:
        return False
    if "." in base:
        head, attr = base.split(".", 1)
        target = s.import_aliases.get(head)
        return target is not None and (target, attr) in models
    if (mod, base) in models:
        return True
    target = s.import_aliases.get(base)
    if target and "." in target:
        owner, _, name = target.rpartition(".")
        return (owner, name) in models
    return False


def _decorator_entry(dec: ast.expr, fn_name: str, roots: set[str]) -> str | None:
    """Classify a decorator as a web route / CLI command / background task.

    A decorator only counts when the module imports a framework of that kind,
    so `@pytest.mark.group` or a dict's `.get("/x")` are not entry points.
    """
    name = _name_of(dec)
    if name is None:
        return None
    if (
        isinstance(dec, ast.Call)
        and isinstance(dec.func, ast.Attribute)
        and name in _ROUTE_ATTRS
        and roots & _WEB_ROOTS
    ):
        path = dec.args[0] if dec.args else next(
            (k.value for k in dec.keywords if k.arg == "path"), None
        )
        if isinstance(path, ast.Constant) and isinstance(path.value, str) and path.value.startswith("/"):
            verb = "" if name == "route" else f"{name.upper()} "
            return f"route {verb}{path.value}"
        return None
    if name in _CLI_ATTRS and isinstance(dec, (ast.Call, ast.Attribute)) and roots & _CLI_ROOTS:
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


def _is_os_attr(node: ast.expr, attr: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == attr
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _literal_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _env_var(node: ast.AST, os_env: dict[str, set[str]]) -> str | None:
    """Literal key of a read: os.getenv(K), os.environ.get(K), os.environ[K] (not stores)."""

    def is_environ(n: ast.expr) -> bool:
        return _is_os_attr(n, "environ") or (isinstance(n, ast.Name) and n.id in os_env["environ"])

    if isinstance(node, ast.Call) and node.args:
        func = node.func
        is_getenv = _is_os_attr(func, "getenv") or (
            isinstance(func, ast.Name) and func.id in os_env["getenv"]
        )
        if is_getenv or (
            isinstance(func, ast.Attribute) and func.attr == "get" and is_environ(func.value)
        ):
            return _literal_str(node.args[0])
    if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) and is_environ(node.value):
        return _literal_str(node.slice)
    return None


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
