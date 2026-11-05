"""Invariants of the atlas, checked over many seeded random trees, and a malformed-input matrix.

The hand-written tests pin known cases. These look for the ones nobody thought of: name
collisions between inferred and declared groups, odd roots, broken files, hostile hints.
"""
from __future__ import annotations

import json
import random
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import sysatlas
from tmpdirs import mkdtemp
from sysatlas._reflection.reflection import Hints
from sysatlas._reflection.spec import ArchitectureSpec

SEEDS = range(150)
ROOT_NAMES = ("pkg", "code", "crate", "src", "big", "app")
SEGMENTS = ("a", "b", "sub", "big", "extra", "util", "x", "core", "io", "main")
GROUPS = ("big", "big.sub", "sub", "core", "g", "extra", "pkg")
LAYERS = ("edge", "services", "data", "infra", "zzz", "render")


def _build(seed: int) -> tuple[Path, Hints, list[str]]:
    """A random source tree, hints for it, and the dotted names of its modules."""
    rng = random.Random(seed)
    base = Path(mkdtemp())
    root = base / rng.choice(ROOT_NAMES)
    root.mkdir()
    has_init = rng.random() < 0.6
    if has_init:
        (root / "__init__.py").write_text("")
    prefix = root.name if has_init else None
    rels: set[str] = set()
    dense = seed % 3 == 0  # few packages holding many modules, to cross the component size cap
    for _ in range(rng.randint(12, 40) if dense else rng.randint(1, 45)):
        if dense:
            parts = [rng.choice(("big", "core")), rng.choice(("sub", "sub", "io", "")), f"m{rng.randint(0, 30)}"]
            parts = [p for p in parts if p]
        else:
            parts = [rng.choice(SEGMENTS) for _ in range(rng.randint(0, 3) + 1)]
        rels.add("/".join(parts) + ".py")
    for rel in sorted(rels):
        parent = (root / rel).parent
        parent.mkdir(parents=True, exist_ok=True)
        if parent != root and rng.random() < 0.5:
            (parent / "__init__.py").write_text("")
    dotted = []
    for rel in sorted(rels):
        lines = []
        for _ in range(rng.randint(0, 4)):
            target = rng.choice(sorted(rels)).removesuffix(".py").replace("/", ".")
            mod = f"{prefix}.{target}" if prefix else target
            lines.append(rng.choice([f"import {mod}", f"from {mod} import X", f"from . import {target.split('.')[0]}"]))
        if rng.random() < 0.3:
            lines += ["import os", "v = os.environ.get('V%d')" % rng.randint(0, 5)]
        if rng.random() < 0.3:
            lines += ["from pydantic import BaseModel", "class M(BaseModel): ..."]
        if rng.random() < 0.15:
            lines.append("def (:")  # syntax error
        if rng.random() < 0.1:
            lines.append('"""import %s.example"""' % root.name)
        body = "\n".join(lines) + "\nX = 1\n"
        (root / rel).write_bytes((b"\xef\xbb\xbf" if rng.random() < 0.05 else b"") + body.encode())
        dotted.append(".".join(([prefix] if prefix else []) + rel.removesuffix(".py").split("/")))
    hints = Hints(
        group={m: rng.choice(GROUPS) for m in rng.sample(dotted, k=min(len(dotted), rng.randint(0, 12)))},
        layer={m: rng.choice(LAYERS) for m in rng.sample(dotted, k=min(len(dotted), rng.randint(0, 8)))},
        rename={m: rng.choice(SEGMENTS) for m in rng.sample(dotted, k=min(len(dotted), rng.randint(0, 6)))},
    )
    return root, hints, dotted


