"""Architecture mapping in the atlas: entry points, external systems, components,
spec conformance, and the intent overlay."""
from __future__ import annotations

import json
import re
import tempfile
import textwrap
import unittest
from unittest import mock
from pathlib import Path

import sysatlas
from sysatlas._reflection.intent import Intent
from sysatlas._reflection.reflection import Hints
from sysatlas._reflection.spec import ArchitectureSpec


def _tree(files: dict[str, str], pyproject: str = "") -> Path:
    base = Path(tempfile.mkdtemp())
    root = base / "pkg"
    root.mkdir()
    (root / "__init__.py").write_text("")
    if pyproject:
        (base / "pyproject.toml").write_text(textwrap.dedent(pyproject))
    for name, body in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(body))
    return root


def _reflect(root: Path, hints: Hints | None = None):
    return sysatlas.reflect(root, hints=hints or Hints()).exclude("__init__.py", "*/__init__.py")


def _mod(model, suffix: str):
    return next(m for m in model.modules if m.name.endswith(suffix))


class EntryPoints(unittest.TestCase):
    def test_detects_each_kind(self) -> None:
        root = _tree({
            "api.py": '''
                from fastapi import FastAPI
                app = FastAPI()

                @app.get("/items")
                def items(): ...

                @app.post("/items/{id}")
                async def create(): ...
            ''',
            "cli.py": '''
                import click

                @click.group()
                def main(): ...

                @main.command()
                def run(): ...

                if __name__ == "__main__":
                    main()
            ''',
            "jobs.py": '''
                from celery import shared_task

                @shared_task
                def nightly(): ...
            ''',
        })
        model = _reflect(root).to_atlas_model()
        self.assertEqual(
            _mod(model, "api").entry_points, ["route GET /items", "route POST /items/{id}"]
        )
        self.assertEqual(_mod(model, "cli").entry_points, ["cli main", "cli run", "main"])
        self.assertEqual(_mod(model, "jobs").entry_points, ["task nightly"])

    def test_dict_get_decorator_lookalikes_are_not_routes(self) -> None:
        root = _tree({
            "x.py": '''
                import functools
                cache = {}

                @functools.lru_cache(maxsize=None)
                def f(): ...

                @cache.get("key")
                def g(): ...
            ''',
        })
        self.assertEqual(_mod(_reflect(root).to_atlas_model(), "x").entry_points, [])

    def test_console_script_from_pyproject(self) -> None:
        root = _tree(
            {"cli.py": "def main(): ...\n"},
            pyproject='''
                [project]
                name = "pkg"
                [project.scripts]
                tool = "pkg.cli:main"
            ''',
        )
        model = _reflect(root).to_atlas_model()
        self.assertEqual(_mod(model, "cli").entry_points, ["script tool"])
        self.assertEqual(_mod(model, "cli").role, "entry-point")
        self.assertIn("`script tool`", _reflect(root).to_atlas())

    def test_no_toml_reader_means_no_scripts(self) -> None:
        root = _tree(
            {"cli.py": "def main(): ...\n"},
            pyproject='[project.scripts]\ntool = "pkg.cli:main"\n',
        )
        with mock.patch("sysatlas._reflection.project.tomllib", None):
            model = _reflect(root).to_atlas_model()
        self.assertEqual(_mod(model, "cli").entry_points, [])

    def test_broken_pyproject_is_ignored(self) -> None:
        root = _tree({"cli.py": "def main(): ...\n"}, pyproject="[project\nbroken")
        self.assertEqual(_mod(_reflect(root).to_atlas_model(), "cli").entry_points, [])


