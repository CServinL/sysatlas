"""Architecture mapping in the atlas: entry points, external systems, components,
spec conformance, and the intent overlay."""
from __future__ import annotations

import json
import re
import textwrap
import unittest
from unittest import mock
from pathlib import Path

import sysatlas
from tmpdirs import mkdtemp
from sysatlas._reflection import project as project_module
from sysatlas._reflection.intent import Intent
from sysatlas._reflection.reflection import Hints
from sysatlas._reflection.spec import ArchitectureSpec


def _tree(files: dict[str, str], pyproject: str = "") -> Path:
    base = Path(mkdtemp())
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

    @unittest.skipIf(project_module.tomllib is None, "no TOML reader on this Python")
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

    def test_oversized_package_is_split_by_subpackage(self) -> None:
        files = {f"big/sub{i // 4}/m{i}.py": "X = 1\n" for i in range(16)}
        files["big/top.py"] = "Y = 1\n"
        model = self._model(files)
        names = sorted(c.name for c in model.components)
        self.assertEqual([n for n in names if n.startswith("big.")], [f"big.sub{i}" for i in range(4)])
        self.assertTrue(all(c.module_count <= 10 for c in model.components))

    def test_hinted_group_is_never_split(self) -> None:
        files = {f"m{i}.py": "X = 1\n" for i in range(14)}
        hints = Hints(group={f"pkg.m{i}": "bag" for i in range(14)})
        model = self._model(files, hints)
        self.assertEqual([(c.name, c.module_count) for c in model.components], [("bag", 14)])

    def test_clashing_names_keep_the_name_on_the_biggest_block(self) -> None:
        model = self._model({
            "util/a.py": "X = 1\n",
            "util/b.py": "X = 1\n",
            "util.py": "Z = 1\n",
        })
        names = sorted(c.name for c in model.components)
        self.assertIn("util", names)
        self.assertTrue(any(n.startswith("util (") for n in names), names)

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
        good = Path(mkdtemp()) / "intent.json"
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


class DetectorInputs(unittest.TestCase):
    """Inputs that fooled the architecture facts: lookalike decorators, stores, globs, tables, references."""

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


class ImportResolution(unittest.TestCase):
    """Parser fixes found by running the atlas on real repositories."""

    def test_namespace_package_root_resolves_its_own_imports(self) -> None:
        base = Path(mkdtemp())
        root = base / "app"  # no __init__.py: an implicit namespace package
        (root / "web").mkdir(parents=True)
        (root / "web" / "views.py").write_text("from app.core import logic\nimport rich\n")
        (root / "core").mkdir()
        (root / "core" / "logic.py").write_text("X = 1\n")
        model = sysatlas.reflect(root, hints=Hints()).to_atlas_model()
        self.assertEqual(
            sorted(m.name for m in model.modules), ["app.core.logic", "app.web.views"]
        )
        views = next(m for m in model.modules if m.name == "app.web.views")
        self.assertEqual(views.internal_deps, ["app.core.logic"])
        self.assertEqual(views.external, ["rich"])
        self.assertEqual(model.libraries, ["rich"])

    def test_container_root_is_not_given_a_prefix(self) -> None:
        base = Path(mkdtemp())
        root = base / "src"
        (root / "pkg").mkdir(parents=True)
        (root / "pkg" / "__init__.py").write_text("")
        (root / "pkg" / "a.py").write_text("from pkg import b\n")
        (root / "pkg" / "b.py").write_text("X = 1\n")
        names = sorted(m.name for m in sysatlas.reflect(root, hints=Hints()).graph.modules)
        self.assertEqual(names, ["pkg", "pkg.a", "pkg.b"])

    def test_relative_import_inside_init_means_the_package_itself(self) -> None:
        root = _tree({"sub/__init__.py": "from .worker import run\nfrom . import helper\n",
                      "sub/worker.py": "def run(): ...\n",
                      "sub/helper.py": "X = 1\n"})
        graph = sysatlas.reflect(root, hints=Hints()).graph.by_name()
        self.assertEqual(graph["pkg.sub"].imports, ["pkg.sub.helper", "pkg.sub.worker"])
        self.assertEqual(graph["pkg.sub"].external, [])

    def test_relative_import_in_a_regular_module_still_means_the_parent(self) -> None:
        root = _tree({"sub/__init__.py": "", "sub/a.py": "from . import b\nfrom ..top import T\n",
                      "sub/b.py": "X = 1\n", "top.py": "T = 1\n"})
        graph = sysatlas.reflect(root, hints=Hints()).graph.by_name()
        self.assertEqual(graph["pkg.sub.a"].imports, ["pkg.sub", "pkg.sub.b", "pkg.top"])