class Invariants(unittest.TestCase):
    def _check(self, seed: int) -> None:
        root, hints, _ = _build(seed)
        model = sysatlas.reflect(root, hints=hints).to_atlas_model()
        text = model.to_markdown()

        names = [m.name for m in model.modules]
        self.assertEqual(len(names), len(set(names)), "module names are unique")
        comp_names = [c.name for c in model.components]
        self.assertEqual(len(comp_names), len(set(comp_names)), "component names are unique")
        known = set(comp_names)
        for m in model.modules:
            self.assertIn(m.component, known, f"{m.name} has an owner")
        for c in model.components:
            self.assertEqual(
                c.module_count, sum(1 for m in model.modules if m.component == c.name), "counts add up"
            )
            self.assertTrue(set(c.depends_on) <= known and set(c.dependents) <= known)
        self.assertEqual(sum(c.module_count for c in model.components), model.module_count)
        labels = [m.label for m in model.modules]
        self.assertEqual(len(labels), len(set(labels)), "module labels are unique")
        self.assertEqual(text, sysatlas.reflect(root, hints=hints).to_atlas(), "deterministic")
        self.assertEqual(model, sysatlas.reflect(root, hints=hints).to_atlas_model())
        for section in text.split("\n## ")[1:]:
            self.assertLess(len(section.splitlines()), 260)
        json.loads(model.model_dump_json())

    def test_invariants_hold_for_random_trees(self) -> None:
        for seed in SEEDS:
            with self.subTest(seed=seed):
                self._check(seed)

    def test_conformance_status_follows_the_spec(self) -> None:
        """Specs built so that the right status is known without the production formula."""
        for seed in range(60):
            root, _, _ = _build(seed)

            def status(*components: dict):
                spec = ArchitectureSpec.model_validate({"components": list(components)})
                return sysatlas.reflect(root, hints=Hints(architecture=spec)).to_atlas_model().conformance

            everything = {"name": "all", "modules": ["*"]}
            ghost = {"name": "ghost", "modules": ["nothing.here.*"]}
            with self.subTest(seed=seed):
                # one component owning every module: nothing unmapped, no edge crosses components
                self.assertTrue(status(everything).ok)
                # a planned component that matches nothing departs from the plan
                c = status(everything, ghost)
                self.assertFalse(c.ok)
                self.assertEqual(c.empty_components, ["ghost"])
                # a specific component declared after a catch-all can never own anything
                c = status(everything, {"name": "late", "modules": ["*"]})
                self.assertFalse(c.ok)
                self.assertEqual((c.empty_components, c.shadowed_components), ([], ["late"]))


