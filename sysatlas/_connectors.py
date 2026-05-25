from __future__ import annotations

LONG_LAYER_THRESHOLD = 3   # edges spanning >= this many ranks become connectors


def classify_edges(
    edges: list[dict],
    rank: dict[str, int],
) -> tuple[list[dict], list[dict]]:
    """Split edges into (direct, connector_pairs).

    direct: regular edges to be routed normally.
    connector_pairs: edges that should be drawn as two off-page connector glyphs
                     instead of a single long line.
    """
    direct: list[dict] = []
    connectors: list[dict] = []
    for e in edges:
        s, t = e["source"], e["target"]
        if s not in rank or t not in rank:
            direct.append(e)
            continue
        span = abs(rank[t] - rank[s])
        if span >= LONG_LAYER_THRESHOLD:
            connectors.append(e)
        else:
            direct.append(e)
    return direct, connectors
