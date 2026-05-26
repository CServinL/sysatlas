"""Round-trip merge: reflected structure + user-authored annotation overlay."""
from __future__ import annotations

import unittest
from pathlib import Path

import sysatlas
from sysatlas._ontology.qualities import QualityAttribute


SYSATLAS = Path(__file__).resolve().parents[1] / "sysatlas"


class MergeOverlay(unittest.TestCase):
    def setUp(self) -> None:
        self.r = sysatlas.reflect(SYSATLAS).exclude("LLM_GUIDE.md", "_reflection/*")

    def _overlay(self) -> sysatlas.SystemMap:
        ov = sysatlas.SystemMap(title="overlay")
        ov.add_component(
            "_route",
            qualities=[QualityAttribute(category="performance_efficiency", criticality="high")],
        )
        ov.add_component(
            "GhostFromIntent",
            qualities=[QualityAttribute(category="security", criticality="critical")],
        )
        return ov

    def test_qualities_land_on_reflected_component(self) -> None:
        merged = self.r.merge_with(self._overlay(), title="merged")
        route = merged.diagram.components["_route"]
        cats = {q.category for q in route.qualities}
        self.assertIn("performance_efficiency", cats)

    def test_unmatched_overlay_becomes_stub(self) -> None:
        merged = self.r.merge_with(self._overlay())
        self.assertIn("GhostFromIntent", merged.diagram.components)
        ghost = merged.diagram.components["GhostFromIntent"]
        self.assertTrue(ghost.is_stub)
        self.assertEqual(ghost.defined_in, "user-asserted")

    def test_reflected_structure_preserved(self) -> None:
        merged = self.r.merge_with(self._overlay())
        edges = {(c.source, c.target) for c in merged.diagram.connections}
        self.assertIn(("_layout", "_place"), edges)


if __name__ == "__main__":
    unittest.main()
