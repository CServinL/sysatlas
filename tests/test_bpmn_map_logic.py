"""Logic tests for BPMNMap."""
import os
import tempfile
import unittest

from sysatlas import BPMNMap


class BPMNMapBuilder(unittest.TestCase):
    def test_pool_lane_event_activity(self) -> None:
        b = BPMNMap()
        b.pool("Co")
        b.lane("L", pool="Co")
        b.event("start", kind="start", lane="L")
        b.activity("work", lane="L")
        b.event("end", kind="end", lane="L")
        b.flow("start", "work")
        b.flow("work", "end")
        d = b.diagram
        self.assertIn("Co", d.pools)
        self.assertEqual(d.lanes["L"].pool, "Co")
        self.assertEqual(d.events["start"].kind, "start")
        self.assertEqual(len(d.flows), 2)

    def test_lane_auto_creates_pool(self) -> None:
        b = BPMNMap()
        b.lane("L", pool="Co")
        self.assertIn("Co", b.diagram.pools)

    def test_gateway_kinds(self) -> None:
        b = BPMNMap()
        b.pool("P").lane("L", pool="P")
        b.gateway("x",  kind="exclusive", lane="L")
        b.gateway("p",  kind="parallel",  lane="L")
        b.gateway("i",  kind="inclusive", lane="L")
        d = b.diagram
        self.assertEqual(d.gateways["x"].kind, "exclusive")
        self.assertEqual(d.gateways["p"].kind, "parallel")
        self.assertEqual(d.gateways["i"].kind, "inclusive")

    def test_flow_kinds(self) -> None:
        b = BPMNMap()
        b.event("s", kind="start").event("e", kind="end")
        b.flow("s", "e", kind="sequence")
        b.flow("s", "e", kind="conditional", label="if x")
        d = b.diagram
        self.assertEqual([f.kind for f in d.flows], ["sequence", "conditional"])

    def test_flow_endpoint_validation(self) -> None:
        b = BPMNMap()
        b.event("s", kind="start")
        b.flow("s", "missing")
        with self.assertRaises(Exception):
            _ = b.diagram


class BPMNMapSave(unittest.TestCase):
    def test_save_produces_html(self) -> None:
        b = BPMNMap(title="T")
        b.pool("P").lane("L", pool="P")
        b.event("s", kind="start", lane="L").event("e", kind="end", lane="L")
        b.flow("s", "e")
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        b.save(path)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        finally:
            os.unlink(path)
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("mxGraphModel", content)


if __name__ == "__main__":
    unittest.main()
