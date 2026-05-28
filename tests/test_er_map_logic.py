"""Logic tests for ERMap."""
import os
import tempfile
import unittest

from sysatlas import ERMap


class ERMapBuilder(unittest.TestCase):
    def test_entity_and_attribute(self) -> None:
        e = ERMap()
        e.entity("User").attribute("User", "id", type="uuid", is_key=True)
        u = e.diagram.entities["User"]
        self.assertEqual(u.attributes[0].name, "id")
        self.assertTrue(u.attributes[0].is_key)

    def test_attribute_auto_creates_entity(self) -> None:
        e = ERMap()
        e.attribute("Order", "id", is_key=True)
        self.assertIn("Order", e.diagram.entities)

    def test_relate_auto_creates_entities(self) -> None:
        e = ERMap()
        e.relate("A", "B", name="links")
        self.assertIn("A", e.diagram.entities)
        self.assertIn("B", e.diagram.entities)
        self.assertEqual(e.diagram.relationships[0].name, "links")

    def test_weak_entity_flag(self) -> None:
        e = ERMap().entity("LineItem", is_weak=True)
        self.assertTrue(e.diagram.entities["LineItem"].is_weak)

    def test_chaining(self) -> None:
        m = (ERMap(title="T")
             .entity("A")
             .entity("B")
             .relate("A", "B", source_card="1", target_card="*"))
        rel = m.diagram.relationships[0]
        self.assertEqual((rel.source_card, rel.target_card), ("1", "*"))


class ERMapSave(unittest.TestCase):
    def test_save_produces_html(self) -> None:
        e = ERMap(title="T").entity("A").entity("B").relate("A", "B", name="r")
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        e.save(path)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        finally:
            os.unlink(path)
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("GraphViewer", content)
        self.assertIn("mxGraphModel", content)


if __name__ == "__main__":
    unittest.main()
