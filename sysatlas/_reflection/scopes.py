"""Lexical scopes of a Python module: which import binding a name refers to, and environment reads.

A name bound by an import inside a function does not change what the same name means
elsewhere, and a parameter or local with the same name hides an import. Everything here
resolves names against the scope they are written in. Walkers are iterative, so deeply
nested source cannot overflow the stack.
"""
from __future__ import annotations

import ast
from typing import Iterable, Iterator, NamedTuple

_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)
_ROLES = {"os": "os", "os.environ": "environ", "os.getenv": "getenv"}


def is_type_checking(test: ast.expr) -> bool:
    """True for the test of an `if TYPE_CHECKING:` guard (bare or as `typing.TYPE_CHECKING`)."""
    return (
        (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
        or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
    )


def absolute_from(node: ast.ImportFrom, modname: str | None, is_package: bool = False) -> str | None:
    """Resolve a 'from .x import y' relative import to an absolute dotted prefix.

    In a package's `__init__.py` the module name is the package itself, so one
    leading dot means that package; in a regular module it means the parent.
    With no module name (`None`) relative imports cannot be resolved and give None.
    """
    if node.level == 0:
        return node.module or ""
    if modname is None:
        return None
    parts = modname.split(".")
    up = node.level - 1 if is_package else node.level
    if up > len(parts):
        return None
    base = parts[: len(parts) - up]
    if node.module:
        base = base + node.module.split(".")
    # Empty base: a top-level module doing `from . import x`. Treat it as the
    # module's own top-level name so the edge is captured.
    if not base:
        return parts[0] if parts else ""
    return ".".join(base)


def walk_runtime(tree: ast.AST) -> Iterator[ast.AST]:
    """Like ast.walk (pre-order), but skips the body of `if TYPE_CHECKING:` guards.

    Type-only imports are not runtime dependencies, so counting them would
    invent import cycles the code was deliberately written to avoid.
    """
    stack = list(reversed(list(ast.iter_child_nodes(tree))))
    while stack:
        node = stack.pop()
        if isinstance(node, ast.If) and is_type_checking(node.test):
            stack.extend(reversed(node.orelse))
            continue
        yield node
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def walk_scope(stmts: list[ast.stmt]) -> Iterator[ast.AST]:
    """Statements of one lexical scope, including those inside if / try / with / for / while.

    Yields function and class definitions but does not descend into their
    bodies, which are scopes of their own. Skips `if TYPE_CHECKING:` bodies.
    """
    stack = list(reversed(stmts))
    while stack:
        node = stack.pop()
        if isinstance(node, _SCOPE_NODES):
            yield node
            continue
        if isinstance(node, ast.If) and is_type_checking(node.test):
            stack.extend(reversed(node.orelse))
            continue
        yield node
        children = [
            c for c in ast.iter_child_nodes(node)
            if isinstance(c, (ast.stmt, ast.ExceptHandler, ast.match_case))
        ]
        stack.extend(reversed(children))


def import_bindings(stmts: list[ast.stmt], modname: str | None, is_package: bool) -> dict[str, str]:
    """Local name -> dotted target for the imports in one lexical scope.

    `import a.b` binds `a` to `a`; `import a.b as c` binds `c` to `a.b`;
    `from p import n as m` binds `m` to `p.n`.
    """
    out: dict[str, str] = {}
    for node in walk_scope(stmts):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    out[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    out[top] = top
        elif isinstance(node, ast.ImportFrom):
            base = absolute_from(node, modname, is_package)
            if base is None:
                continue
            for alias in node.names:
                if alias.name != "*":
                    out[alias.asname or alias.name] = f"{base}.{alias.name}" if base else alias.name
    return out


def scope_maps(
    tree: ast.Module, modname: str, is_package: bool
) -> tuple[dict[str, str], dict[int, dict[str, str]]]:
    """Module-level import bindings, and for every def / class the bindings visible where it is defined.

    A class body's own imports are visible to the class body (so to its methods'
    decorators), but not inside the methods.
    """
    module_map = import_bindings(tree.body, modname, is_package)
    enclosing: dict[int, dict[str, str]] = {}
    # (statements, bindings visible to definitions made here, bindings the bodies of those definitions extend)
    stack: list[tuple[list[ast.stmt], dict[str, str], dict[str, str]]] = [
        (tree.body, module_map, module_map)
    ]
    while stack:
        stmts, here, for_bodies = stack.pop()
        for node in walk_scope(stmts):
            if not isinstance(node, _SCOPE_NODES):
                continue
            enclosing[id(node)] = here
            own = import_bindings(node.body, modname, is_package)
            if isinstance(node, ast.ClassDef):
                stack.append((node.body, {**for_bodies, **own}, for_bodies))
            else:
                inner = {**for_bodies, **own}
                stack.append((node.body, inner, inner))
    return module_map, enclosing


# --- environment reads -------------------------------------------------------------------


class _Scope(NamedTuple):
    """Names bound in one scope, mapped to their environment role ("os", "environ", "getenv"),
    or None when bound to something else (a parameter, a local, an unrelated import)."""

    names: dict[str, str | None]
    is_class: bool = False


def _walrus_targets(node: ast.AST) -> set[str]:
    """Names bound by `:=` inside a comprehension, which Python binds in the enclosing function."""
    out: set[str] = set()
    stack = list(ast.iter_child_nodes(node))
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.Lambda, *_SCOPE_NODES)):
            continue
        if isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        stack.extend(ast.iter_child_nodes(n))
    return out


def _stored_names(roots: Iterable[ast.AST]) -> set[str]:
    """Names assigned, defined, or captured in one scope, not counting nested scopes."""
    out: set[str] = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        if isinstance(node, _SCOPE_NODES):
            out.add(node.name)
            continue
        if isinstance(node, ast.Lambda):
            continue
        if isinstance(node, _COMPREHENSIONS):
            out |= _walrus_targets(node)
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            out.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            out.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            out.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            out.add(node.rest)
        stack.extend(ast.iter_child_nodes(node))
    return out


