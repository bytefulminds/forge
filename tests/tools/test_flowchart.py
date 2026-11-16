from __future__ import annotations

import pytest

from forge.tools.markdown_tool import flowchart as fc


def test_round_trip_keeps_shapes_labels_edges_and_positions() -> None:
    chart = fc.Flowchart("LR")
    chart.nodes += [
        fc.Node("A", "Start", "stadium", 0, 0),
        fc.Node("B", "Valid? (yes/no)", "diamond", 200, 10),
        fc.Node("C", 'Store "it"', "database", 400, -50),
    ]
    chart.edges += [
        fc.Edge("A", "B"),
        fc.Edge("B", "C", "yes", "thick"),
        fc.Edge("B", "A", "", "dotted"),
    ]
    code = fc.to_mermaid(chart)
    assert code.startswith("flowchart LR\n")
    assert '    B{"Valid? (yes/no)"}' in code and "B ==>|yes| C" in code
    again = fc.parse(code)
    assert again == chart


def test_reads_common_hand_written_flowcharts() -> None:
    chart = fc.parse(
        "graph TB\n  S[Sensors] -->|MQTT| C(Collector) --> V{Valid?}\n"
        "  V -- yes --> D[(readings.csv)]\n  V -.-> L[Error log];\n  %% a comment\n"
    )
    assert chart.direction == "TD"
    assert [(n.id, n.shape) for n in chart.nodes] == [
        ("S", "rect"), ("C", "round"), ("V", "diamond"), ("D", "database"), ("L", "rect"),
    ]  # fmt: skip
    assert [(e.source, e.target, e.label, e.style) for e in chart.edges] == [
        ("S", "C", "MQTT", "arrow"),
        ("C", "V", "", "arrow"),
        ("V", "D", "yes", "arrow"),
        ("V", "L", "", "dotted"),
    ]
    # No stored layout: placed in layers along the flow, top to bottom.
    ys = {n.id: n.y for n in chart.nodes}
    assert ys["S"] < ys["C"] < ys["V"] < ys["D"] == ys["L"]


@pytest.mark.parametrize(
    "code",
    [
        "sequenceDiagram\n  A->>B: hi\n",
        "flowchart TD\n  subgraph one\n  A-->B\n  end\n",
        "flowchart TD\n  A & B --> C\n",
        "flowchart TD\n  A[open\n",
        "",
    ],
)
def test_refuses_what_it_cannot_draw(code: str) -> None:
    with pytest.raises(fc.FlowchartError):
        fc.parse(code)


def test_block_at_finds_the_mermaid_fence_around_the_caret() -> None:
    lines = ["# x", "```mermaid", "flowchart TD", "A-->B", "```", "", "```py", "x", "```"]
    assert fc.block_at(lines, 3) == (1, 4)
    assert fc.block_at(lines, 7) is None
    assert fc.block_at(lines, 0) is None


def test_new_ids() -> None:
    chart = fc.Flowchart(nodes=[fc.Node("A", "a"), fc.Node("B", "b")])
    assert chart.new_id() == "C"


def test_custom_box_sizes_round_trip() -> None:
    chart = fc.Flowchart("TD", [fc.Node("A", "Big", "rect", 10, 20, 240, 90), fc.Node("B", "x")])
    again = fc.parse(fc.to_mermaid(chart))
    a, b = again.node("A"), again.node("B")
    assert a is not None and (a.w, a.h) == (240, 90)
    assert b is not None and (b.w, b.h) == (0, 0)  # sized to fit its text
