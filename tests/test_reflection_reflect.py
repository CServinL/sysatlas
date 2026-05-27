"""End-to-end M2: sysatlas.reflect(sysatlas) → SystemMap with components + connections."""
from __future__ import annotations

import unittest
from pathlib import Path

import sysatlas


REPO = Path(__file__).resolve().parents[1]
SYSATLAS = REPO / "sysatlas"


class ReflectSysatlas(unittest.TestCase):
    def setUp(self) -> None:
        self.r = sysatlas.reflect(SYSATLAS).exclude("LLM_GUIDE.md", "_reflection/*")
        self.m = self.r.to_system_map(title="sysatlas internals")
        self.diagram = self.m.diagram

    def test_returns_reflection(self) -> None:
        self.assertIsInstance(self.r, sysatlas.Reflection)

    def test_builds_system_map(self) -> None:
        self.assertIsInstance(self.m, sysatlas.SystemMap)
        self.assertEqual(self.diagram.title, "sysatlas internals")

    def test_known_modules_present_as_components(self) -> None:
        names = set(self.diagram.components)
        for expected in {"system_map", "system", "_layout", "_place", "_route", "_render"}:
            self.assertIn(expected, names, f"missing component {expected}")

    def test_known_edge_present(self) -> None:
        edges = {(c.source, c.target) for c in self.diagram.connections}
        self.assertIn(("_layout", "_place"), edges)
        self.assertIn(("_layout", "_route"), edges)

    def test_layer_inference(self) -> None:
        render = self.diagram.components["_render"]
        self.assertEqual(render.layer, "render")

    def test_group_inference_for_ontology(self) -> None:
        arch = self.diagram.components["architecture"]
        self.assertEqual(arch.group, "diagram-types")

    def test_exclude_filters_modules(self) -> None:
        names = set(self.diagram.components)
        for excluded in {"reflection", "parser", "resolve", "layers"}:
            self.assertNotIn(excluded, names, f"{excluded} should be excluded")


if __name__ == "__main__":
    unittest.main()
