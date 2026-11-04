"""The bundled Claude Code Skills (sysatlas/_skill/<name>/SKILL.md) are well-formed and reachable."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import sysatlas

NAMES = ("sysatlas", "sysatlas-document")


def _front(text: str) -> str:
    return text.split("\n---\n", 1)[0]


class BundledSkills(unittest.TestCase):
    def test_path_points_at_matching_file(self) -> None:
        for name in NAMES:
            with self.subTest(name=name):
                p = Path(sysatlas.skill_path(name))
                self.assertTrue(p.is_file())
                self.assertEqual(p.parent.name, name)
                self.assertEqual(p.read_text(encoding="utf-8"), sysatlas.skill(name))

    def test_default_is_the_main_skill(self) -> None:
        self.assertEqual(sysatlas.skill(), sysatlas.skill("sysatlas"))
        self.assertEqual(sysatlas.skill_path(), sysatlas.skill_path("sysatlas"))

    def test_frontmatter_block_and_required_keys(self) -> None:
        for name in NAMES:
            with self.subTest(name=name):
                text = sysatlas.skill(name)
                self.assertTrue(text.startswith("---\n"))
                self.assertIn("\n---\n", text[4:])
                front = _front(text)
                self.assertEqual(
                    re.search(r"^name:\s*(.+)$", front, re.M).group(1).strip(), name
                )
                desc = re.search(r"^description:\s*(.+)$", front, re.M)
                self.assertIsNotNone(desc)
                self.assertIn("sysatlas", desc.group(1).lower())

    def test_main_skill_covers_the_essentials(self) -> None:
        text = sysatlas.skill("sysatlas")
        for token in ("atlas", "reflect", "SystemMap", "sysatlas._*", "sysatlas-document"):
            self.assertIn(token, text)

    def test_document_skill_covers_the_workflow(self) -> None:
        text = sysatlas.skill("sysatlas-document")
        for token in ("Documentation gaps", "intent.json", "fingerprint", "docstring", "patterns"):
            self.assertIn(token, text)

    def test_document_skill_has_a_complete_pattern_checklist(self) -> None:
        text = sysatlas.skill("sysatlas-document")
        section = text.split("## Pattern checklist", 1)[1].split("\n## ", 1)[0]
        rows = [
            ln for ln in section.splitlines()
            if ln.startswith("| ") and not ln.startswith("| Pattern") and not ln.startswith("|---")
        ]
        self.assertGreaterEqual(len(rows), 10)
        for row in rows:
            with self.subTest(row=row[:40]):
                cells = [c.strip() for c in row.strip("|").split("|")]
                self.assertEqual(len(cells), 3)
                self.assertTrue(all(cells))
                self.assertIn(cells[1], ("yes", "no"))
        for verdict in ("`present`", "`partial`", "`absent`"):
            self.assertIn(verdict, section)
        self.assertIn("Detector limits", section)
        self.assertIn("not that the pattern\nis absent", section)
        self.assertNotIn("Do not repeat the search", section)
        self.assertIn("Answer every row", section)

    def test_checklist_matches_the_detectors(self) -> None:
        from sysatlas._reflection.patterns import ORDER

        text = sysatlas.skill("sysatlas-document")
        section = text.split("## Pattern checklist", 1)[1].split("\n## ", 1)[0]
        detected = {
            ln.strip("|").split("|")[0].strip()
            for ln in section.splitlines()
            if ln.startswith("| ") and "| yes |" in ln
        }
        self.assertEqual(detected, set(ORDER))

    def test_unknown_name_is_rejected_with_the_valid_ones(self) -> None:
        for bad in ("nope", "../sysatlas", ""):
            with self.subTest(name=bad):
                with self.assertRaises(ValueError) as ctx:
                    sysatlas.skill(bad)
                self.assertIn("sysatlas-document", str(ctx.exception))

    def test_document_skill_example_matches_the_intent_schema(self) -> None:
        import json
        from sysatlas._reflection.intent import Intent

        block = re.search(r"```json\n(.*?)```", sysatlas.skill("sysatlas-document"), re.S)
        self.assertIsNotNone(block)
        Intent.model_validate(json.loads(block.group(1)))


if __name__ == "__main__":
    unittest.main()
