"""Builder-API coverage for sysatlas.SystemMap.

Mirrors the historical netlyx-era tests but against the current Pydantic
ArchitectureDiagram backing model and the draw.io renderer.
"""
import os
import tempfile
import unittest

from sysatlas import SystemMap


class SystemMapBuilder(unittest.TestCase):
    def test_add_component_and_connect(self) -> None:
        m = SystemMap()
        m.add_component("A", layer="l1")
        m.add_component("B", layer="l2")
        m.connect("A", "B", label="calls")
        comps = m.diagram.components
        self.assertIn("A", comps)
        self.assertIn("B", comps)
        edge = m.diagram.connections[0]
        self.assertEqual((edge.source, edge.target, edge.label), ("A", "B", "calls"))

    def test_connect_auto_adds_nodes(self) -> None:
        m = SystemMap()
        m.connect("X", "Y")
        self.assertIn("X", m.diagram.components)
        self.assertIn("Y", m.diagram.components)

    def test_group_registration(self) -> None:
        m = SystemMap()
        m.group("storage", color="#dcfce7")
        self.assertIn("storage", m.diagram.groups)
        self.assertEqual(m.diagram.groups["storage"].color, "#dcfce7")

    def test_layer_order_preserved(self) -> None:
        m = SystemMap()
        m.add_component("A", layer="ingress")
        m.add_component("B", layer="services")
        m.add_component("C", layer="storage")
        self.assertEqual(m._layer_order, ["ingress", "services", "storage"])

    def test_chaining(self) -> None:
        m = (
            SystemMap()
            .group("svc", color="#bbf7d0")
            .add_component("A", group="svc", layer="l1")
            .add_component("B", group="svc", layer="l2")
            .connect("A", "B")
        )
        self.assertIn("A", m.diagram.components)
        self.assertEqual(m.diagram.connections[0].target, "B")

    def test_label_separate_from_name(self) -> None:
        m = SystemMap()
        m.add_component("bbva", label="parsers/bbva.py", layer="entrada")
        self.assertEqual(m.diagram.components["bbva"].label, "parsers/bbva.py")
        self.assertEqual(m.diagram.components["bbva"].name, "bbva")

    def test_extra_metadata_kept(self) -> None:
        m = SystemMap()
        m.add_component("API Gateway", layer="ingress", tech="Envoy", owner="platform")
        c = m.diagram.components["API Gateway"]
        self.assertEqual(c.tech, "Envoy")
        # extra='allow' on Component
        self.assertEqual(c.model_extra.get("owner"), "platform")

    def test_edge_color_and_style(self) -> None:
        m = SystemMap()
        m.connect("A", "B", color="#3b82f6", style="dashed")
        e = m.diagram.connections[0]
        self.assertEqual(e.color, "#3b82f6")
        self.assertEqual(e.style, "dashed")


class SystemMapSave(unittest.TestCase):
    def _save(self, m: SystemMap, viewer: str = "cdn") -> str:
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        m.save(path, viewer=viewer)
        try:
            return open(path, encoding="utf-8").read()
        finally:
            os.unlink(path)

    def test_save_produces_html_with_drawio_viewer(self) -> None:
        m = SystemMap(title="Test")
        m.add_component("A", layer="l1")
        m.add_component("B", layer="l2")
        m.connect("A", "B", label="->")
        content = self._save(m)
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("GraphViewer", content)
        self.assertIn("mxGraphModel", content)

    def test_save_embed_viewer_inlines_script(self) -> None:
        m = SystemMap()
        m.add_component("A")
        m.add_component("B")
        m.connect("A", "B")
        embed = self._save(m, viewer="embed")
        cdn   = self._save(m, viewer="cdn")
        # cdn mode loads viewer via a <script src=...> tag; embed inlines it.
        self.assertIn('<script src="https://viewer.diagrams.net', cdn)
        self.assertNotIn('<script src="https://viewer.diagrams.net', embed)


if __name__ == "__main__":
    unittest.main()
