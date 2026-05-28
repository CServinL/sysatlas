"""Logic tests for SequenceMap."""
import os
import tempfile
import unittest

from sysatlas import SequenceMap


class SequenceMapBuilder(unittest.TestCase):
    def test_actors_and_messages(self) -> None:
        s = SequenceMap()
        s.actor("A").actor("B")
        s.send("A", "B", label="ping")
        s.send("B", "A", label="pong", kind="reply")
        d = s.diagram
        self.assertEqual(list(d.actors), ["A", "B"])
        self.assertEqual([m.order for m in d.messages], [1, 2])
        self.assertEqual(d.messages[0].label, "ping")
        self.assertEqual(d.messages[1].kind, "reply")

    def test_send_auto_adds_actors(self) -> None:
        s = SequenceMap()
        s.send("X", "Y")
        self.assertIn("X", s.diagram.actors)
        self.assertIn("Y", s.diagram.actors)

    def test_explicit_order_advances_counter(self) -> None:
        s = SequenceMap()
        s.send("A", "B", order=10)
        s.send("A", "B")
        self.assertEqual([m.order for m in s.diagram.messages], [10, 11])

    def test_activation_and_frame(self) -> None:
        s = SequenceMap()
        s.actor("A").actor("B")
        s.send("A", "B")
        s.send("B", "A", kind="reply")
        s.activate("B", 1, 2)
        s.frame("opt", 1, 2, label="cond")
        d = s.diagram
        self.assertEqual(len(d.activations), 1)
        self.assertEqual(d.frames[0].kind, "opt")

    def test_chaining(self) -> None:
        m = (SequenceMap(title="t")
             .actor("A", kind="actor")
             .actor("B", kind="system")
             .send("A", "B", label="go"))
        self.assertEqual(m.diagram.actors["A"].kind, "actor")
        self.assertEqual(m.diagram.messages[0].label, "go")


class SequenceMapSave(unittest.TestCase):
    def _save(self, m: SequenceMap, viewer: str = "cdn") -> str:
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        m.save(path, viewer=viewer)
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        finally:
            os.unlink(path)

    def test_save_produces_html(self) -> None:
        s = SequenceMap(title="T").actor("A").actor("B").send("A", "B", label="hi")
        content = self._save(s)
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("GraphViewer", content)
        self.assertIn("mxGraphModel", content)
        self.assertIn("hi", content)


if __name__ == "__main__":
    unittest.main()