class MalformedInputs(unittest.TestCase):
    """Valid syntax, wrong shape: incidental files are ignored, explicit config raises one clear error."""

    def _root(self, **files: str) -> Path:
        base = Path(mkdtemp())
        root = base / "pkg"
        root.mkdir()
        (root / "a.py").write_text("X = 1\n")
        for name, body in files.items():
            target = base / name if name == "pyproject.toml" else root / name
            target.write_text(body)
        return root

    def test_pyproject_with_the_wrong_shape_is_ignored(self) -> None:
        bodies = [
            'project = "demo"\n',
            "[project]\nscripts = []\n",
            "[project.scripts]\nx = 5\n",
            '[project.scripts]\nx = ["a", "b"]\n',
            "[project]\ngui-scripts = 3\n",
            "[project\nbroken",
            "",
        ]
        for body in bodies:
            with self.subTest(body=body):
                root = self._root(**{"pyproject.toml": body})
                self.assertEqual(sysatlas.reflect(root, hints=Hints()).to_atlas_model().module_count, 1)

    def test_a_pyproject_that_cannot_be_read_is_ignored(self) -> None:
        for label, content in [
            ("latin-1", b'[project]\nname = "caf\xe9"\n'),
            ("utf-16", '[project]\nname = "x"\n'.encode("utf-16")),
            ("nested too deep", b"x = " + b"[" * 5000 + b"]" * 5000 + b"\n"),
            ("nul bytes", b"\x00\x00"),
        ]:
            with self.subTest(label):
                root = self._root()
                (root.parent / "pyproject.toml").write_bytes(content)
                self.assertEqual(sysatlas.reflect(root, hints=Hints()).to_atlas_model().module_count, 1)

    def test_a_hints_file_that_cannot_be_decoded_names_the_file(self) -> None:
        root = self._root()
        (root / "sysatlas.json").write_bytes(b'{"exclude": []}\xff\xfe')
        with self.assertRaises(ValueError) as ctx:
            sysatlas.reflect(root)
        self.assertIn("sysatlas.json", str(ctx.exception))

    def test_a_yaml_hints_file_fails_with_one_error_naming_it(self) -> None:
        class YamlError(Exception):  # like yaml.YAMLError, which is not a ValueError
            pass

        def safe_load(text: str):
            if text == "boom":
                raise YamlError("while parsing a flow sequence")
            return {"[]": [], "0": 0, "": None, "exclude: [a]": {"exclude": ["a"]}}[text]

        stub = types.ModuleType("yaml")
        stub.safe_load = safe_load
        with mock.patch.dict(sys.modules, {"yaml": stub}):
            for text, ok in [("boom", False), ("[]", False), ("0", False), ("", True), ("exclude: [a]", True)]:
                with self.subTest(text=text):
                    root = self._root()
                    (root / "sysatlas.yaml").write_text(text)
                    if ok:
                        sysatlas.reflect(root)
                    else:
                        with self.assertRaises(ValueError) as ctx:
                            sysatlas.reflect(root)
                        self.assertIn("sysatlas.yaml", str(ctx.exception))

    def test_a_bad_hints_file_raises_one_clear_error_naming_it(self) -> None:
        for label, body in [
            ("a list", "[1, 2]"),
            ("invalid json", "{oops"),
            ("wrong field type", '{"exclude": 5}'),
            ("unknown field", '{"bogus": 1}'),
            ("bad spec", '{"architecture": {"components": [{"name": "a", "modules": ["x"], "depends_on": ["nope"]}]}}'),
        ]:
            with self.subTest(label):
                root = self._root(**{"sysatlas.json": body})
                with self.assertRaises(ValueError) as ctx:
                    sysatlas.reflect(root)
                self.assertIn("sysatlas.json", str(ctx.exception))

    def test_a_bad_intent_file_raises_one_clear_error_naming_it(self) -> None:
        root = self._root()
        for label, body in [
            ("not an object", "[]"),
            ("not utf-8", b"{}\xff"),
            ("invalid json", "{x"),
            ("unknown field", '{"bogus": 1}'),
            ("dangling pattern", '{"components": {"a": {"purpose": "p", "patterns": ["nope"]}}}'),
        ]:
            with self.subTest(label):
                path = Path(mkdtemp()) / "intent.json"
                path.write_bytes(body if isinstance(body, bytes) else body.encode())
                with self.assertRaises(ValueError) as ctx:
                    sysatlas.reflect(root, hints=Hints()).to_atlas(intent=path)
                self.assertIn("intent.json", str(ctx.exception))

    def test_one_hostile_source_file_does_not_abort_the_scan(self) -> None:
        root = self._root()
        (root / "deep.py").write_text("x = " + "+".join(["1"] * 4000) + "\n")
        # shapes that make the parser itself give up (MemoryError on current Pythons)
        (root / "nots.py").write_text("x = " + "not " * 20000 + "1\n")
        (root / "lambdas.py").write_text("x = " + "lambda: " * 3000 + "1\n")
        (root / "elifs.py").write_text("if a:\n    pass\n" + "elif a:\n    pass\n" * 6000)
        (root / "bom.py").write_bytes(b"\xef\xbb\xbfclass FromBom: ...\n")
        (root / "latin.py").write_bytes(b"# -*- coding: latin-1 -*-\nx = '\xe9'\nclass Latin: ...\n")
        (root / "nul.py").write_bytes(b"X = 1\x00\n")
        model = sysatlas.reflect(root, hints=Hints()).to_atlas_model()
        by = {m.name.split(".")[-1]: m for m in model.modules}
        self.assertEqual(by["bom"].classes, ["FromBom"])
        self.assertEqual(by["latin"].classes, ["Latin"])
        self.assertTrue(by["nul"].unparsed)
        self.assertEqual(model.module_count, 8)

    def test_the_public_api_reader_survives_a_bom_and_a_huge_expression(self) -> None:
        for label, init, expected in [
            ("bom", b'\xef\xbb\xbf__all__ = ["A", "B"]\n', ["A", "B"]),
            ("long concatenation", ("__all__ = " + " + ".join(["['a']"] * 6000) + "\n").encode(), ["a"]),
        ]:
            with self.subTest(label):
                base = Path(mkdtemp())
                root = base / "pkg"
                root.mkdir()
                (root / "__init__.py").write_bytes(init)
                self.assertEqual(sysatlas.reflect(root, hints=Hints()).to_atlas_model().public_api, expected)


if __name__ == "__main__":
    unittest.main()
