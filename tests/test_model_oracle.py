"""Data-model detection against Python itself.

Random modules define classes over aliased, dotted and subscripted bases and decorators, with
decoy imports inside functions. They are run against stand-ins for `pydantic` and `dataclasses`;
the classes that really derive from `BaseModel` or are dataclasses are the oracle.
"""
from __future__ import annotations

import builtins
import random
import types
import unittest
from pathlib import Path

from tmpdirs import mkdtemp

from sysatlas._reflection.parser import scan

ATTEMPTS = 6000
MIN_VALID = 400
BASE_IMPORTS = {
    "from pydantic import BaseModel": "BaseModel",
    "from pydantic import BaseModel as Schema": "Schema",
    "from pydantic import BaseModel as Model2": "Model2",
}
MODULE_IMPORTS = {"import pydantic": "pydantic", "import pydantic as pd": "pd"}
DC_IMPORTS = {
    "from dataclasses import dataclass": "dataclass",
    "from dataclasses import dataclass as dc": "dc",
    "import dataclasses": "dataclasses",
}
DECOYS = (
    "from collections import UserDict as Schema",
    "from collections import UserDict as BaseModel",
    "from collections import UserDict as dc",
    "import collections as pd",
)


class _BaseModel:
    def __class_getitem__(cls, item):
        return cls


def _dataclass(cls=None, **kw):
    def mark(c):
        c.__is_dc__ = True
        return c

    return mark(cls) if cls is not None else mark


def _models(source: str) -> list[str] | None:
    """Public top-level classes that derive from BaseModel or are dataclasses; None if the module is invalid."""
    modules = {
        "pydantic": types.SimpleNamespace(BaseModel=_BaseModel),
        "dataclasses": types.SimpleNamespace(dataclass=_dataclass),
        "collections": types.SimpleNamespace(UserDict=dict),
    }

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        return modules[name]

    namespace = {"__builtins__": {**vars(builtins), "__import__": fake_import}, "__name__": "gen"}
    try:
        exec(compile(source, "<generated>", "exec"), namespace)
    except Exception:
        return None
    found = []
    for name, value in namespace.items():
        if isinstance(value, type) and not name.startswith("_") and value.__module__ == "gen":
            if issubclass(value, _BaseModel) or getattr(value, "__is_dc__", False):
                found.append(name)
    return sorted(found)


def _program(rng: random.Random) -> str:
    lines: list[str] = []
    bound: dict[str, str] = {}  # name -> kind, so no name is both imported and assigned
    bases = ["object"]  # expressions usable as a base
    decorators: list[str] = []

    def add_import(table: dict[str, str], bases_for: str | None) -> None:
        line = rng.choice(list(table))
        name = table[line]
        if name in bound:
            return
        bound[name] = "import"
        lines.append(line)
        if bases_for == "model":
            bases.extend([name, f"{name}[int]"])
        elif bases_for == "module":
            bases.append(f"{name}.BaseModel")
        elif name == "dataclasses":
            decorators.extend(["dataclasses.dataclass", "dataclasses.dataclass(frozen=True)"])
        else:
            decorators.extend([name, f"{name}(frozen=True)"])

    for _ in range(rng.randint(2, 9)):
        kind = rng.choices(["model-import", "module-import", "dc-import", "class", "decoy"], weights=[3, 2, 2, 8, 2])[0]
        if kind == "model-import":
            add_import(BASE_IMPORTS, "model")
        elif kind == "module-import":
            add_import(MODULE_IMPORTS, "module")
        elif kind == "dc-import":
            add_import(DC_IMPORTS, None)
        elif kind == "decoy":
            lines += ["def helper():", f"    {rng.choice(DECOYS)}", "    return 1"]
        else:
            name = ("_" if rng.random() < 0.15 else "") + f"C{len(lines)}"
            deco = [f"@{rng.choice(decorators)}"] if decorators and rng.random() < 0.35 else []
            base = ", ".join(rng.sample(bases, rng.randint(1, min(2, len(bases)))))
            lines += deco + [f"class {name}({base}):", "    pass"]
            bases.extend([name, f"{name}[int]"] if False else [name])
    return "\n".join(lines) + "\n"


class ModelsAgainstExecution(unittest.TestCase):
    def test_detected_models_match_the_classes_that_are_models(self) -> None:
        root = Path(mkdtemp())
        expected: dict[str, tuple[list[str], str]] = {}
        for seed in range(ATTEMPTS):
            source = _program(random.Random(seed))
            result = _models(source)
            if result is None:
                continue
            (root / f"p{seed}.py").write_text(source)
            expected[f"p{seed}"] = (result, source)
        self.assertGreaterEqual(len(expected), MIN_VALID, "too few programs ran: the generator is no longer exercising anything")
        self.assertTrue(any(models for models, _ in expected.values()), "no generated program has a model")

        modules = {m.name: m for m in scan(root).modules}
        bad = [(n, want, modules[n].models, src) for n, (want, src) in expected.items() if modules[n].models != want]
        for n, want, got, src in bad[:3]:
            print(f"--- {n}: expected {want} got {got}\n{src}")
        self.assertEqual(len(bad), 0, f"{len(bad)} of {len(expected)} programs disagree")


if __name__ == "__main__":
    unittest.main()