class ExternalSystems(unittest.TestCase):
    def test_systems_libraries_and_stdlib(self) -> None:
        root = _tree({
            "store.py": '''
                import os
                import json
                import sqlite3
                import requests
                import sqlalchemy.orm
                from pydantic import BaseModel
                from . import other
            ''',
            "other.py": "X = 1\n",
        })
        model = _reflect(root).to_atlas_model()
        self.assertEqual(
            _mod(model, "store").external, ["pydantic", "requests", "sqlalchemy", "sqlite3"]
        )
        kinds = {(e.kind, e.system) for e in model.external_systems}
        self.assertEqual(
            kinds,
            {
                ("datastore", "SQLite"),
                ("datastore", "SQL database (SQLAlchemy)"),
                ("http-client", "HTTP APIs"),
            },
        )
        self.assertEqual(model.libraries, ["pydantic"])
        self.assertEqual(_mod(model, "store").role, "adapter")

    def test_type_checking_imports_are_not_external(self) -> None:
        root = _tree({
            "t.py": '''
                from typing import TYPE_CHECKING
                if TYPE_CHECKING:
                    import requests
            ''',
        })
        self.assertEqual(_mod(_reflect(root).to_atlas_model(), "t").external, [])

    def test_same_system_through_two_drivers_is_one_row(self) -> None:
        root = _tree({"a.py": "import psycopg2\n", "b.py": "import asyncpg\n"})
        systems = _reflect(root).to_atlas_model().external_systems
        self.assertEqual([(s.kind, s.system) for s in systems], [("datastore", "PostgreSQL")])
        self.assertEqual(len(systems[0].used_by), 2)


class ModelsAndConfig(unittest.TestCase):
    def test_models_found_directly_and_through_same_module_parents(self) -> None:
        root = _tree({
            "m.py": '''
                from dataclasses import dataclass
                from typing import TypedDict
                from pydantic import BaseModel

                class Base1(BaseModel): ...
                class Child(Base1): ...
                class _Hidden(BaseModel): ...
                class Plain: ...

                @dataclass
                class Row: ...

                class Shape(TypedDict): ...
            ''',
        })
        m = _mod(_reflect(root).to_atlas_model(), "m")
        self.assertEqual(m.models, ["Base1", "Child", "Row", "Shape"])
        self.assertEqual(m.role, "logic")

    def test_env_vars_literal_keys_only(self) -> None:
        root = _tree({
            "c.py": '''
                import os
                a = os.getenv("A_VAR")
                b = os.environ.get("B_VAR", "x")
                c = os.environ["C_VAR"]
                d = os.getenv(name_from_elsewhere)
                e = os.environ.get(dynamic)
            ''',
        })
        model = _reflect(root).to_atlas_model()
        self.assertEqual([v.name for v in model.env_vars], ["A_VAR", "B_VAR", "C_VAR"])

    def test_undocumented_symbols(self) -> None:
        root = _tree({
            "d.py": '''
                """Doc."""
                def good():
                    """Has one."""
                def bad(): ...
                class Bare: ...
                def _private(): ...
            ''',
        })
        model = _reflect(root).to_atlas_model()
        self.assertEqual(_mod(model, "d").undocumented, ["Bare", "bad"])
        self.assertEqual(model.gaps.modules_without_doc, [])


class Components(unittest.TestCase):
    def _model(self, files: dict[str, str], hints: Hints | None = None):
        return _reflect(_tree(files), hints).to_atlas_model()

    def test_cycle_members_become_one_component(self) -> None:
        model = self._model({
            "a.py": "from . import b\n",
            "b.py": "from . import a\n",
            "c.py": "from . import a\n",
            "d.py": "from . import b\n",
        })
        owners = {m.label: m.component for m in model.modules}
        self.assertEqual(owners["a"], owners["b"])
        self.assertEqual(len([c for c in model.components if c.module_count == 2]), 1)
        self.assertNotIn(owners["c"], (owners["a"], owners["d"]))

    def test_helper_used_by_one_caller_joins_it(self) -> None:
        model = self._model({
            "main.py": "from . import helper\nfrom . import shared\n",
            "other.py": "from . import shared\n",
            "helper.py": "X = 1\n",
            "shared.py": "Y = 1\n",
        })
        owners = {m.label: m.component for m in model.modules}
        self.assertEqual(owners["main"], owners["helper"])
        self.assertNotEqual(owners["shared"], owners["main"])
        self.assertNotEqual(owners["shared"], owners["other"])

    def test_no_absorption_across_layers(self) -> None:
        hints = Hints(layer={"pkg.main": "edge", "pkg.helper": "data"})
        model = self._model(
            {"main.py": "from . import helper\n", "helper.py": "X = 1\n"}, hints
        )
        owners = {m.label: m.component for m in model.modules}
        self.assertNotEqual(owners["main"], owners["helper"])

    def test_chain_does_not_collapse_past_the_cap(self) -> None:
        files = {f"m{i}.py": f"from . import m{i + 1}\n" for i in range(24)}
        files["m24.py"] = "X = 1\n"
        model = self._model(files)
        self.assertGreater(len(model.components), 1)
        self.assertTrue(all(c.module_count <= 10 for c in model.components))

    def test_tiers_follow_dependency_direction(self) -> None:
        model = self._model({
            "top.py": "from . import mid\n",
            "mid.py": "from . import low\nfrom . import low2\n",
            "low.py": "X = 1\n",
            "low2.py": "X = 1\n",
            "side.py": "from . import low\n",
        })
        tier = {m.label: next(c.tier for c in model.components if c.name == m.component)
                for m in model.modules}
        self.assertLess(tier["top"], tier["low"])
        self.assertEqual(tier["top"], 0)

    def test_component_names_are_unique(self) -> None:
        model = self._model({
            "a/util.py": "X = 1\n",
            "b/util.py": "Y = 1\n",
            "a/x.py": "from . import util\n",
            "b/y.py": "from . import util\n",
        })
        names = [c.name for c in model.components]
        self.assertEqual(len(names), len(set(names)))


