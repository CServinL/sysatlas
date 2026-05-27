"""Hub-and-spoke placement: components land in the right region."""
import unittest

from sysatlas._hub_layout import compute_hub_layout


def _layered(layer: str, *names: str) -> dict:
    return {n: {"layer": layer} for n in names}


class HubLayoutPlacement(unittest.TestCase):
    def setUp(self) -> None:
        nodes = {}
        nodes.update(_layered("interfaces", "User", "LLM"))
        nodes.update(_layered("write", "Builders", "Reflection"))
        nodes.update(_layered("hub", "Ontology"))
        nodes.update(_layered("read", "Render"))
        nodes.update(_layered("external", "Source code", "Diagrams"))
        self.pos, self.routes, self.heights = compute_hub_layout(nodes, [], [])

    def test_hub_at_centre(self) -> None:
        self.assertIn("Ontology", self.pos)
        self.assertGreater(self.heights["Ontology"], 60)

    def test_interfaces_above_hub(self) -> None:
        for n in ("User", "LLM"):
            self.assertLess(self.pos[n][1], self.pos["Ontology"][1])

    def test_external_below_hub(self) -> None:
        for n in ("Source code", "Diagrams"):
            self.assertGreater(self.pos[n][1], self.pos["Ontology"][1])

    def test_write_left_of_hub(self) -> None:
        for n in ("Builders", "Reflection"):
            self.assertLess(self.pos[n][0], self.pos["Ontology"][0])

    def test_read_right_of_hub(self) -> None:
        self.assertGreater(self.pos["Render"][0], self.pos["Ontology"][0])


if __name__ == "__main__":
    unittest.main()
