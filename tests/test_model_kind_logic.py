"""Tests for the ModelKind taxonomy."""
import unittest

from sysatlas._ontology.iso42010 import (
    ArchitectureDescription, Concern, Stakeholder, View, Viewpoint,
)
from sysatlas._ontology.model_kind import ModelKind
from sysatlas._ontology.model_kinds import DEFAULT_KINDS


class ModelKindSchema(unittest.TestCase):
    def test_basic_fields(self) -> None:
        mk = ModelKind(name="custom-arch", ontology="architecture",
                       description="d", conventions="c")
        self.assertEqual(mk.name, "custom-arch")
        self.assertEqual(mk.ontology, "architecture")

    def test_extras_rejected(self) -> None:
        with self.assertRaises(Exception):
            ModelKind(name="x", ontology="architecture", bogus=1)


class DefaultRegistry(unittest.TestCase):
    def test_default_kinds_present(self) -> None:
        self.assertIn("c4-context", DEFAULT_KINDS)
        self.assertIn("c4-container", DEFAULT_KINDS)
        self.assertIn("uml-sequence", DEFAULT_KINDS)
        self.assertIn("er-logical", DEFAULT_KINDS)
        self.assertIn("bpmn-subset", DEFAULT_KINDS)

    def test_multiple_kinds_same_ontology(self) -> None:
        arch_backed = [k.name for k in DEFAULT_KINDS.values() if k.ontology == "architecture"]
        self.assertGreaterEqual(len(arch_backed), 3)  # at least the 3 C4 zooms

    def test_kind_ontology_points_to_real_module(self) -> None:
        import importlib
        for kind in DEFAULT_KINDS.values():
            mod = importlib.import_module(f"sysatlas._ontology.{kind.ontology}")
            self.assertTrue(hasattr(mod, "__name__"))


class ViewpointModelKindValidation(unittest.TestCase):
    def test_viewpoint_refs_default_registry(self) -> None:
        ad = ArchitectureDescription(
            stakeholders={"dev": Stakeholder(name="dev")},
            concerns={"perf": Concern(name="perf", stakeholders=["dev"])},
            viewpoints={
                "vp": Viewpoint(name="vp", concerns=["perf"],
                                model_kinds=["c4-container"]),
            },
        )
        self.assertIn("vp", ad.viewpoints)

    def test_viewpoint_refs_project_local_registry(self) -> None:
        ad = ArchitectureDescription(
            stakeholders={"dev": Stakeholder(name="dev")},
            concerns={"perf": Concern(name="perf", stakeholders=["dev"])},
            model_kinds={
                "ddd-context": ModelKind(name="ddd-context", ontology="architecture",
                                         description="DDD bounded context"),
            },
            viewpoints={
                "vp": Viewpoint(name="vp", concerns=["perf"],
                                model_kinds=["ddd-context"]),
            },
        )
        self.assertIn("ddd-context", ad.model_kinds)

    def test_unknown_model_kind_rejected(self) -> None:
        with self.assertRaises(Exception):
            ArchitectureDescription(
                stakeholders={"dev": Stakeholder(name="dev")},
                concerns={"perf": Concern(name="perf", stakeholders=["dev"])},
                viewpoints={
                    "vp": Viewpoint(name="vp", concerns=["perf"],
                                    model_kinds=["bogus-kind"]),
                },
            )

    def test_legacy_empty_kinds_still_works(self) -> None:
        ad = ArchitectureDescription(
            stakeholders={"dev": Stakeholder(name="dev")},
            concerns={"perf": Concern(name="perf", stakeholders=["dev"])},
            viewpoints={"vp": Viewpoint(name="vp", concerns=["perf"])},
        )
        self.assertEqual(ad.viewpoints["vp"].model_kinds, [])


if __name__ == "__main__":
    unittest.main()
