"""Render a trace link set as an HTML matrix (sources × targets).

Complementary to the dashed-connector view: useful for audit-style
analysis ("what realizes / depends_on / satisfies what?") and for spotting
gaps (rows or columns that should have links but don't).
"""
from __future__ import annotations

from sysatlas._ontology.trace import TraceLink

_KIND_ABBR = {
    "realizes":      "Rz",
    "implements":    "Im",
    "refines":       "Rf",
    "satisfies":     "Sa",
    "represents":    "Rp",
    "documents":     "Dc",
    "tested_by":     "Tb",
    "derives_from":  "Df",
    "depends_on":    "Dp",
    "describes":     "Ds",
}

_KIND_COLOR = {
    "realizes":      "#3b82f6",
    "implements":    "#0ea5e9",
    "refines":       "#10b981",
    "satisfies":     "#84cc16",
    "represents":    "#a855f7",
    "documents":     "#f97316",
    "tested_by":     "#ef4444",
    "derives_from":  "#64748b",
    "depends_on":    "#9333ea",
    "describes":     "#f59e0b",
}


def render_trace_matrix(links: list[TraceLink], title: str = "Trace Matrix") -> str:
    """Build an HTML matrix from a list of trace links.

    Rows are sources, columns are targets, cells show the abbreviated kind
    in a coloured tag. Empty cells are blank. A legend at the bottom expands
    the abbreviations.
    """
    sources = sorted({str(l.source) for l in links})
    targets = sorted({str(l.target) for l in links})

    by_pair: dict[tuple[str, str], list[TraceLink]] = {}
    for l in links:
        by_pair.setdefault((str(l.source), str(l.target)), []).append(l)

    header_cells = "".join(
        f'<th>{_escape(t)}</th>' for t in targets
    )
    rows_html = []
    for s in sources:
        cells = []
        for t in targets:
            pair = by_pair.get((s, t))
            if not pair:
                cells.append('<td></td>')
                continue
            tags = "".join(_tag(l.kind, l.note) for l in pair)
            cells.append(f'<td>{tags}</td>')
        rows_html.append(f'<tr><th>{_escape(s)}</th>{"".join(cells)}</tr>')

    legend = "".join(
        f'<span class="lg" style="background:{c}">{_KIND_ABBR[k]}</span> {k}'
        for k, c in _KIND_COLOR.items()
    )

    return _SHELL.format(
        title=_escape(title),
        header=header_cells,
        rows="\n".join(rows_html),
        legend=legend,
        n_links=len(links),
        n_sources=len(sources),
        n_targets=len(targets),
    )


def _tag(kind: str, note: str | None) -> str:
    abbr = _KIND_ABBR.get(kind, kind[:2])
    color = _KIND_COLOR.get(kind, "#6b7280")
    title_attr = f' title="{_escape(note)}"' if note else f' title="{kind}"'
    return f'<span class="tag" style="background:{color}"{title_attr}>{abbr}</span>'


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


_SHELL = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: sans-serif; margin: 24px; background: #f8fafc; color: #111827; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .meta {{ color: #6b7280; font-size: 13px; margin-bottom: 16px; }}
  table {{ border-collapse: collapse; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
  th, td {{ border: 1px solid #e5e7eb; padding: 6px 10px; font-size: 12px; text-align: left; vertical-align: middle; }}
  th {{ background: #f3f4f6; font-weight: 600; white-space: nowrap; }}
  td {{ min-width: 44px; }}
  .tag {{ display: inline-block; color: #fff; font-size: 10px; font-weight: 700;
          padding: 2px 5px; border-radius: 4px; margin: 1px; }}
  .legend {{ margin-top: 18px; font-size: 12px; color: #374151; }}
  .lg {{ display: inline-block; color: #fff; font-size: 10px; font-weight: 700;
         padding: 2px 5px; border-radius: 4px; margin: 0 4px 0 12px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta">{n_links} links — {n_sources} sources × {n_targets} targets</div>
<table>
  <thead><tr><th></th>{header}</tr></thead>
  <tbody>
{rows}
  </tbody>
</table>
<div class="legend">{legend}</div>
</body>
</html>"""
