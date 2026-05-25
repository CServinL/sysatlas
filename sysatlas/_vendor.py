from __future__ import annotations

import urllib.request
from pathlib import Path

_VENDOR_DIR = Path.home() / ".sysatlas" / "vendor"
_VIEWER_URLS = [
    "https://cdn.jsdelivr.net/npm/@jgraph/drawio/src/main/webapp/js/viewer-static.min.js",
    "https://unpkg.com/@jgraph/drawio/src/main/webapp/js/viewer-static.min.js",
    "https://app.diagrams.net/js/viewer-static.min.js",
]
VIEWER_CDN = _VIEWER_URLS[0]
_VIEWER_PATH = _VENDOR_DIR / "viewer-static.min.js"


def viewer_js() -> str:
    """Return viewer-static.min.js content, downloading it on first use."""
    if not _VIEWER_PATH.exists():
        _download()
    return _VIEWER_PATH.read_text(encoding="utf-8")


def _download() -> None:
    _VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    print(f"sysatlas: downloading draw.io viewer → {_VIEWER_PATH}")
    for url in _VIEWER_URLS:
        try:
            urllib.request.urlretrieve(url, _VIEWER_PATH)
            print("sysatlas: done")
            return
        except Exception:
            continue
    raise RuntimeError(
        "Could not download draw.io viewer. "
        "Copy viewer-static.min.js manually to: " + str(_VIEWER_PATH)
    )
