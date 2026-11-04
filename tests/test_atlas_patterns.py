"""Pattern candidates: structural detectors in the atlas, each with a lookalike that must not fire."""
from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

import sysatlas
from sysatlas._reflection.reflection import Hints


def _tree(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp()) / "pkg"
    root.mkdir()
    (root / "__init__.py").write_text("")
    for name, body in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(body))
    return root


def _model(files: dict[str, str]):
    return sysatlas.reflect(_tree(files), hints=Hints()).exclude("__init__.py", "*/__init__.py").to_atlas_model()


def _names(model) -> list[str]:
    return [c.name for c in model.pattern_candidates]


def _cand(model, name: str):
    return next(c for c in model.pattern_candidates if c.name == name)


class Interfaces(unittest.TestCase):
    BASE = "from abc import ABC, abstractmethod\nclass Source(ABC):\n    @abstractmethod\n    def fetch(self): ...\n"

    def test_adapters_over_external_systems(self) -> None:
        model = _model({
            "base.py": self.BASE,
            "a.py": "import requests\nfrom pkg.base import Source\nclass A(Source):\n    def fetch(self): ...\n",
            "b.py": "import psycopg2\nfrom pkg.base import Source\nclass B(Source):\n    def fetch(self): ...\n",
        })
        self.assertEqual(_names(model), ["Ports and adapters"])
        ev = " ".join(_cand(model, "Ports and adapters").evidence)
        self.assertIn("A (a)", ev)
        self.assertIn("B (b)", ev)

    def test_plain_implementations_are_a_strategy(self) -> None:
        model = _model({
            "base.py": self.BASE,
            "a.py": "from pkg.base import Source\nclass A(Source):\n    def fetch(self): ...\n",
            "b.py": "from pkg import base\nclass B(base.Source):\n    def fetch(self): ...\n",
        })
        self.assertEqual(_names(model), ["Strategy"])

    def test_one_implementation_is_not_enough(self) -> None:
        model = _model({
            "base.py": self.BASE,
            "a.py": "from pkg.base import Source\nclass A(Source):\n    def fetch(self): ...\n",
        })
        self.assertEqual(_names(model), [])

    def test_concrete_base_with_subclasses_is_not_an_interface(self) -> None:
        model = _model({
            "base.py": "class Source:\n    def fetch(self): ...\n",
            "a.py": "from pkg.base import Source\nclass A(Source): ...\n",
            "b.py": "from pkg.base import Source\nclass B(Source): ...\n",
        })
        self.assertEqual(_names(model), [])

    def test_protocol_and_abstractmethod_without_abc_count_as_abstract(self) -> None:
        model = _model({
            "base.py": "from typing import Protocol\nclass P(Protocol):\n    def run(self): ...\n"
                       "import abc\nclass Q:\n    @abc.abstractmethod\n    def go(self): ...\n",
            "a.py": "from pkg.base import P, Q\nclass A(P): ...\nclass C(Q): ...\n",
            "b.py": "from pkg.base import P, Q\nclass B(P): ...\nclass D(Q): ...\n",
        })
        ev = " ".join(_cand(model, "Strategy").evidence)
        self.assertIn("P (base)", ev)
        self.assertIn("Q (base)", ev)


class FluentBuilder(unittest.TestCase):
    def test_chained_methods_are_found(self) -> None:
        model = _model({
            "b.py": '''
                class Builder:
                    def a(self): return self
                    def b(self): return self
                    def c(self):
                        x = 1
                        return self
                    def build(self): return 1
            ''',
        })
        self.assertEqual(_cand(model, "Fluent builder").evidence, ["Builder (b)"])

    def test_two_chained_methods_or_mixed_returns_do_not_count(self) -> None:
        model = _model({
            "b.py": '''
                class Two:
                    def a(self): return self
                    def b(self): return self
                class Mixed:
                    def a(self, f):
                        if f:
                            return self
                        return 1
                    def b(self, f):
                        if f:
                            return self
                        return None
                    def c(self): return self
                class Nested:
                    def a(self):
                        def inner(): return 1
                        return self
                    def b(self): return self
            ''',
        })
        self.assertNotIn("Fluent builder", _names(model))


