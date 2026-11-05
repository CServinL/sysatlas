"""Temporary directories for tests, removed when the test module finishes."""
from __future__ import annotations

import shutil
import tempfile
import unittest


def mkdtemp() -> str:
    path = tempfile.mkdtemp()
    unittest.addModuleCleanup(shutil.rmtree, path, True)
    return path