class ParsingAndGrouping(unittest.TestCase):
    """Oversized packages, container roots, aliased and dotted names, decorators imported by name, path globs."""

    def _model(self, files: dict[str, str]):
        return _reflect(_tree(files)).to_atlas_model()

    def _models(self, model) -> dict[str, list[str]]:
        return {m.name: m.models for m in model.modules if m.models}

    def test_oversized_subgroup_is_split_again(self) -> None:
        model = self._model({f"big/sub/m{i}.py": "X = 1\n" for i in range(11)})
        self.assertLessEqual(max(c.module_count for c in model.components), 10)

    def test_oversized_subgroup_splits_recursively_through_levels(self) -> None:
        files = {f"big/a/b/m{i}.py": "X = 1\n" for i in range(11)}
        files.update({f"big/a/c/m{i}.py": "X = 1\n" for i in range(3)})
        model = self._model(files)
        names = {c.name for c in model.components}
        self.assertLessEqual(max(c.module_count for c in model.components), 10)
        self.assertIn("big.a.c", names)

    def test_checkout_directory_named_like_its_package_keeps_container_naming(self) -> None:
        base = Path(mkdtemp())
        root = base / "pkg"  # repository checkout
        (root / "pkg").mkdir(parents=True)  # the package itself
        (root / "pkg" / "__init__.py").write_text("")
        (root / "pkg" / "a.py").write_text("from pkg import b\n")
        (root / "pkg" / "b.py").write_text("X = 1\n")
        graph = sysatlas.reflect(root, hints=Hints()).graph.by_name()
        self.assertEqual(sorted(graph), ["pkg", "pkg.a", "pkg.b"])
        self.assertIn("pkg.b", graph["pkg.a"].imports)

    def test_aliased_imports_are_resolved_for_models_and_interfaces(self) -> None:
        model = self._model({
            "m.py": "from pydantic import BaseModel as Schema\nfrom dataclasses import dataclass as dc\nclass User(Schema): ...\n@dc\nclass Row: ...\n",
            "kid.py": "from pkg.m import User\nclass Admin(User): ...\n",
            "base.py": "from abc import ABC as Root, abstractmethod as am\nclass S(Root):\n    @am\n    def f(self): ...\n",
            "a.py": "from pkg.base import S\nclass A(S): ...\n",
            "b.py": "from pkg.base import S\nclass B(S): ...\n",
        })
        self.assertEqual(self._models(model), {"pkg.m": ["Row", "User"], "pkg.kid": ["Admin"]})
        self.assertEqual(_pattern(model, "Strategy").evidence[0].split(":")[0], "S (base)")

    def test_attribute_chain_bases_resolve(self) -> None:
        model = self._model({
            "base.py": "from pydantic import BaseModel\nclass Common(BaseModel): ...\n",
            "m.py": "import pkg.base\nclass Child(pkg.base.Common): ...\n",
            "n.py": "import pkg.base as b\nclass Other(b.Common): ...\n",
        })
        self.assertEqual(self._models(model), {"pkg.base": ["Common"], "pkg.m": ["Child"], "pkg.n": ["Other"]})

    def test_decorators_imported_by_name_are_entry_points(self) -> None:
        model = self._model({
            "bare.py": "from click import command\n@command\ndef one(): ...\n",
            "called.py": "from click import command as cmd\n@cmd()\ndef two(): ...\n",
            "route.py": "from litestar import get\n@get('/x')\ndef three(): ...\n",
            "task.py": "from celery import shared_task as st\n@st\ndef four(): ...\n",
            "plain.py": "def command(f): return f\n@command\ndef nope(): ...\n",
        })
        found = {m.name.split(".")[-1]: m.entry_points for m in model.modules if m.entry_points}
        self.assertEqual(
            found,
            {"bare": ["cli one"], "called": ["cli two"], "route": ["route GET /x"], "task": ["task four"]},
        )

    def test_aliased_os_module_still_reads_env(self) -> None:
        model = self._model({"e.py": "import os as _os\na = _os.environ['A_VAR']\nb = _os.getenv('B_VAR')\n_os.environ['C_VAR'] = '1'\n"})
        self.assertEqual([v.name for v in model.env_vars], ["A_VAR", "B_VAR"])

    def test_exclusions_match_posix_paths_on_windows(self) -> None:
        from pathlib import PureWindowsPath
        from unittest import mock

        from sysatlas._reflection.parser import Module, ProjectGraph
        from sysatlas._reflection.reflection import Reflection

        root = "C:\\proj"
        graph = ProjectGraph(root=root, modules=[
            Module(name="p._reflection.parser", path="C:\\proj\\_reflection\\parser.py", package="p"),
            Module(name="p.keep", path="C:\\proj\\keep.py", package="p"),
        ])
        with mock.patch("sysatlas._reflection.reflection.Path", PureWindowsPath):
            kept = Reflection(graph, Hints()).exclude("_reflection/*")._kept_modules()
        self.assertEqual([m.name for m in kept], ["p.keep"])