class Structure(unittest.TestCase):
    CHAIN = {
        "a.py": "from pkg import b\n", "b.py": "from pkg import c\n",
        "c.py": "from pkg import d\n", "d.py": "X = 1\n",
    }

    def test_pipeline_chain_survives_component_merging(self) -> None:
        model = _model(self.CHAIN)
        self.assertEqual(len(model.components), 1)  # single-caller helpers merge into one
        self.assertIn("a -> b -> c -> d", _cand(model, "Pipeline").evidence)

    def test_layered_needs_three_tiers(self) -> None:
        hints = Hints(layer={"pkg.a": "edge", "pkg.b": "services", "pkg.c": "data", "pkg.d": "infra"})
        model = sysatlas.reflect(_tree(self.CHAIN), hints=hints).exclude("__init__.py").to_atlas_model()
        self.assertEqual(_cand(model, "Layered").evidence[0], "4 dependency tiers over 4 components")
        self.assertNotIn("Layered", _names(_model(self.CHAIN)))

    def test_a_branch_breaks_the_pipeline(self) -> None:
        model = _model({
            "a.py": "from pkg import b\n", "b.py": "from pkg import c, d\n",
            "c.py": "X = 1\n", "d.py": "X = 1\n",
        })
        self.assertNotIn("Pipeline", _names(model))

    def test_a_fan_in_hub_is_not_a_pipeline(self) -> None:
        model = _model({
            "a.py": "from pkg import hub\n", "b.py": "from pkg import hub\n",
            "c.py": "from pkg import hub\n", "hub.py": "X = 1\n",
        })
        self.assertNotIn("Pipeline", _names(model))

    def test_facade_needs_small_hub(self) -> None:
        small = {
            "api.py": "from pkg import a, b, c\n",
            "a.py": "X = 1\n", "b.py": "X = 1\n", "c.py": "X = 1\n",
            "u1.py": "from pkg import api\n", "u2.py": "from pkg import api\n", "u3.py": "from pkg import api\n",
        }
        self.assertIn("Facade", _names(_model(small)))
        big = dict(small)
        big["api.py"] = "from pkg import a, b, c\n" + "\n".join(f"def f{i}(): return {i}" for i in range(400))
        self.assertNotIn("Facade", _names(_model(big)))

    def test_plugin_registry_needs_users(self) -> None:
        files = {
            "reg.py": "REG = {}\ndef register(name): ...\n",
            "p1.py": "from pkg.reg import register\n", "p2.py": "from pkg.reg import register\n",
        }
        self.assertIn("Plugin registry", _names(_model(files)))
        del files["p2.py"]
        self.assertNotIn("Plugin registry", _names(_model(files)))


class Boundaries(unittest.TestCase):
    def test_repository_needs_a_datastore(self) -> None:
        with_db = _model({"repo.py": "import sqlite3\nclass UserRepository: ...\nclass Helper: ...\n"})
        self.assertEqual(_cand(with_db, "Repository").evidence, ["UserRepository (repo) over SQLite"])
        no_db = _model({"repo.py": "class UserRepository: ...\n"})
        self.assertNotIn("Repository", _names(no_db))

    def test_event_driven_by_publish_subscribe_pair_or_queue(self) -> None:
        bus = _model({"bus.py": "def publish(e): ...\ndef subscribe(h): ...\n"})
        self.assertIn("Event-driven", _names(bus))
        only_publish = _model({"bus.py": "def publish(e): ...\n"})
        self.assertNotIn("Event-driven", _names(only_publish))
        queue = _model({"w.py": "import pika\n"})
        self.assertIn("Event-driven", _names(queue))
        mail = _model({"m.py": "import smtplib\n"})
        self.assertNotIn("Event-driven", _names(mail))

    def test_client_server_and_commands(self) -> None:
        model = _model({
            "api.py": "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/a')\ndef a(): ...\n@app.post('/b')\ndef b(): ...\n",
            "cli.py": "import click\n@click.command()\ndef one(): ...\n@click.command()\ndef two(): ...\n",
        })
        self.assertEqual(_cand(model, "Client and server").evidence, ["2 routes in 1 component(s)"])
        self.assertEqual(_cand(model, "Command and task queue").evidence, ["2 cli entries"])
        single = _model({"cli.py": "import click\n@click.command()\ndef one(): ...\n"})
        self.assertNotIn("Command and task queue", _names(single))


class Rendering(unittest.TestCase):
    def test_section_lists_candidates_in_a_fixed_order(self) -> None:
        text = sysatlas.reflect("sysatlas").to_atlas(title="x")
        section = text.split("## Pattern candidates", 1)[1].split("\n## ", 1)[0]
        self.assertIn("not a verdict", section)
        self.assertIn("Fluent builder", section)
        self.assertLess(section.index("Layered"), section.index("Fluent builder"))

    def test_empty_section_says_so(self) -> None:
        text = sysatlas.reflect(_tree({"a.py": "X = 1\n"}), hints=Hints()).exclude("__init__.py").to_atlas()
        self.assertIn("_None found._", text.split("## Pattern candidates", 1)[1].split("\n## ", 1)[0])

    def test_candidates_are_in_the_json_model(self) -> None:
        model = sysatlas.reflect("sysatlas").to_atlas_model()
        self.assertIn("pattern_candidates", model.model_dump())


