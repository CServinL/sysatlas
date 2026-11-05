"""The scope analysis against Python itself.

Random programs are built from scope constructs (parameters, locals, global, nonlocal, class
bodies, comprehensions, lambdas, aliased imports), then run against recording stand-ins for
`os` and `click`. What the programs really read and decorated is the oracle: the analysis must
report exactly that.
"""
from __future__ import annotations

import builtins
import random
import types
import unittest
from pathlib import Path

from tmpdirs import mkdtemp

from sysatlas._reflection.parser import scan

ATTEMPTS = 14000
MIN_VALID = 400
ENV_NAMES = ("environ", "env", "g", "o", "os")
PARAM_NAMES = ("cmd", "environ", "env", "g", "o", "os")
IMPORTS = {
    "import os": "os", "import os as o": "o", "from os import environ": "environ",
    "from os import environ as env": "env", "from os import getenv as g": "g",
    "from os import getenv": "getenv", "import click": "click",
    "from click import command as cmd": "cmd", "from click import command": "command",
}
READS = (
    '{n}["{k}"]', '{n}.get("{k}")', '{n}.get(key="{k}")', 'os.environ["{k}"]', 'o.environ.get("{k}")',
    'os.getenv("{k}")', 'g("{k}")', 'g(key="{k}")', 'o.getenv("{k}")', 'getenv("{k}")', 'environ["{k}"]',
)
DECORATORS = ("cmd", "cmd()", "click.command()", "click.command", "command", "command()")


class Inert:
    """Stands for any parameter: callable, subscriptable, never recorded."""

    def __call__(self, f=None, *args, **kw):
        return f if callable(f) and not isinstance(f, Inert) else Inert()

    def __getitem__(self, key):
        return "v"

    def get(self, key=None, default=None):
        return "v"


def _run(source: str) -> tuple[list[str], list[str]] | None:
    """(environment keys read, functions decorated by click.command), or None if the program is invalid."""
    env: list[str] = []
    cli: list[str] = []

    class Environ(dict):
        def __getitem__(self, key):
            env.append(key)
            return "v"

        def get(self, key=None, default=None):
            env.append(key)
            return "v"

    def getenv(key=None, default=None):
        env.append(key)
        return "v"

    def command(f=None, **kw):
        if callable(f):
            cli.append(f.__name__)
            return f
        return lambda g: (cli.append(g.__name__), g)[1]

    modules = {
        "os": types.SimpleNamespace(environ=Environ(), getenv=getenv),
        "click": types.SimpleNamespace(command=command),
    }

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        return modules[name]

    namespace = {"__builtins__": {**vars(builtins), "__import__": fake_import}, "__name__": "gen", "Inert": Inert}
    try:
        exec(compile(source, "<generated>", "exec"), namespace)
    except Exception:  # SyntaxError, NameError, UnboundLocalError, AttributeError...: not a usable program
        return None
    return env, cli


