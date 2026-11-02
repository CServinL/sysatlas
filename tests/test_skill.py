"""The bundled Claude Code Skill (sysatlas/_skill/SKILL.md) is well-formed and reachable."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import sysatlas


class BundledSkill(unittest.TestCase):
    def setUp(self) -> None:
        self.text = sysatlas.skill()

    def test_path_points_at_matching_file(self) -> None:
        p = Path(sysatlas.skill_path())
        self.assertTrue(p.is_file())
        self.assertEqual(p.read_text(encoding="utf-8"), self.text)

    def test_has_frontmatter_block(self) -> None:
        self.assertTrue(self.text.startswith("---\n"))
        self.assertIn("\n---\n", self.text[4:])

    def test_frontmatter_has_required_keys(self) -> None:
        front = self.text.split("\n---\n", 1)[0]
        name = re.search(r"^name:\s*(.+)$", front, re.M)
        desc = re.search(r"^description:\s*(.+)$", front, re.M)
        self.assertIsNotNone(name)
        self.assertIsNotNone(desc)
        self.assertEqual(name.group(1).strip(), "sysatlas")
        self.assertIn("sysatlas", desc.group(1).lower())

    def test_body_covers_the_essentials(self) -> None:
        for token in ("atlas", "reflect", "SystemMap", "sysatlas._*"):
            self.assertIn(token, self.text)


if __name__ == "__main__":
    unittest.main()
