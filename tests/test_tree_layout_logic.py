"""Logic tests for compute_tree_layout."""
import unittest

from sysatlas._tree_layout import compute_tree_layout


class TreeLayoutCycles(unittest.TestCase):
    def test_valid_tree_lays_out(self) -> None:
        nodes = {"root": {}, "a": {}, "b": {}}
        edges = [{"source": "root", "target": "a"}, {"source": "root", "target": "b"}]
        pos, routes = compute_tree_layout(nodes, edges)
        self.assertEqual(set(pos), {"root", "a", "b"})

    def test_multi_root_rejected(self) -> None:
        nodes = {"a": {}, "b": {}}
        edges: list = []
        with self.assertRaises(ValueError):
            compute_tree_layout(nodes, edges)

    def test_cycle_reachable_from_root_rejected(self) -> None:
        nodes = {"root": {}, "a": {}, "b": {}}
        edges = [
            {"source": "root", "target": "a"},
            {"source": "a", "target": "b"},
            {"source": "b", "target": "a"},  # cycle back to a
        ]
        with self.assertRaises(ValueError):
            compute_tree_layout(nodes, edges)


if __name__ == "__main__":
    unittest.main()