class ReviewRegressions(unittest.TestCase):
    """Defects found in review of the pattern detectors."""

    ABC_BASE = "from abc import ABC, abstractmethod\nclass Source(ABC):\n    @abstractmethod\n    def f(self): ...\n"

    def test_generic_protocol_and_subscripted_bases_are_linked(self) -> None:
        model = _model({
            "base.py": "from typing import Protocol, TypeVar\nT = TypeVar('T')\nclass Source(Protocol[T]):\n    def f(self): ...\n",
            "a.py": "import requests\nfrom pkg.base import Source\nclass A(Source[int]): ...\n",
            "b.py": "import psycopg2\nfrom pkg.base import Source\nclass B(Source[int]): ...\n",
        })
        self.assertEqual(_names(model), ["Ports and adapters"])

    def test_subscripted_model_base_still_resolves(self) -> None:
        model = _model({
            "base.py": "from pydantic import BaseModel\nfrom typing import Generic, TypeVar\nT = TypeVar('T')\nclass Page(BaseModel, Generic[T]): ...\n",
            "m.py": "from pkg.base import Page\nclass UserPage(Page[int]): ...\n",
        })
        self.assertEqual(next(m for m in model.modules if m.name == "pkg.m").models, ["UserPage"])

    def test_reexported_bases_resolve_for_interfaces_and_models(self) -> None:
        model = _model({
            "sub/__init__.py": "from pkg.sub.base import Source, Common\n",
            "sub/base.py": self.ABC_BASE + "from pydantic import BaseModel\nclass Common(BaseModel): ...\n",
            "a.py": "from pkg.sub import Source, Common\nclass A(Source): ...\nclass M(Common): ...\n",
            "b.py": "from pkg.sub import Source\nclass B(Source): ...\n",
        })
        self.assertEqual(_names(model), ["Strategy"])
        self.assertEqual(next(m for m in model.modules if m.name == "pkg.a").models, ["M"])

    def test_fluent_needs_a_final_return_self_and_instance_methods(self) -> None:
        model = _model({
            "x.py": '''
                class Conditional:
                    def a(self, f):
                        if f:
                            return self
                    def b(self, f):
                        if f:
                            return self
                    @property
                    def c(self): return self
            ''',
            "y.py": '''
                class Decorated:
                    @property
                    def a(self): return self
                    @staticmethod
                    def b(self): return self
                    @classmethod
                    def c(cls, self): return self
                    def d(self): return self
            ''',
        })
        self.assertNotIn("Fluent builder", _names(model))

    def test_adapters_need_distinct_modules(self) -> None:
        model = _model({
            "base.py": self.ABC_BASE,
            "b.py": "import psycopg2\nfrom pkg.base import Source\nclass B1(Source): ...\nclass B2(Source): ...\n",
        })
        self.assertNotIn("Ports and adapters", _names(model))
        self.assertEqual(_names(model), ["Strategy"])

    def test_event_driven_ignores_generic_helper_names(self) -> None:
        for body in ("def on(): ...\ndef emit(): ...\n", "def dispatch(): ...\ndef listen(): ...\n"):
            with self.subTest(body=body):
                self.assertNotIn("Event-driven", _names(_model({"ev.py": body})))
        bus = _model({"bus.py": "def publish(e): ...\ndef subscribe(h): ...\n"})
        self.assertIn("(names only)", " ".join(_cand(bus, "Event-driven").evidence))

    def test_layered_says_when_cycles_weaken_it(self) -> None:
        hints = Hints(layer={f"pkg.{n}": f"l{i}" for i, n in enumerate("abcde")})
        files = {"a.py": "from pkg import b\n", "b.py": "from pkg import c, a\n", "c.py": "from pkg import d\n",
                 "d.py": "from pkg import e\n", "e.py": "X = 1\n"}
        model = sysatlas.reflect(_tree(files), hints=hints).exclude("__init__.py").to_atlas_model()
        self.assertIn("weakens the layering", " ".join(_cand(model, "Layered").evidence))


if __name__ == "__main__":
    unittest.main()