class ScopesAndEvidence(unittest.TestCase):
    """Names resolve in the scope they are written in; groups, prefixes and facts need real evidence."""

    def _model(self, files: dict[str, str], hints: Hints | None = None, **kw):
        return _reflect(_tree(files), hints).to_atlas_model(**kw)

    def test_a_nested_import_does_not_change_module_level_bindings(self) -> None:
        model = self._model({
            "m.py": '''
                from pydantic import BaseModel as Schema
                from click import command as cmd

                class User(Schema): ...

                @cmd()
                def one(): ...

                def helper():
                    from collections import UserDict as Schema
                    from other import thing as cmd
                    return Schema, cmd
            ''',
        })
        m = next(x for x in model.modules if x.name == "pkg.m")
        self.assertEqual(m.models, ["User"])
        self.assertEqual(m.entry_points, ["cli one"])

    def test_a_nested_import_applies_inside_its_own_scope(self) -> None:
        model = self._model({
            "m.py": '''
                import click

                def build():
                    from click import command as c2

                    @c2
                    def inner(): ...
                    return inner
            ''',
        })
        self.assertEqual(next(x for x in model.modules if x.name == "pkg.m").entry_points, ["cli inner"])

    def test_gap_output_is_bounded_per_module(self) -> None:
        body = "\n".join(f"def f{i}(): ..." for i in range(300))
        text = self._model({"big.py": body}).to_markdown()
        line = next(ln for ln in text.splitlines() if ln.startswith("- Public symbols without a docstring"))
        self.assertIn("… +", line)
        self.assertLess(len(line), 600)

    def test_a_declared_group_is_never_split_by_size(self) -> None:
        files = {f"big/m{i}.py": "X = 1\n" for i in range(11)}
        hints = Hints(group={f"pkg.big.m{i}": "big" for i in range(11)})
        model = self._model(files, hints, intent={"components": {"big": {"purpose": "kept"}}})
        self.assertEqual([(c.name, c.module_count) for c in model.components], [("big", 11)])
        self.assertEqual(model.gaps.unknown_intent, [])
        inferred = self._model(files)
        self.assertGreater(len(inferred.components), 1)

    def test_import_examples_in_docstrings_do_not_rename_modules(self) -> None:
        base = Path(mkdtemp())
        root = base / "src"
        (root / "pkg").mkdir(parents=True)
        (root / "pkg" / "__init__.py").write_text("")
        (root / "pkg" / "a.py").write_text('"""Usage:\n\n    import src.example\n    from src.example import x\n"""\nfrom pkg import b\n')
        (root / "pkg" / "b.py").write_text("X = 1\n")
        graph = sysatlas.reflect(root, hints=Hints()).graph.by_name()
        self.assertEqual(sorted(graph), ["pkg", "pkg.a", "pkg.b"])
        self.assertIn("pkg.b", graph["pkg.a"].imports)

    def test_every_matching_abstract_base_is_recorded(self) -> None:
        model = self._model({
            "base.py": "from abc import ABC, abstractmethod\n"
                       "class P(ABC):\n    @abstractmethod\n    def f(self): ...\n"
                       "class Q(ABC):\n    @abstractmethod\n    def g(self): ...\n",
            "a.py": "from pkg.base import P, Q\nclass A(P, Q): ...\n",
            "b.py": "from pkg.base import Q\nclass B(Q): ...\n",
        })
        evidence = " ".join(_pattern(model, "Strategy").evidence)
        self.assertIn("Q (base): A (a), B (b)", evidence)
        a = next(x for x in model.modules if x.name == "pkg.a")
        self.assertEqual([(l.cls, l.base) for l in a.implements], [("A", "P"), ("A", "Q")])

    def test_implementer_lists_are_bounded(self) -> None:
        files = {"base.py": "from abc import ABC, abstractmethod\nclass S(ABC):\n    @abstractmethod\n    def f(self): ...\n"}
        files.update({f"i{n}.py": f"from pkg.base import S\nclass I{n}(S): ...\n" for n in range(30)})
        evidence = _pattern(self._model(files), "Strategy").evidence[0]
        self.assertIn("… +22", evidence)

    def test_environment_reads_by_keyword(self) -> None:
        model = self._model({
            "e.py": '''
                import os
                from os import getenv as g, environ as env
                a = os.getenv(key="A_KEY")
                b = os.environ.get(key="B_KEY")
                c = g(key="C_KEY", default="x")
                d = env.get(key="D_KEY")
                e = os.getenv(name_from_elsewhere)
                f = os.getenv(key=name_from_elsewhere)
            ''',
        })
        self.assertEqual([v.name for v in model.env_vars], ["A_KEY", "B_KEY", "C_KEY", "D_KEY"])

    def test_route_path_given_as_the_flask_rule_keyword(self) -> None:
        model = self._model({"w.py": "from flask import Flask\napp = Flask(__name__)\n@app.route(rule='/x')\ndef x(): ...\n"})
        self.assertEqual(next(x for x in model.modules if x.name == "pkg.w").entry_points, ["route /x"])