def _params(args: ast.arguments) -> list[ast.arg]:
    every = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    every.extend(a for a in (args.vararg, args.kwarg) if a is not None)
    return every


def _scope_of(stmts: list[ast.stmt], params: Iterable[str] = (), is_class: bool = False) -> _Scope:
    names: dict[str, str | None] = dict.fromkeys((*_stored_names(stmts), *params))
    declared: set[str] = set()  # `global x` / `nonlocal x`: the name belongs to another scope
    for node in walk_scope(stmts):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            declared.update(node.names)
    for local, target in import_bindings(stmts, None, False).items():
        names[local] = _ROLES.get(target)
    for name in declared:
        names.pop(name, None)
    return _Scope(names, is_class)


def _global_roles(tree: ast.Module) -> dict[str, str | None]:
    """Roles of names a function imports under a `global` declaration (a lazy-import idiom)."""
    out: dict[str, str | None] = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, _FUNCTIONS):
            continue
        declared = {n for g in walk_scope(fn.body) if isinstance(g, ast.Global) for n in g.names}
        if declared:
            for local, target in import_bindings(fn.body, None, False).items():
                if local in declared:
                    out.setdefault(local, _ROLES.get(target))
    return out


def _role(chain: tuple[_Scope, ...], name: str) -> str | None:
    for scope in reversed(chain):
        if name in scope.names:
            return scope.names[name]
    return None


def _is_environ(chain: tuple[_Scope, ...], n: ast.expr) -> bool:
    if isinstance(n, ast.Name):
        return _role(chain, n.id) == "environ"
    return (
        isinstance(n, ast.Attribute)
        and n.attr == "environ"
        and isinstance(n.value, ast.Name)
        and _role(chain, n.value.id) == "os"
    )


def _env_key(node: ast.AST, chain: tuple[_Scope, ...]) -> ast.expr | None:
    """The key expression of an environment read, or None when `node` is not one."""
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            is_read = _role(chain, func.id) == "getenv"
        else:
            is_read = isinstance(func, ast.Attribute) and (
                (func.attr == "getenv" and isinstance(func.value, ast.Name) and _role(chain, func.value.id) == "os")
                or (func.attr == "get" and _is_environ(chain, func.value))
            )
        if is_read:
            return node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "key"), None)
    elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) and _is_environ(chain, node.value):
        return node.slice
    return None


def _without_class(chain: tuple[_Scope, ...]) -> tuple[_Scope, ...]:
    """Class scopes are visible to their own body only, not to anything nested in it."""
    return tuple(s for s in chain if not s.is_class)


def _scoped_children(node: ast.AST, chain: tuple[_Scope, ...]) -> list[tuple[ast.AST, tuple[_Scope, ...]]]:
    """Children of `node` paired with the scopes they are evaluated in.

    A def, class, lambda or comprehension opens a scope for its body; decorators, defaults,
    annotations, bases and a comprehension's first iterable are evaluated in the enclosing
    one. `if TYPE_CHECKING:` bodies are skipped, as in the import analysis.
    """
    if isinstance(node, ast.If) and is_type_checking(node.test):
        return [(c, chain) for c in node.orelse]
    if isinstance(node, _FUNCTIONS):
        args = node.args
        params = _params(args)
        outside = [*node.decorator_list, *args.defaults, *(d for d in args.kw_defaults if d is not None)]
        outside += [a.annotation for a in params if a.annotation is not None]
        if node.returns is not None:
            outside.append(node.returns)
        inner = _without_class(chain) + (_scope_of(node.body, [a.arg for a in params]),)
        return [(c, chain) for c in outside] + [(c, inner) for c in node.body]
    if isinstance(node, ast.ClassDef):
        outside = [*node.decorator_list, *node.bases, *(k.value for k in node.keywords)]
        inner = _without_class(chain) + (_scope_of(node.body, is_class=True),)
        return [(c, chain) for c in outside] + [(c, inner) for c in node.body]
    if isinstance(node, ast.Lambda):
        args = node.args
        outside = [*args.defaults, *(d for d in args.kw_defaults if d is not None)]
        inner = _without_class(chain) + (_Scope(dict.fromkeys(a.arg for a in _params(args))),)
        return [(c, chain) for c in outside] + [(node.body, inner)]
    if isinstance(node, _COMPREHENSIONS):
        first = node.generators[0].iter
        scope = _Scope(dict.fromkeys(_stored_names([g.target for g in node.generators])))
        inner = _without_class(chain) + (scope,)
        return [(first, chain)] + [(c, inner) for c in ast.iter_child_nodes(node) if c is not first]
    return [(c, chain) for c in ast.iter_child_nodes(node)]


def env_reads(tree: ast.Module) -> list[str]:
    """Literal keys of environment reads: os.getenv(K), os.environ.get(K), os.environ[K].

    A name counts as `os`, `os.environ` or `os.getenv` only where an import binds it in
    the scope that sees it; a parameter, local or comprehension variable of the same name
    hides the import. Stores (`os.environ[K] = v`) are not reads. K may be given by the
    `key=` keyword.
    """
    module = _scope_of(tree.body)
    for name, role in _global_roles(tree).items():
        module.names.setdefault(name, role)
    found: list[str] = []
    stack: list[tuple[ast.AST, tuple[_Scope, ...]]] = [(stmt, (module,)) for stmt in tree.body]
    while stack:
        node, chain = stack.pop()
        key = _env_key(node, chain)
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            found.append(key.value)
        stack.extend(_scoped_children(node, chain))
    return found