class Builder:
    """Builds programs in which no scope both imports and assigns the same name.

    What such a name means depends on the order of the statements, which an analysis of
    scopes cannot decide; the analysis resolves it to the import (the `try: import x / except:
    x = None` idiom), and that choice is documented rather than tested here.
    """

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.keys = 0
        self.defs = 0
        self.scopes: list[dict[str, str]] = [{}]

    def bind(self, name: str, kind: str) -> bool:
        """Record a binding in the current scope; False if the scope already binds the name differently."""
        return self.scopes[-1].setdefault(name, kind) == kind

    def key(self) -> str:
        self.keys += 1
        return f"K{self.keys}"

    def name(self, prefix: str) -> str:
        self.defs += 1
        return f"{prefix}{self.defs}"

    def read(self) -> str:
        return self.rng.choice(READS).format(n=self.rng.choice(ENV_NAMES), k=self.key())

    def statement(self, depth: int, in_class: bool = False) -> list[str]:
        rng = self.rng
        kind = rng.choices(
            ["import", "read", "assign", "decorated", "function", "class", "expr", "shadowed_global"],
            weights=[4, 5, 2, 3, 3 if depth < 3 else 0, 1 if depth < 2 and not in_class else 0, 3, 2 if depth < 2 else 0],
        )[0]
        if kind == "import":
            line = rng.choice(list(IMPORTS))
            return [line] if self.bind(IMPORTS[line], "import") else ["pass"]
        if kind == "read":
            return [f"_ = {self.read()}"]
        if kind == "assign":
            name = rng.choice(ENV_NAMES + ("cmd",))
            return [f"{name} = Inert()"] if self.bind(name, "assign") else ["pass"]
        if kind == "decorated":
            return [f"@{rng.choice(DECORATORS)}", f"def {self.name('d')}(): pass"]
        if kind == "expr":
            k = self.key()
            choices = [
                f'_ = [env["{k}"] for env in [Inert()]]',
                f'_ = [environ["{k}"] for _i in [1]]',
                f'_ = [x for x in environ["{k}"]]',
                f'_ = (lambda env: env["{k}"])(Inert())',
                f'_ = (lambda: environ["{k}"])()',
            ]
            if self.bind("environ", "assign"):  # a walrus in a comprehension binds in the enclosing scope
                choices.append('_ = [(environ := Inert()) for _i in [1]]')
            return [rng.choice(choices)]
        if kind == "function":
            return self.function(depth)
        if kind == "shadowed_global":
            return self.shadowed_global()
        return self.klass(depth)

    def block(self, depth: int, count: int, in_class: bool = False) -> list[str]:
        lines: list[str] = []
        for _ in range(count):
            lines += self.statement(depth, in_class)
        return lines or ["pass"]

    def use_of(self, name: str) -> list[str]:
        """A statement that reads or decorates with `name`."""
        if name == "cmd":
            return ["@cmd", f"def {self.name('d')}(): pass"]
        k = self.key()
        uses = {
            "environ": f'environ["{k}"]', "env": f'env.get("{k}")', "g": f'g("{k}")',
            "o": f'o.getenv("{k}")', "os": f'os.environ["{k}"]',
        }
        return [f"_ = {uses[name]}"]

    def shadowed_global(self) -> list[str]:
        """An outer function whose parameter hides a module-level import, and a nested function that
        declares the name `global` and uses it: the use must resolve to the module's import."""
        imported = sorted(n for n, kind in self.scopes[0].items() if kind == "import" and n in PARAM_NAMES)
        if len(self.scopes) != 1 or not imported:
            return ["pass"]
        name = self.rng.choice(imported)
        outer, inner = self.name("f"), self.name("f")
        lines = [f"def {outer}({name}):", f"    def {inner}():", f"        global {name}"]
        lines += ["        " + line for line in self.use_of(name)]
        return lines + [f"    {inner}()", f"{outer}(Inert())"]

    def function(self, depth: int, method: bool = False) -> list[str]:
        rng = self.rng
        name = self.name("f")
        params = rng.sample(PARAM_NAMES, rng.randint(0, 2))
        head = []
        self.scopes.append({p: "param" for p in params})
        if rng.random() < 0.3:
            declared = rng.choice(ENV_NAMES + ("cmd",))
            head.append(f"{rng.choice(['global', 'global', 'nonlocal'])} {declared}")
            self.scopes[-1][declared] = "declared"  # nothing else in this scope may bind it
        forced = self.use_of(declared) if head else []  # a declared name is only interesting if it is used
        body = head + forced + self.block(depth + 1, rng.randint(1, 4))
        self.scopes.pop()
        signature = ", ".join((["self"] if method else []) + params)
        lines = [f"def {name}({signature}):"] + ["    " + b for b in body]
        call = f"{name}({', '.join('Inert()' for _ in params)})"
        return lines + [call]

    def klass(self, depth: int) -> list[str]:
        name = self.name("C")
        self.scopes.append({})
        body = self.block(depth + 1, self.rng.randint(1, 3), in_class=True)
        self.scopes.pop()
        method = self.function(depth + 1, method=True)
        defn, call = method[:-1], method[-1]
        mname = call.split("(")[0]
        params = call[len(mname) + 1 : -1]
        lines = [f"class {name}:"] + ["    " + b for b in body + defn]
        return lines + [f"{name}().{mname}({params})"]

    def program(self) -> str:
        return "\n".join(self.block(0, self.rng.randint(2, 7))) + "\n"


class ScopesAgainstExecution(unittest.TestCase):
    def test_env_reads_and_decorators_match_what_the_programs_do(self) -> None:
        root = Path(mkdtemp())
        expected: dict[str, tuple[list[str], list[str], str]] = {}
        for seed in range(ATTEMPTS):
            source = Builder(random.Random(seed)).program()
            result = _run(source)
            if result is None:
                continue
            name = f"p{seed}"
            (root / f"{name}.py").write_text(source)
            expected[name] = (sorted(set(result[0])), sorted(set(result[1])), source)
        self.assertGreaterEqual(len(expected), MIN_VALID, "too few programs ran: the generator is no longer exercising anything")

        modules = {m.name: m for m in scan(root).modules}
        mismatches = []
        for name, (env, cli, source) in expected.items():
            m = modules[name]
            found = [e.split(" ", 1)[1] for e in m.entry_points if e.startswith("cli ")]
            if m.env_vars != env or sorted(found) != cli:
                mismatches.append((name, env, m.env_vars, cli, sorted(found), source))
        for name, env, got_env, cli, got_cli, source in mismatches[:3]:
            print(f"--- {name}: env expected {env} got {got_env}; cli expected {cli} got {got_cli}\n{source}")
        self.assertEqual(len(mismatches), 0, f"{len(mismatches)} of {len(expected)} programs disagree")


if __name__ == "__main__":
    unittest.main()
