import pytest
import netlyx


def test_add_component_and_connect():
    m = netlyx.SystemMap()
    m.add_component("A", layer="l1")
    m.add_component("B", layer="l2")
    m.connect("A", "B", label="calls")

    assert "A" in m._graph.nodes
    assert "B" in m._graph.nodes
    assert m._graph.has_edge("A", "B")
    assert m._graph["A"]["B"]["label"] == "calls"


def test_connect_auto_adds_nodes():
    m = netlyx.SystemMap()
    m.connect("X", "Y")
    assert "X" in m._graph.nodes
    assert "Y" in m._graph.nodes


def test_group_registration():
    m = netlyx.SystemMap()
    m.group("storage", color="#dcfce7")
    assert "storage" in m._groups
    assert m._groups["storage"]["color"] == "#dcfce7"


def test_layer_order_preserved():
    m = netlyx.SystemMap()
    m.add_component("A", layer="ingress")
    m.add_component("B", layer="services")
    m.add_component("C", layer="storage")
    assert m._layer_order == ["ingress", "services", "storage"]


def test_save_produces_html(tmp_path):
    m = netlyx.SystemMap(title="Test")
    m.add_component("A", layer="l1")
    m.add_component("B", layer="l2")
    m.connect("A", "B", label="->")

    out = tmp_path / "diagram.html"
    m.save(str(out))
    assert out.exists()
    content = out.read_text()
    assert "plotly" in content.lower()


def test_strategy_spring(tmp_path):
    m = netlyx.SystemMap(strategy="spring")
    m.add_component("A")
    m.add_component("B")
    m.connect("A", "B")
    out = tmp_path / "spring.html"
    m.save(str(out))
    assert out.exists()


def test_strategy_circular(tmp_path):
    m = netlyx.SystemMap(strategy="circular")
    for name in ["A", "B", "C", "D"]:
        m.add_component(name)
    m.connect("A", "B")
    m.connect("B", "C")
    out = tmp_path / "circular.html"
    m.save(str(out))
    assert out.exists()


def test_label_separate_from_name(tmp_path):
    m = netlyx.SystemMap()
    m.add_component("bbva", label="parsers/bbva.py\n(PDF → CSV)", layer="entrada")
    m.add_component("loader", label="db/loader.py", layer="storage")
    m.connect("bbva", "loader")
    out = tmp_path / "label.html"
    m.save(str(out))
    # Plotly unicode-escapes non-ASCII chars in the JSON payload;
    # decode before asserting so the test is resilient to encoding choices.
    content = out.read_text().encode().decode("unicode_escape")
    assert "parsers/bbva.py" in content
    assert "db/loader.py" in content


def test_metadata_in_hover(tmp_path):
    m = netlyx.SystemMap()
    m.add_component("API Gateway", layer="ingress", tech="Envoy", owner="platform")
    out = tmp_path / "meta.html"
    m.save(str(out))
    content = out.read_text()
    assert "Envoy" in content
    assert "platform" in content


def test_node_size_parameter(tmp_path):
    m = netlyx.SystemMap(node_size=80)
    m.add_component("A")
    m.add_component("B")
    m.connect("A", "B")
    out = tmp_path / "big.html"
    m.save(str(out))
    assert out.exists()


def test_edge_color_override(tmp_path):
    m = netlyx.SystemMap()
    m.add_component("A")
    m.add_component("B")
    m.connect("A", "B", color="#3b82f6")
    out = tmp_path / "color.html"
    m.save(str(out))
    assert "#3b82f6" in out.read_text()


def test_edge_style_options(tmp_path):
    m = netlyx.SystemMap()
    m.add_component("A")
    m.add_component("B")
    m.add_component("C")
    m.connect("A", "B", style="dashed")
    m.connect("A", "C", style="dotted")
    out = tmp_path / "styles.html"
    m.save(str(out))
    assert out.exists()


def test_chaining():
    m = (
        netlyx.SystemMap()
        .group("svc", color="#bbf7d0")
        .add_component("A", group="svc", layer="l1")
        .add_component("B", group="svc", layer="l2")
        .connect("A", "B")
    )
    assert "A" in m._graph.nodes
    assert m._graph.has_edge("A", "B")
