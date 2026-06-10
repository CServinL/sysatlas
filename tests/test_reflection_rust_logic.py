"""Unit tests for the Rust tree-sitter scanner (parser_rust.py)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sysatlas._reflection.parser_rust import _collect, _module_name, _resolve, scan_rust


# ---------------------------------------------------------------------------
# _module_name
# ---------------------------------------------------------------------------

class ModuleNamingTests(unittest.TestCase):
    def _name(self, rel: str) -> str:
        src = Path("/fake/src")
        return _module_name(src / rel, src)

    def test_main_rs(self) -> None:
        self.assertEqual(self._name("main.rs"), "crate")

    def test_lib_rs(self) -> None:
        self.assertEqual(self._name("lib.rs"), "crate")

    def test_top_level_module(self) -> None:
        self.assertEqual(self._name("foo.rs"), "crate.foo")

    def test_nested_module(self) -> None:
        self.assertEqual(self._name("foo/bar.rs"), "crate.foo.bar")

    def test_mod_rs_collapses(self) -> None:
        self.assertEqual(self._name("foo/mod.rs"), "crate.foo")

    def test_deep_mod_rs(self) -> None:
        self.assertEqual(self._name("foo/bar/mod.rs"), "crate.foo.bar")


# ---------------------------------------------------------------------------
# _collect (use tree node → raw :: paths)
# ---------------------------------------------------------------------------

def _parse_use(src: bytes):
    """Parse a single `use ...;` statement and return the use-tree child node."""
    import tree_sitter_rust as tsrust
    from tree_sitter import Language, Parser
    tree = Parser(Language(tsrust.language())).parse(src)
    ud = tree.root_node.children[0]   # use_declaration
    return next(c for c in ud.children if c.type not in ("use", ";"))


class CollectTests(unittest.TestCase):
    def _paths(self, src: bytes) -> list[str]:
        return sorted(_collect(_parse_use(src)))

    def test_simple_scoped(self) -> None:
        self.assertIn("crate::foo::Bar", self._paths(b"use crate::foo::Bar;"))

    def test_use_list(self) -> None:
        paths = self._paths(b"use crate::foo::{Bar, Baz};")
        self.assertIn("crate::foo::Bar", paths)
        self.assertIn("crate::foo::Baz", paths)

    def test_wildcard_returns_prefix(self) -> None:
        paths = self._paths(b"use crate::foo::*;")
        self.assertIn("crate::foo", paths)

    def test_use_as_clause(self) -> None:
        paths = self._paths(b"use crate::foo::Bar as B;")
        self.assertIn("crate::foo::Bar", paths)

    def test_self_relative(self) -> None:
        paths = self._paths(b"use self::bar;")
        self.assertIn("self::bar", paths)

    def test_super_relative(self) -> None:
        paths = self._paths(b"use super::baz::Thing as T;")
        self.assertIn("super::baz::Thing", paths)


# ---------------------------------------------------------------------------
# _resolve
# ---------------------------------------------------------------------------

class ResolveTests(unittest.TestCase):
    IN_TREE = {"crate", "crate.foo", "crate.foo.bar", "crate.foo.baz", "crate.baz"}

    def test_crate_path_resolved(self) -> None:
        r = _resolve("crate::foo::bar::Struct", "crate.main", self.IN_TREE)
        self.assertEqual(r, "crate.foo.bar")

    def test_crate_itself(self) -> None:
        r = _resolve("crate::foo", "crate.baz", self.IN_TREE)
        self.assertEqual(r, "crate.foo")

    def test_self_resolved(self) -> None:
        r = _resolve("self::bar", "crate.foo", self.IN_TREE)
        self.assertEqual(r, "crate.foo.bar")

    def test_super_resolved(self) -> None:
        # super from crate.foo.bar → parent is crate.foo → super::baz → crate.foo.baz
        r = _resolve("super::baz", "crate.foo.bar", self.IN_TREE)
        self.assertEqual(r, "crate.foo.baz")

    def test_external_crate_returns_none(self) -> None:
        r = _resolve("std::collections::HashMap", "crate.foo", self.IN_TREE)
        self.assertIsNone(r)

    def test_self_path_walks_to_parent(self) -> None:
        # use crate::foo::bar from within crate.foo.bar → self filtered,
        # resolver walks up to closest in-tree ancestor (crate.foo)
        r = _resolve("crate::foo::bar", "crate.foo.bar", self.IN_TREE)
        self.assertEqual(r, "crate.foo")


# ---------------------------------------------------------------------------
# scan_rust integration
# ---------------------------------------------------------------------------

_MAIN_RS = b"""\
mod utils;
mod network;

use crate::utils::helper;
use crate::network::Client;

fn main() {}
"""

_UTILS_RS = b"""\
pub fn helper() {}
"""

_NETWORK_RS = b"""\
use crate::utils::helper;

pub struct Client;
"""


class ScanRustTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        src = Path(self._tmp.name) / "src"
        src.mkdir()
        (src / "main.rs").write_bytes(_MAIN_RS)
        (src / "utils.rs").write_bytes(_UTILS_RS)
        (src / "network.rs").write_bytes(_NETWORK_RS)
        self.graph = scan_rust(self._tmp.name)
        self.by_name = self.graph.by_name()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_modules_discovered(self) -> None:
        names = set(self.by_name)
        self.assertIn("crate", names)
        self.assertIn("crate.utils", names)
        self.assertIn("crate.network", names)

    def test_main_imports_utils_and_network(self) -> None:
        main = self.by_name["crate"]
        self.assertIn("crate.utils", main.imports)
        self.assertIn("crate.network", main.imports)

    def test_network_imports_utils(self) -> None:
        net = self.by_name["crate.network"]
        self.assertIn("crate.utils", net.imports)

    def test_utils_has_no_in_tree_imports(self) -> None:
        utils = self.by_name["crate.utils"]
        self.assertEqual(utils.imports, [])

    def test_no_self_import(self) -> None:
        for m in self.graph.modules:
            self.assertNotIn(m.name, m.imports)

    def test_package_is_crate(self) -> None:
        for m in self.graph.modules:
            self.assertEqual(m.package, "crate")

    def test_src_root_recorded(self) -> None:
        self.assertTrue(self.graph.root.endswith("src"))


if __name__ == "__main__":
    unittest.main()
