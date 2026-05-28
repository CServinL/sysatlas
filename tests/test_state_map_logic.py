"""Logic tests for StateMap."""
import os
import tempfile
import unittest

from sysatlas import StateMap


class StateMapBuilder(unittest.TestCase):
    def test_states_and_transitions(self) -> None:
        s = StateMap()
        s.initial("i")
        s.state("A")
        s.state("B")
        s.final("f")
        s.transition("i", "A")
        s.transition("A", "B", event="go")
        s.transition("B", "f")
        d = s.diagram
        self.assertEqual(d.states["i"].kind, "initial")
        self.assertEqual(d.states["f"].kind, "final")
        self.assertEqual(d.transitions[1].event, "go")

    def test_validation_requires_initial(self) -> None:
        s = StateMap()
        s.state("A")
        s.state("B")
        s.transition("A", "B")
        with self.assertRaises(Exception):
            _ = s.diagram

    def test_composite_with_children(self) -> None:
        s = StateMap()
        s.initial("i")
        s.state("Active", kind="composite")
        s.initial("ai", parent="Active")
        s.state("Sub", parent="Active")
        s.transition("i", "Active")
        s.transition("ai", "Sub")
        d = s.diagram
        self.assertEqual(d.states["ai"].parent, "Active")
        self.assertEqual(d.states["Sub"].parent, "Active")

    def test_entry_exit_do_actions(self) -> None:
        s = StateMap()
        s.initial("i")
        s.state("Running", entry="open()", do="loop()", exit="close()")
        s.transition("i", "Running")
        d = s.diagram
        self.assertEqual(d.states["Running"].entry_action, "open()")
        self.assertEqual(d.states["Running"].do_activity, "loop()")
        self.assertEqual(d.states["Running"].exit_action, "close()")


class StateMapSave(unittest.TestCase):
    def test_save_produces_html(self) -> None:
        s = StateMap(title="T")
        s.initial("i")
        s.state("A")
        s.transition("i", "A")
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        s.save(path)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        finally:
            os.unlink(path)
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("mxGraphModel", content)


if __name__ == "__main__":
    unittest.main()
