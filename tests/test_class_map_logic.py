"""Logic tests for ClassMap."""
import os
import tempfile
import unittest

from sysatlas import ClassMap


class ClassMapBuilder(unittest.TestCase):
    def test_class_with_attr_and_method(self) -> None:
        c = ClassMap()
        c.cls("User")
        c.attribute("User", "id", type="UUID")
        c.method("User", "save", return_type="bool", params=["force: bool"])
        u = c.diagram.classes["User"]
        self.assertEqual(u.attributes[0].name, "id")
        self.assertEqual(u.methods[0].params, ["force: bool"])

    def test_attribute_auto_creates_class(self) -> None:
        c = ClassMap()
        c.attribute("User", "id", type="UUID")
        self.assertIn("User", c.diagram.classes)

    def test_relate_auto_creates_classes(self) -> None:
        c = ClassMap()
        c.relate("A", "B", kind="inheritance")
        self.assertIn("A", c.diagram.classes)
        self.assertIn("B", c.diagram.classes)
        self.assertEqual(c.diagram.relations[0].kind, "inheritance")

    def test_self_inheritance_rejected(self) -> None:
        c = ClassMap()
        c.cls("A")
        c.relate("A", "A", kind="inheritance")
        with self.assertRaises(Exception):
            _ = c.diagram

    def test_kinds(self) -> None:
        c = ClassMap()
        c.cls("I", kind="interface")
        c.cls("A", kind="abstract")
        c.cls("E", kind="enum")
        d = c.diagram
        self.assertEqual(d.classes["I"].kind, "interface")
        self.assertEqual(d.classes["A"].kind, "abstract")
        self.assertEqual(d.classes["E"].kind, "enum")


class ClassMapSave(unittest.TestCase):
    def test_save_produces_html(self) -> None:
        c = ClassMap(title="T")
        c.cls("A").cls("B").relate("A", "B", kind="association")
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        c.save(path)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        finally:
            os.unlink(path)
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("mxGraphModel", content)


if __name__ == "__main__":
    unittest.main()