class SpecConformance(unittest.TestCase):
    FILES = {
        "web/views.py": "from pkg.core import logic\nfrom pkg.db import store\n",
        "core/logic.py": "from pkg.db import store\n",
        "db/store.py": "X = 1\n",
        "extra.py": "Z = 1\n",
    }

    def _atlas(self, spec: dict):
        hints = Hints(architecture=ArchitectureSpec.model_validate(spec))
        return _reflect(_tree(self.FILES), hints).to_atlas_model()

    def test_reports_forbidden_dependency_unmapped_and_empty(self) -> None:
        model = self._atlas({
            "components": [
                {"name": "web", "modules": ["pkg.web.*"], "depends_on": ["core"]},
                {"name": "core", "modules": ["pkg.core.*"], "depends_on": ["db"]},
                {"name": "db", "modules": ["pkg.db.*"]},
                {"name": "ghost", "modules": ["pkg.nothing.*"]},
            ]
        })
        c = model.conformance
        self.assertFalse(c.ok)
        self.assertEqual([(v.kind, v.src, v.dst) for v in c.violations], [("dependency", "web", "db")])
        self.assertEqual(c.unmapped_modules, ["pkg.extra"])
        self.assertEqual(c.empty_components, ["ghost"])

    def test_layer_violation(self) -> None:
        model = self._atlas({
            "layers": ["ui", "domain", "data"],
            "components": [
                {"name": "web", "modules": ["pkg.web.*"], "layer": "ui", "depends_on": ["core", "db"]},
                {"name": "core", "modules": ["pkg.core.*"], "layer": "domain", "depends_on": ["db"]},
                {"name": "db", "modules": ["pkg.db.*"], "layer": "data", "depends_on": ["web"]},
                {"name": "rest", "modules": ["pkg.extra"]},
            ],
        })
        # nothing imports web from db in FILES, so there is no layer violation
        self.assertEqual([v for v in model.conformance.violations if v.kind == "layer"], [])
        self.assertTrue(model.conformance.ok)

    def test_upward_import_is_a_layer_violation(self) -> None:
        files = {"low/a.py": "from pkg.high import b\n", "high/b.py": "X = 1\n"}
        hints = Hints(architecture=ArchitectureSpec.model_validate({
            "layers": ["high", "low"],
            "components": [
                {"name": "hi", "modules": ["pkg.high.*"], "layer": "high"},
                {"name": "lo", "modules": ["pkg.low.*"], "layer": "low", "depends_on": ["hi"]},
            ],
        }))
        model = _reflect(_tree(files), hints).to_atlas_model()
        self.assertEqual(
            [(v.kind, v.src, v.dst) for v in model.conformance.violations],
            [("layer", "lo", "hi")],
        )

    def test_conforming_code_is_ok_and_absent_without_spec(self) -> None:
        model = self._atlas({
            "components": [
                {"name": "web", "modules": ["pkg.web.*"], "depends_on": ["core", "db"]},
                {"name": "core", "modules": ["pkg.core.*"], "depends_on": ["db"]},
                {"name": "db", "modules": ["pkg.db.*"]},
                {"name": "rest", "modules": ["pkg.extra"]},
            ]
        })
        self.assertTrue(model.conformance.ok)
        self.assertIn("conforms", model.to_markdown())
        self.assertIsNone(_reflect(_tree(self.FILES)).to_atlas_model().conformance)
        self.assertNotIn("## Spec conformance", _reflect(_tree(self.FILES)).to_atlas())

    def test_bad_specs_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ArchitectureSpec.model_validate(
                {"components": [{"name": "a", "modules": ["x"], "depends_on": ["nope"]}]}
            )
        with self.assertRaises(ValueError):
            ArchitectureSpec.model_validate(
                {"components": [{"name": "a", "modules": ["x"]}, {"name": "a", "modules": ["y"]}]}
            )
        with self.assertRaises(ValueError):
            ArchitectureSpec.model_validate({"layers": ["ui", "ui"], "components": []})
        with self.assertRaises(ValueError):
            ArchitectureSpec.model_validate(
                {"layers": ["ui"], "components": [{"name": "a", "modules": ["x"], "layer": "zzz"}]}
            )

    def test_spec_loads_from_hints_file(self) -> None:
        root = _tree({"a.py": "X = 1\n"})
        (root / "sysatlas.json").write_text(json.dumps({
            "exclude": ["__init__.py"],
            "architecture": {"components": [{"name": "all", "modules": ["pkg.*"]}]},
        }))
        self.assertTrue(sysatlas.reflect(root).to_atlas_model().conformance.ok)


