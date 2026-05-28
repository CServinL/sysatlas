"""Regenerate all interactive HTML artefacts under docs/demos/html/.

Each demo .py uses `.show()`, which writes to /tmp. This script monkey-
patches `.show()` on the public builders (SystemMap, System, TreeMap)
to save to `docs/demos/html/<demo>.html` instead, then runs each demo
via runpy so its module-top code executes unchanged. Special-cases
`trace_matrix.py` because it calls `.save()` and `.save_trace_matrix()`
to /tmp paths — we redirect those too.

Run from repo root:
    python scripts/regen_demos.py
"""
from __future__ import annotations

import runpy
from pathlib import Path

from sysatlas import SequenceMap, SystemMap, System, TreeMap

REPO = Path(__file__).resolve().parents[1]
DEMOS = REPO / "docs" / "demos"
OUT = DEMOS / "html"
OUT.mkdir(exist_ok=True)


def _redirect(cls, target: Path) -> None:
    def show(self, debug=False, viewer="cdn"):
        self.save(str(target), viewer=viewer)
    cls.show = show


def run(demo: str) -> None:
    target = OUT / f"{demo}.html"
    _redirect(SystemMap, target)
    _redirect(System, target)
    _redirect(TreeMap, target)
    _redirect(SequenceMap, target)

    if demo == "trace_matrix":
        # This demo saves two artefacts via System.save / save_trace_matrix.
        real_save   = System.save
        real_matrix = System.save_trace_matrix
        diagram_path = OUT / "trace_matrix.html"
        matrix_path  = OUT / "trace_matrix_table.html"
        def sys_save(self, path, viewer="cdn"):
            real_save(self, str(diagram_path), viewer=viewer)
        def matrix_save(self, path, title=None):
            real_matrix(self, str(matrix_path), title=title)
        System.save = sys_save
        System.save_trace_matrix = matrix_save
        runpy.run_path(str(DEMOS / "trace_matrix.py"), run_name="__main__")
        System.save = real_save
        System.save_trace_matrix = real_matrix
        print(f"  → {diagram_path.relative_to(REPO)}")
        print(f"  → {matrix_path.relative_to(REPO)}")
        return

    runpy.run_path(str(DEMOS / f"{demo}.py"), run_name="__main__")
    print(f"  → {target.relative_to(REPO)}")


def main() -> None:
    demos = [p.stem for p in sorted(DEMOS.glob("*.py"))]
    for d in demos:
        print(f"[regen] {d}")
        run(d)


if __name__ == "__main__":
    main()