class RobustnessAndStatus(unittest.TestCase):
    """Key collisions, language, namespace evidence, env scopes, conformance status, hostile source files."""

    def _model(self, files: dict[str, str], hints: Hints | None = None, **kw):
        return _reflect(_tree(files), hints).to_atlas_model(**kw)

    def test_a_declared_group_named_like_an_inferred_subgroup_keeps_every_module(self) -> None:
        files = {f"big/sub/m{i}.py": "X = 1\n" for i in range(10)}
        files.update({"big/one.py": "X = 1\n", "extra.py": "X = 1\n"})
        model = self._model(files, Hints(group={"pkg.extra": "big.sub"}))
        names = [c.name for c in model.components]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(sum(c.module_count for c in model.components), model.module_count)
        self.assertEqual(model.module_count, 12)

    def test_a_python_package_named_crate_is_python(self) -> None:
        base = Path(mkdtemp())
        root = base / "crate"
        root.mkdir()
        (root / "__init__.py").write_text("")
        (root / "a.py").write_text("X = 1\n")
        self.assertEqual(sysatlas.reflect(root, hints=Hints()).to_atlas_model().language, "python")

    def test_an_import_that_may_be_the_stdlib_is_not_namespace_evidence(self) -> None:
        base = Path(mkdtemp())
        root = base / "code"  # also a standard-library module name
        (root / "pkg").mkdir(parents=True)
        (root / "pkg" / "__init__.py").write_text("")
        (root / "pkg" / "a.py").write_text("import code\nfrom code import interact\nfrom pkg import b\n")
        (root / "pkg" / "b.py").write_text("X = 1\n")
        graph = sysatlas.reflect(root, hints=Hints()).graph.by_name()
        self.assertEqual(sorted(graph), ["pkg", "pkg.a", "pkg.b"])
        self.assertIn("pkg.b", graph["pkg.a"].imports)

    def test_environment_reads_resolve_in_their_own_scope(self) -> None:
        model = self._model({
            "e.py": '''
                import os
                from os import environ as env, getenv as ge

                top = env["TOP"]

                def read_dict(env):
                    return env["PARAM_NOT_CONFIG"]

                def local_shadow():
                    env = {}
                    return env["LOCAL_NOT_CONFIG"]

                def helper():
                    from os import environ as e2
                    return e2["HELPER"]

                def other(e2):
                    return e2["OTHER_NOT_CONFIG"]

                def nested():
                    from os import getenv as g
                    def inner():
                        return g("NESTED")
                    return inner

                squares = [env["COMP_NOT_CONFIG"] for env in rows]
                pick = lambda env: env["LAMBDA_NOT_CONFIG"]
                again = lambda: env["LAMBDA_CLOSURE"]

                class C:
                    from os import environ as cls_env
                    attr = cls_env["CLASS_BODY"]
                    def method(self):
                        return cls_env["CLASS_NOT_VISIBLE"]

                walrus = ge("VIA_ALIAS")
            ''',
            "p.py": "import os.path\nx = os.environ['VIA_OS_PATH']\n",
        })
        self.assertEqual(
            [v.name for v in model.env_vars],
            ["CLASS_BODY", "HELPER", "LAMBDA_CLOSURE", "NESTED", "TOP", "VIA_ALIAS", "VIA_OS_PATH"],
        )

    def test_conformance_status_counts_a_missing_planned_component(self) -> None:
        spec = ArchitectureSpec.model_validate({"components": [
            {"name": "core", "modules": ["pkg.*"]},
            {"name": "worker", "modules": ["pkg.worker.*"]},
        ]})
        model = self._model({"a.py": "X = 1\n"}, Hints(architecture=spec))
        self.assertEqual(model.conformance.empty_components, ["worker"])
        self.assertFalse(model.conformance.ok)
        self.assertIn("departs from the spec", model.to_markdown())

    def test_modules_claimed_by_two_components_are_reported(self) -> None:
        spec = ArchitectureSpec.model_validate({"components": [
            {"name": "all", "modules": ["pkg.*"]},
            {"name": "special", "modules": ["pkg.a"]},
        ]})
        model = self._model({"a.py": "X = 1\n", "b.py": "X = 1\n"}, Hints(architecture=spec))
        self.assertEqual(model.conformance.ambiguous_modules, ["pkg.a"])
        self.assertIn("claimed by more than one spec component", model.to_markdown())

    def test_files_left_out_for_sharing_a_module_name_are_reported(self) -> None:
        root = _tree({"a.py": "class FromFile: ...\n", "a/__init__.py": "class FromPackage: ...\n"})
        model = sysatlas.reflect(root, hints=Hints()).exclude("__init__.py").to_atlas_model()
        self.assertEqual(len(model.shadowed_files), 1)
        self.assertIn("share a module name", model.to_markdown())
        clean = self._model({"a.py": "X = 1\n"})
        self.assertEqual(clean.shadowed_files, [])
        self.assertNotIn("share a module name", clean.to_markdown())

    def test_labels_stay_unique_when_renames_collide(self) -> None:
        # renaming a and b to the same name makes both fall back to their dotted names, which
        # equal the new name of c: the fallback itself must not produce a duplicate
        hints = Hints(rename={"pkg.a": "x", "pkg.b": "x", "pkg.c": "pkg.a", "pkg.d.a": "a"})
        model = self._model({"a.py": "X = 1\n", "b.py": "X = 1\n", "c.py": "X = 1\n", "d/a.py": "X = 1\n"}, hints)
        labels = [m.label for m in model.modules]
        self.assertEqual(len(labels), 4)
        self.assertEqual(len(labels), len(set(labels)))

    def test_a_source_file_nested_too_deep_does_not_abort_the_scan(self) -> None:
        files = {"deep.py": "class Deep: ...\nx = " + "+".join(["1"] * 6000) + "\n", "ok.py": "class Ok: ...\n"}
        model = self._model(files)
        by = {m.name.split(".")[-1]: m for m in model.modules}
        self.assertEqual(by["ok"].classes, ["Ok"])
        self.assertTrue(by["deep"].classes == ["Deep"] or by["deep"].unparsed)

    def test_a_byte_order_mark_and_a_coding_declaration_do_not_hide_symbols(self) -> None:
        root = _tree({})
        (root / "bom.py").write_bytes(b"\xef\xbb\xbfclass FromBom: ...\n")
        (root / "latin.py").write_bytes(b"# -*- coding: latin-1 -*-\nname = '\xe9'\nclass Latin: ...\n")
        by = {m.name.split(".")[-1]: m for m in _reflect(root).to_atlas_model().modules}
        self.assertEqual((by["bom"].classes, by["bom"].unparsed), (["FromBom"], False))
        self.assertEqual((by["latin"].classes, by["latin"].unparsed), (["Latin"], False))


    def test_environment_scope_edge_cases(self) -> None:
        model = self._model({
            "e.py": """
                import os
                from os import environ
                from typing import TYPE_CHECKING

                def walrus():
                    [(environ := {}) for _ in range(1)]
                    return environ["WALRUS_NOT_CONFIG"]

                def first_iterable():
                    return [k for environ in environ["FIRST_ITERABLE"]]

                class C:
                    from os import environ as e
                    f = lambda self: e["LAMBDA_IN_CLASS_NOT_VISIBLE"]
                    g = [e["COMP_IN_CLASS_NOT_VISIBLE"] for _ in range(1)]
                    h = [x for x in e["COMP_FIRST_ITERABLE_IN_CLASS"]]

                def init():
                    global np_env
                    from os import environ as np_env

                def later():
                    return np_env["GLOBAL_IMPORT"]

                if TYPE_CHECKING:
                    x = os.environ["TYPE_ONLY_NOT_CONFIG"]

                def annotated(a: os.environ["ANNOTATION"]) -> os.environ["RETURN"]: ...
            """,
        })
        self.assertEqual(
            [v.name for v in model.env_vars],
            ["ANNOTATION", "COMP_FIRST_ITERABLE_IN_CLASS", "FIRST_ITERABLE", "GLOBAL_IMPORT", "RETURN"],
        )

    def test_a_class_level_import_reaches_its_methods_decorators_only(self) -> None:
        model = self._model({
            "c.py": """
                import click

                class C:
                    from click import command as cmd

                    @cmd()
                    def method(self):
                        @cmd()
                        def inner(): ...
                        return inner
            """,
        })
        self.assertEqual(next(m for m in model.modules if m.name == "pkg.c").entry_points, ["cli method"])

    def test_a_component_shadowed_by_an_earlier_one_is_reported_as_such(self) -> None:
        spec = ArchitectureSpec.model_validate({"components": [
            {"name": "all", "modules": ["pkg.*"]},
            {"name": "special", "modules": ["pkg.a"]},
        ]})
        c = self._model({"a.py": "X = 1\n", "b.py": "X = 1\n"}, Hints(architecture=spec)).conformance
        self.assertEqual((c.empty_components, c.shadowed_components), ([], ["special"]))
        self.assertFalse(c.ok)
        text = self._model({"a.py": "X = 1\n", "b.py": "X = 1\n"}, Hints(architecture=spec)).to_markdown()
        self.assertIn("an earlier component already owns", text)
        self.assertNotIn("match no module", text)

    def test_overlapping_components_are_precedence_not_a_departure(self) -> None:
        spec = ArchitectureSpec.model_validate({"components": [
            {"name": "specific", "modules": ["pkg.a"]},
            {"name": "rest", "modules": ["pkg.*"]},
        ]})
        root = _tree({"a.py": "X = 1\n", "b.py": "X = 1\n"})
        c = _reflect(root, Hints(architecture=spec)).to_atlas_model().conformance
        self.assertEqual((c.ambiguous_modules, c.shadowed_components, c.empty_components), (["pkg.a"], [], []))

    def test_the_package_wins_when_two_files_share_a_module_name(self) -> None:
        root = _tree({
            "a.py": "from pydantic import BaseModel\nclass FromFile(BaseModel): ...\n",
            "a/__init__.py": "from pydantic import BaseModel\nclass FromPackage(BaseModel): ...\nclass Other(BaseModel): ...\n",
        })
        model = sysatlas.reflect(root, hints=Hints()).exclude("__init__.py").to_atlas_model()
        kept = next(m for m in model.modules if m.name == "pkg.a")
        self.assertEqual((kept.classes, kept.models), (["FromPackage", "Other"], ["FromPackage", "Other"]))
        self.assertEqual(model.shadowed_files, ["a.py"])


