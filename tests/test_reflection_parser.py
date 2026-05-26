"""Run the AST parser on sysatlas itself; assert known facts about its import graph."""
from __future__ import annotations

import unittest
from pathlib import Path

from sysatlas._reflection.parser import scan


REPO = Path(__file__).resolve().parents[1]
SYSATLAS = REPO / "sysatlas"


class ScanSysatlas(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = scan(SYSATLAS)
        self.by_name = self.graph.by_name()

    def test_root_recorded(self) -> None:
        self.assertEqual(self.graph.root, str(SYSATLAS))

    def test_picks_up_public_modules(self) -> None:
        names = set(self.by_name)
        for expected in {
            "sysatlas",
            "sysatlas.system_map",
            "sysatlas.system",
            "sysatlas.tree_map",
            "sysatlas._layout",
            "sysatlas._place",
            "sysatlas._route",
            "sysatlas._render",
            "sysatlas._ontology.architecture",
        }:
            self.assertIn(expected, names, f"missing {expected}")

    def test_skips_pycache(self) -> None:
        for m in self.graph.modules:
            self.assertNotIn("__pycache__", m.path)

    def test_filters_stdlib_and_third_party(self) -> None:
        layout = self.by_name["sysatlas._layout"]
        for imp in layout.imports:
            self.assertTrue(
                imp.startswith("sysatlas"),
                f"_layout should only have in-tree imports after filtering, got {imp}",
            )

    def test_layout_imports_place_and_route(self) -> None:
        layout = self.by_name["sysatlas._layout"]
        self.assertIn("sysatlas._place", layout.imports)
        self.assertIn("sysatlas._route", layout.imports)

    def test_relative_imports_resolved(self) -> None:
        sm = self.by_name["sysatlas.system_map"]
        joined = " ".join(sm.imports)
        self.assertIn("sysatlas._ontology.architecture", joined + " ")

    def test_ontology_architecture_uses_qualities(self) -> None:
        arch = self.by_name["sysatlas._ontology.architecture"]
        self.assertIn("sysatlas._ontology.qualities", arch.imports)

    def test_no_self_import(self) -> None:
        for m in self.graph.modules:
            self.assertNotIn(m.name, m.imports)


if __name__ == "__main__":
    unittest.main()
