"""Logic tests for the deterministic architecture atlas (Reflection.to_atlas)."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import sysatlas
from sysatlas._reflection.atlas import Atlas

REPO = Path(__file__).resolve().parents[1]
SYSATLAS = REPO / "sysatlas"

_SECTIONS = (
    "## Overview",
    "## Layers",
    "## Packages",
    "## Dependency structure",
    "## Import cycles",
    "## Coupling hotspots",
    "## Public API surface",
)


def _tree(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp()) / "pkg"
    root.mkdir()
    (root / "__init__.py").write_text("")
    for name, body in files.items():
        (root / name).write_text(textwrap.dedent(body))
    return root


def _reflect(root: Path):
    """Reflect a temp tree, dropping the empty package __init__ from the graph."""
    return sysatlas.reflect(root).exclude("__init__.py")


class Determinism(unittest.TestCase):
    def test_byte_identical_same_process(self) -> None:
        a = sysatlas.reflect(SYSATLAS).to_atlas(title="sysatlas")
        b = sysatlas.reflect(SYSATLAS).to_atlas(title="sysatlas")
        self.assertEqual(a, b)

    def test_identical_across_hash_seed(self) -> None:
        code = (
            "import sysatlas, hashlib;"
            "s=sysatlas.reflect(r'%s').to_atlas(title='x');"
            "print(hashlib.sha256(s.encode()).hexdigest())" % SYSATLAS
        )
        out = []
        for seed in ("0", "1", "2"):
            env = {**os.environ, "PYTHONHASHSEED": seed}
            r = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, env=env, cwd=REPO,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            out.append(r.stdout.strip())
        self.assertEqual(len(set(out)), 1, out)

    def test_no_absolute_paths(self) -> None:
        atlas = sysatlas.reflect(SYSATLAS).to_atlas()
        self.assertNotIn(str(REPO), atlas)
        self.assertNotIn(str(Path.home()), atlas)


class Structure(unittest.TestCase):
    def setUp(self) -> None:
        self.atlas = sysatlas.reflect(SYSATLAS).to_atlas(title="sysatlas")

    def test_all_sections_present(self) -> None:
        for section in _SECTIONS:
            self.assertIn(section, self.atlas)

    def test_public_api_listed(self) -> None:
        self.assertIn("`reflect`", self.atlas)
        self.assertIn("`SystemMap`", self.atlas)

    def test_bounded_medium(self) -> None:
        self.assertLess(len(self.atlas.splitlines()), 400)

    def test_excludes_honored(self) -> None:
        atlas = sysatlas.reflect(SYSATLAS).exclude("_reflection/*").to_atlas()
        self.assertNotIn("`parser`", atlas)
        self.assertNotIn("`metrics`", atlas)
        self.assertNotIn("### _reflection", atlas)


class Cycles(unittest.TestCase):
    def test_true_positive(self) -> None:
        root = _tree({
            "a.py": "from pkg import b\n",
            "b.py": "from pkg import a\n",
        })
        atlas = _reflect(root).to_atlas()
        cyc = atlas.split("## Import cycles", 1)[1]
        self.assertIn("a", cyc)
        self.assertIn("b", cyc)
        self.assertNotIn("None detected", cyc)

    def test_true_negative(self) -> None:
        root = _tree({
            "a.py": "from pkg import b\n",
            "b.py": "x = 1\n",
        })
        atlas = _reflect(root).to_atlas()
        self.assertIn("_None detected._", atlas.split("## Import cycles", 1)[1])


class TypeCheckingImports(unittest.TestCase):
    def test_skips_type_only_but_keeps_runtime_else(self) -> None:
        root = _tree({
            "a.py": """\
                from typing import TYPE_CHECKING
                if TYPE_CHECKING:
                    from pkg import b
                else:
                    from pkg import b
            """,
            "b.py": "x = 1\n",
        })
        graph = _reflect(root).graph.by_name()
        self.assertIn("pkg.b", graph["pkg.a"].imports)


class FanCounts(unittest.TestCase):
    def test_known_edges(self) -> None:
        root = _tree({
            "hub.py": "x = 1\n",
            "a.py": "from pkg import hub\n",
            "b.py": "from pkg import hub\n",
            "c.py": "from pkg import hub, a\n",
        })
        model = _reflect(root).to_atlas_model()
        by_name = {m.name: m for m in model.modules}
        self.assertEqual(by_name["pkg.hub"].fan_in, 3)
        self.assertEqual(by_name["pkg.hub"].fan_out, 0)
        self.assertEqual(by_name["pkg.c"].fan_out, 2)
        self.assertEqual(model.hotspots[0], "pkg.hub")


class DisplayCollisions(unittest.TestCase):
    def test_colliding_names_disambiguated(self) -> None:
        root = _tree({"a.py": "x = 1\n"})
        (root / "sub").mkdir()
        (root / "sub" / "__init__.py").write_text("")
        (root / "sub" / "a.py").write_text("from pkg import a\n")
        model = _reflect(root).to_atlas_model()
        labels = sorted(m.label for m in model.modules)
        self.assertEqual(len(labels), len(set(labels)), labels)
        self.assertIn("sub.a", labels)


class Symbols(unittest.TestCase):
    def test_classes_in_graph(self) -> None:
        graph = sysatlas.reflect(SYSATLAS).graph.by_name()
        self.assertLessEqual(
            {"Component", "Connection"},
            set(graph["sysatlas._ontology.architecture"].classes),
        )

    def test_symbols_column_shows_classes_and_functions(self) -> None:
        root = _tree({
            "a.py": "class Foo:\n    pass\n\n\ndef bar():\n    pass\n",
        })
        packages = _reflect(root).to_atlas().split("## Packages", 1)[1]
        row = next(line for line in packages.splitlines() if "`a`" in line)
        self.assertIn("Foo", row)
        self.assertIn("bar()", row)


class PublicApi(unittest.TestCase):
    def test_annotated_all_is_read(self) -> None:
        root = Path(tempfile.mkdtemp()) / "pkg"
        root.mkdir()
        (root / "__init__.py").write_text('__all__: list[str] = ["Foo", "Bar"]\n')
        atlas = sysatlas.reflect(root).to_atlas()
        api = atlas.split("## Public API surface", 1)[1]
        self.assertIn("`Foo`", api)
        self.assertIn("`Bar`", api)


class LargeTree(unittest.TestCase):
    def test_truncates_and_stays_bounded(self) -> None:
        files = {}
        for i in range(300):
            files[f"m{i:03d}.py"] = f"from pkg import m{(i + 1) % 300:03d}\n"
        root = _tree(files)
        model = _reflect(root).to_atlas_model(max_modules=80)
        self.assertTrue(model.truncated)
        atlas = model.to_markdown()
        self.assertLess(len(atlas.splitlines()), 700)
        self.assertIn("more_", atlas)

    def test_per_group_cap_scales_with_max_modules(self) -> None:
        files = {}
        for i in range(300):
            files[f"m{i:03d}.py"] = f"from pkg import m{(i + 1) % 300:03d}\n"
        root = _tree(files)
        r = _reflect(root)
        small = r.to_atlas_model(max_modules=30).to_markdown().count("\n| `m")
        large = r.to_atlas_model(max_modules=80).to_markdown().count("\n| `m")
        self.assertLess(small, large)

    def test_large_cycle_edges_are_capped(self) -> None:
        files = {}
        for i in range(300):
            files[f"m{i:03d}.py"] = f"from pkg import m{(i + 1) % 300:03d}\n"
        root = _tree(files)
        atlas = _reflect(root).to_atlas()
        cyc = atlas.split("## Import cycles", 1)[1].split("## Coupling hotspots")[0]
        self.assertLess(len(cyc.splitlines()), 30)
        self.assertIn("more edges", cyc)


class JsonModel(unittest.TestCase):
    def test_roundtrip(self) -> None:
        model = sysatlas.reflect(SYSATLAS).to_atlas_model(title="sysatlas")
        restored = Atlas.model_validate_json(model.model_dump_json())
        self.assertEqual(restored.module_count, model.module_count)
        self.assertEqual(restored.to_markdown(), model.to_markdown())


class SyntaxErrorFile(unittest.TestCase):
    def test_unparsed_surfaced(self) -> None:
        root = _tree({
            "ok.py": "x = 1\n",
            "broken.py": "def (:\n",
        })
        atlas = _reflect(root).to_atlas()
        self.assertIn("unparsed", atlas.split("## Layers", 1)[0])


@unittest.skipUnless(
    __import__("importlib").util.find_spec("tree_sitter_rust"),
    "requires sysatlas[reflect-rust]",
)
class RustDegrades(unittest.TestCase):
    def test_no_symbol_columns(self) -> None:
        root = Path(tempfile.mkdtemp()) / "crate" / "src"
        root.mkdir(parents=True)
        (root / "main.rs").write_text("mod foo;\nuse crate::foo::bar;\nfn main(){bar();}\n")
        (root / "foo.rs").write_text("pub fn bar() {}\n")
        atlas = sysatlas.reflect_rust(root.parent).to_atlas(title="crate")
        self.assertIn("## Packages", atlas)
        self.assertNotIn("| symbols |", atlas)
        self.assertNotIn("| purpose |", atlas)

    def test_main_and_lib_crate_collision_deduped(self) -> None:
        root = Path(tempfile.mkdtemp()) / "crate" / "src"
        root.mkdir(parents=True)
        (root / "main.rs").write_text("fn main() {}\n")
        (root / "lib.rs").write_text("pub fn run() {}\n")
        model = sysatlas.reflect_rust(root.parent).to_atlas_model(title="crate")
        names = [m.name for m in model.modules]
        self.assertEqual(names.count("crate"), 1)


if __name__ == "__main__":
    unittest.main()