class ShadowingAndNaming(unittest.TestCase):
    """A name a scope binds itself hides the inherited one; global and nonlocal resolve elsewhere; generated names stay unique."""

    def _model(self, files: dict[str, str], hints: Hints | None = None):
        return _reflect(_tree(files), hints).to_atlas_model()

    def _module(self, model, name: str):
        return next(m for m in model.modules if m.name == f"pkg.{name}")

    def test_a_generated_component_name_never_equals_an_existing_one(self) -> None:
        files = {"util/a.py": "X = 1\n", "util/b.py": "X = 1\n", "util.py": "X = 1\n", "x.py": "X = 1\n"}
        # `util` clashes (a group and a module); the module's qualified name is `util (pkg.util)`,
        # which a declared group may already use
        model = self._model(files, Hints(group={"pkg.x": "util (pkg.util)"}))
        names = [c.name for c in model.components]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(sum(c.module_count for c in model.components), model.module_count)
        self.assertIn("util (pkg.util)", names)

    def test_a_parameter_hides_an_inherited_import_alias(self) -> None:
        model = self._model({
            "f.py": """
                import click
                from click import command as cmd

                def build(cmd):
                    @cmd
                    def from_parameter(): ...
                    return from_parameter

                def uses_import():
                    @cmd
                    def from_import(): ...
                    return from_import
            """,
        })
        self.assertEqual(self._module(model, "f").entry_points, ["cli from_import"])

    def test_a_local_assignment_hides_an_inherited_import_alias(self) -> None:
        model = self._model({
            "f.py": """
                import click
                from click import command as cmd

                def build():
                    cmd = make_decorator()
                    @cmd
                    def from_local(): ...

                class C:
                    cmd = other
                    @cmd
                    def from_class_attribute(self): ...
            """,
        })
        self.assertEqual(self._module(model, "f").entry_points, [])

    def test_a_function_own_import_still_applies_and_a_global_import_reaches_the_module(self) -> None:
        model = self._model({
            "f.py": """
                import click

                def build(cmd):
                    from click import command as cmd

                    @cmd
                    def own_import(): ...

                def init():
                    global late
                    from click import command as late

                @late
                def after_global(): ...
            """,
        })
        self.assertEqual(self._module(model, "f").entry_points, ["cli after_global", "cli own_import"])

    def test_a_global_name_resolves_to_the_modules_alias_past_an_enclosing_parameter(self) -> None:
        model = self._model({
            "f.py": """
                import click
                from click import command as cmd

                def outer(cmd):
                    def inner():
                        global cmd
                        @cmd
                        def from_module(): ...
                    @cmd
                    def from_parameter(): ...
                    return inner, from_parameter
            """,
        })
        self.assertEqual(self._module(model, "f").entry_points, ["cli from_module"])

    def test_global_resolves_in_the_module_past_an_enclosing_parameter(self) -> None:
        model = self._model({
            "e.py": """
                from os import environ

                def outer(environ):
                    def inner():
                        global environ
                        return environ.get("TOKEN")
                    def shadowed():
                        return environ.get("PARAM_NOT_CONFIG")
                    return inner, shadowed
            """,
        })
        self.assertEqual([v.name for v in model.env_vars], ["TOKEN"])

    def test_nonlocal_resolves_in_the_enclosing_function(self) -> None:
        model = self._model({
            "e.py": """
                from os import environ

                def outer(environ):
                    def inner():
                        nonlocal environ
                        return environ["PARAM_NOT_CONFIG"]
                    return inner

                def outer2():
                    from os import environ as environ
                    def inner():
                        nonlocal environ
                        return environ["ENCLOSING_IMPORT"]
                    return inner
            """,
        })
        self.assertEqual([v.name for v in model.env_vars], ["ENCLOSING_IMPORT"])