class IntentOverlay(unittest.TestCase):
    FILES = {"a.py": "def f(): ...\n", "b.py": "def g(): ...\n"}

    def _component(self, model, label: str):
        owner = next(m.component for m in model.modules if m.label == label)
        return next(c for c in model.components if c.name == owner)

    def test_states_none_unverified_current_stale(self) -> None:
        root = _tree(self.FILES)
        base = _reflect(root).to_atlas_model()
        fp = self._component(base, "a").fingerprint
        name = self._component(base, "a").name
        self.assertEqual(self._component(base, "a").intent_state, "none")

        def state(entry: dict) -> str:
            m = _reflect(root).to_atlas_model(intent={"components": {name: entry}})
            return self._component(m, "a").intent_state

        self.assertEqual(state({"purpose": "x"}), "unverified")
        self.assertEqual(state({"purpose": "x", "fingerprint": fp}), "current")
        self.assertEqual(state({"purpose": "x", "fingerprint": "000000000000"}), "stale")

    def test_fingerprint_tracks_symbols_not_bodies(self) -> None:
        root = _tree({"a.py": "def f():\n    return 1\n"})
        fp1 = _reflect(root).to_atlas_model().components[0].fingerprint
        (root / "a.py").write_text("def f():\n    return 2  # edited\n")
        fp2 = _reflect(root).to_atlas_model().components[0].fingerprint
        (root / "a.py").write_text("def f():\n    return 2\n\ndef extra(): ...\n")
        fp3 = _reflect(root).to_atlas_model().components[0].fingerprint
        self.assertEqual(fp1, fp2)
        self.assertNotEqual(fp1, fp3)

    def test_overlay_renders_purpose_patterns_and_summary(self) -> None:
        root = _tree(self.FILES)
        base = _reflect(root).to_atlas_model()
        name = self._component(base, "a").name
        text = _reflect(root).to_atlas(intent={
            "summary": "A tiny demo system.",
            "components": {name: {"purpose": "Does the thing.", "patterns": ["Pipeline"]}},
            "patterns": [{"name": "Pipeline", "description": "Stages in sequence.", "components": [name]}],
        })
        self.assertIn("A tiny demo system.", text)
        self.assertIn("Does the thing. (unverified)", text)
        self.assertIn("## Architectural patterns", text)
        self.assertIn("**Pipeline** — Stages in sequence.", text)
        self.assertIn("not generated", text)

    def test_gaps_list_unknown_and_stale_entries(self) -> None:
        root = _tree(self.FILES)
        model = _reflect(root).to_atlas_model(
            intent={"components": {"renamed-away": {"purpose": "old"}}}
        )
        self.assertEqual(model.gaps.unknown_intent, ["renamed-away"])
        self.assertEqual(len(model.gaps.components_without_intent), len(model.components))
        text = model.to_markdown()
        fp = model.components[0].fingerprint
        self.assertIn(f"[{fp}]", text)

    def test_loads_from_file_and_rejects_bad_input(self) -> None:
        root = _tree(self.FILES)
        good = Path(tempfile.mkdtemp()) / "intent.json"
        good.write_text(json.dumps({"summary": "From a file."}))
        self.assertIn("From a file.", _reflect(root).to_atlas(intent=good))
        self.assertEqual(Intent.model_validate_json(good.read_text()).summary, "From a file.")
        with self.assertRaises(FileNotFoundError):
            _reflect(root).to_atlas(intent=good.with_name("missing.json"))
        with self.assertRaises(ValueError):
            _reflect(root).to_atlas(intent={"components": {"x": {"purpose": "p", "bogus": 1}}})


