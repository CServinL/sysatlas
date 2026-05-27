"""Hints file (sysatlas.json) is auto-loaded from the scan root."""
from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

import sysatlas
from sysatlas._reflection.hints import load_hints
from sysatlas._reflection.reflection import Hints


def _write_fixture(root: Path) -> None:
    (root / "myapp").mkdir()
    (root / "myapp" / "__init__.py").write_text("")
    (root / "myapp" / "api.py").write_text("from myapp import core\n")
    (root / "myapp" / "core.py").write_text("from myapp import storage\n")
    (root / "myapp" / "storage.py").write_text("")
    (root / "myapp" / "tests").mkdir()
    (root / "myapp" / "tests" / "__init__.py").write_text("")
    (root / "myapp" / "tests" / "test_api.py").write_text("from myapp import api\n")


class HintsFile(unittest.TestCase):
    def test_loads_json_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root)
            (root / "myapp" / "sysatlas.json").write_text(json.dumps({
                "exclude": ["tests/*", "*/tests/*"],
                "layer": {"myapp.storage": "data"},
                "rename": {"myapp.api": "API"},
            }))
            r = sysatlas.reflect(root / "myapp")
            self.assertIsInstance(r.hints, Hints)
            self.assertEqual(r.hints.layer["myapp.storage"], "data")

            m = r.to_system_map()
            names = set(m.diagram.components)
            self.assertIn("API", names)
            self.assertNotIn("api", names)
            self.assertNotIn("test_api", names)

            storage = m.diagram.components["storage"]
            self.assertEqual(storage.layer, "data")

    def test_no_hints_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_hints(tmp))

    def test_programmatic_hints_override_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root)
            (root / "myapp" / "sysatlas.json").write_text(json.dumps({
                "rename": {"myapp.api": "FromFile"},
            }))
            r = sysatlas.reflect(root / "myapp", hints=Hints(rename={"myapp.api": "FromKwarg"}))
            names = set(r.to_system_map().diagram.components)
            self.assertIn("FromKwarg", names)
            self.assertNotIn("FromFile", names)


if __name__ == "__main__":
    unittest.main()