class UnboundedSections(unittest.TestCase):
    """Every section of the Markdown stays bounded, however big the repo."""

    def _atlas(self) -> str:
        n = 120
        files = {"__init__.py": "__all__ = [" + ", ".join(f"'s{i}'" for i in range(200)) + "]\n"}
        for i in range(n):
            files[f"g{i}/m{i}.py"] = (
                "".join(f"from pkg.g{j} import m{j}\n" for j in range(i + 1, min(n, i + 40)))
                + f"import lib{i}\nfrom pydantic import BaseModel\nclass M{i}(BaseModel): ...\n"
            )
        for i in range(40):  # 40 separate two-module import cycles
            files[f"cyc{i}/a.py"] = f"from pkg.cyc{i} import b\n"
            files[f"cyc{i}/b.py"] = f"from pkg.cyc{i} import a\n"
        hints = Hints(
            layer={f"pkg.g{i}.m{i}": f"layer{i}" for i in range(n)},
            architecture=ArchitectureSpec.model_validate({
                "components": [
                    {"name": f"c{i}", "modules": [f"pkg.g{i}.m{i}"]} for i in range(n)
                ] + [{"name": f"empty{i}", "modules": [f"pkg.none{i}.*"]} for i in range(60)]
            }),
        )
        root = _tree(files)
        (root / "__init__.py").write_text(files["__init__.py"])
        intent = {
            "patterns": [{"name": f"P{i}", "description": "d", "components": [f"x{j}" for j in range(40)]} for i in range(60)],
        }
        return sysatlas.reflect(root, hints=hints).exclude("__init__.py").to_atlas(intent=intent)

    def test_every_section_is_bounded_and_says_what_it_left_out(self) -> None:
        text = self._atlas()
        sections = text.split("\n## ")[1:]
        self.assertGreater(len(sections), 10)
        for section in sections:
            title = section.split("\n", 1)[0]
            with self.subTest(section=title):
                self.assertLess(len(section.splitlines()), 260)
                self.assertLess(max(len(line) for line in section.splitlines()), 1500)
        self.assertLess(len(text), 120_000)
        for marker in ("more packages", "more_", "… +"):
            self.assertIn(marker, text)

    def test_omitted_counts_are_stated_for_each_capped_list(self) -> None:
        text = self._atlas()
        by_title = {s.split("\n", 1)[0]: s for s in text.split("\n## ")[1:]}
        self.assertIn("more packages", by_title["Packages"])
        self.assertIn("more_", by_title["Layers"])
        self.assertIn("more_", by_title["Import cycles"])
        self.assertIn("more_", by_title["Public API surface"])
        self.assertIn("more_", by_title["Component dependencies"])
        self.assertIn("more_", by_title["Spec conformance"])
        self.assertIn("more_", by_title["Architectural patterns"])
        self.assertIn("Other third-party libraries", by_title["External systems"])
        self.assertIn("… +", by_title["External systems"])


def _pattern(model, name: str):
    return next(c for c in model.pattern_candidates if c.name == name)


if __name__ == "__main__":
    unittest.main()