class Sections(unittest.TestCase):
    def test_new_sections_present_and_bounded(self) -> None:
        files = {f"m{i}.py": f"import requests\nimport os\nos.getenv('V{i}')\n" for i in range(120)}
        text = _reflect(_tree(files)).to_atlas()
        for heading in (
            "## Components", "## Component dependencies", "## Entry points",
            "## External systems", "## Data models", "## Configuration",
            "## Documentation gaps",
        ):
            self.assertIn(heading, text)
        self.assertLess(text.count("\n"), 700)
        self.assertIn("more_", text)


class ReviewRegressions(unittest.TestCase):
    """Defects found in review of the architecture mapper."""

    def test_stale_marker_survives_a_long_purpose(self) -> None:
        r = _reflect(_tree({"a.py": "def f(): ...\n"}))
        name = r.to_atlas_model().components[0].name
        text = r.to_atlas(intent={
            "components": {name: {"purpose": "p" * 200, "fingerprint": "deadbeefdead"}}
        })
        self.assertIn("(stale)", text)

    def test_env_stores_are_not_reads_and_aliases_are_found(self) -> None:
        root = _tree({
            "e.py": '''
                import os
                from os import environ, getenv as ge
                os.environ["WRITTEN"] = "1"
                os.environ.setdefault("DEFAULTED", "1")
                os.environ.pop("POPPED", None)
                a = os.environ["READ_SUBSCRIPT"]
                b = environ.get("READ_ALIAS")
                c = ge("READ_GETENV_ALIAS")
            ''',
        })
        names = [v.name for v in _reflect(root).to_atlas_model().env_vars]
        self.assertEqual(names, ["READ_ALIAS", "READ_GETENV_ALIAS", "READ_SUBSCRIPT"])

    def test_models_follow_inheritance_across_modules(self) -> None:
        root = _tree({
            "base.py": "from pydantic import BaseModel\nclass Common(BaseModel): ...\n",
            "m.py": "from pkg.base import Common\nclass User(Common): ...\n",
            "n.py": "from pkg import base\nclass Admin(base.Common): ...\n",
            "plain.py": "from abc import ABC\nclass Base(ABC): ...\nclass Impl(Base): ...\n",
            "orm.py": "from sqlalchemy.orm import declarative_base\nclass Base: ...\nclass Row(Base): ...\n",
        })
        model = _reflect(root).to_atlas_model()
        self.assertEqual(_mod(model, "m").models, ["User"])
        self.assertEqual(_mod(model, "n").models, ["Admin"])
        self.assertEqual(_mod(model, "plain").models, [])
        self.assertEqual(_mod(model, "orm").models, ["Row"])

    def test_entry_decorators_need_a_framework_import(self) -> None:
        root = _tree({
            "t.py": '''
                import pytest

                @pytest.mark.group
                def a(): ...

                @x.command
                def b(): ...

                @cache.get("/not-a-route")
                def c(): ...
            ''',
            "kw.py": '''
                from fastapi import FastAPI
                app = FastAPI()

                @app.get(path="/by-keyword")
                def d(): ...

                if "__main__" == __name__:
                    pass
            ''',
        })
        model = _reflect(root).to_atlas_model()
        self.assertEqual(_mod(model, "t").entry_points, [])
        self.assertEqual(_mod(model, "kw").entry_points, ["main", "route GET /by-keyword"])

    def test_big_chain_is_not_quadratic(self) -> None:
        import time

        n = 6000
        files = {f"m{i}.py": f"from . import m{i + 1}\n" for i in range(n)}
        files[f"m{n}.py"] = "X = 1\n"
        r = _reflect(_tree(files))
        start = time.perf_counter()
        r.to_atlas_model()
        self.assertLess(time.perf_counter() - start, 8.0)

    def test_spec_globs_are_case_sensitive(self) -> None:
        hints = Hints(architecture=ArchitectureSpec.model_validate({
            "components": [{"name": "w", "modules": ["pkg.Web*"]}]
        }))
        root = _tree({"web.py": "X = 1\n"})
        with mock.patch("os.path.normcase", str.lower):  # what fnmatch.fnmatch sees on Windows
            model = _reflect(root, hints).to_atlas_model()
        self.assertEqual(model.conformance.unmapped_modules, ["pkg.web"])

    def test_exclude_globs_are_case_sensitive(self) -> None:
        r = sysatlas.reflect(_tree({"web.py": "X = 1\n"}), hints=Hints()).exclude("pkg.WEB")
        with mock.patch("os.path.normcase", str.lower):  # what fnmatch.fnmatch sees on Windows
            names = [m.name for m in r.to_atlas_model().modules]
        self.assertIn("pkg.web", names)

    def test_pipe_in_a_name_does_not_break_the_table(self) -> None:
        hints = Hints(group={"pkg.a": "x|y"}, architecture=ArchitectureSpec.model_validate({
            "components": [
                {"name": "p|q", "modules": ["pkg.a"]},
                {"name": "r", "modules": ["pkg.b"]},
            ]
        }))
        text = _reflect(_tree({"a.py": "from pkg import b\n", "b.py": "X = 1\n"}), hints).to_atlas()
        self.assertIn("x\\|y", text)
        columns = 0
        for line in text.splitlines():
            if not line.startswith("|"):
                columns = 0
                continue
            unescaped = len(re.findall(r"(?<!\\)\|", line))
            if set(line) <= set("|-"):
                columns = unescaped
            elif columns:
                self.assertEqual(unescaped, columns, line)

    def test_intent_references_are_checked(self) -> None:
        with self.assertRaises(ValueError):
            Intent.model_validate({
                "components": {"a": {"purpose": "x", "patterns": ["Layred"]}},
                "patterns": [{"name": "Layered", "description": "d"}],
            })
        with self.assertRaises(ValueError):
            Intent.model_validate({
                "patterns": [{"name": "P", "description": "d"}, {"name": "P", "description": "e"}]
            })
        model = _reflect(_tree({"a.py": "X = 1\n"})).to_atlas_model(intent={
            "patterns": [{"name": "P", "description": "d", "components": ["billng"]}]
        })
        self.assertEqual(model.gaps.unknown_intent, ["pattern 'P' names billng"])

    def test_edges_through_unclaimed_modules_are_stated_as_unchecked(self) -> None:
        hints = Hints(architecture=ArchitectureSpec.model_validate({
            "components": [
                {"name": "api", "modules": ["pkg.api"]},
                {"name": "db", "modules": ["pkg.db"]},
            ]
        }))
        files = {"api.py": "from pkg import util\n", "util.py": "from pkg import db\n", "db.py": "X = 1\n"}
        model = _reflect(_tree(files), hints).to_atlas_model()
        self.assertEqual(model.conformance.unmapped_modules, ["pkg.util"])
        self.assertFalse(model.conformance.ok)
        self.assertIn("are not checked", model.to_markdown())


if __name__ == "__main__":
    unittest.main()
