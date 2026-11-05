"""A builder with nothing in it saves (or says clearly why it cannot), never dies in the layout engine."""
from __future__ import annotations

import unittest
from pathlib import Path

import sysatlas
from tmpdirs import mkdtemp


class EmptyDiagrams(unittest.TestCase):
    def test_empty_diagrams_save(self) -> None:
        for kind in ("SystemMap", "ERMap", "StateMap", "ClassMap", "SequenceMap", "BPMNMap"):
            with self.subTest(kind=kind):
                path = Path(mkdtemp()) / "e.html"
                getattr(sysatlas, kind)(title="empty").save(str(path))
                self.assertGreater(path.stat().st_size, 0)

    def test_a_frame_without_actors_is_skipped(self) -> None:
        path = Path(mkdtemp()) / "e.html"
        sysatlas.SequenceMap(title="frame only").frame("loop", 1, 2, label="x").save(str(path))
        self.assertGreater(path.stat().st_size, 0)

    def test_an_empty_tree_says_why_it_cannot_be_drawn(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            sysatlas.TreeMap(title="empty").save(str(Path(mkdtemp()) / "e.html"))
        self.assertIn("root", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
