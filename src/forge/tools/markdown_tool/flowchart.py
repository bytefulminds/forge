"""Mermaid flowcharts as data (no Qt): what the diagram editor draws.

``to_mermaid`` writes a flowchart, with the node positions in a Mermaid
comment (``%% forge-layout: {...}``) so the drawing comes back the same
when the block is opened again. ``parse`` reads the common flowchart
syntax back: nodes in the usual shapes, edges with or without a label, and
chains such as ``A --> B --> C``. Subgraphs, styling and ``A & B`` lists
are not drawn; ``parse`` refuses them so nothing is lost by accident.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field

# Shape name -> (opening, closing) brackets.
SHAPES: dict[str, tuple[str, str]] = {
    "rect": ("[", "]"),
    "round": ("(", ")"),
    "stadium": ("([", "])"),
    "diamond": ("{", "}"),
    "circle": ("((", "))"),
    "database": ("[(", ")]"),
    "hexagon": ("{{", "}}"),
}
# Edge style -> arrow as written in Mermaid.
EDGES: dict[str, str] = {
    "arrow": "-->",
    "line": "---",
    "dotted": "-.->",
    "thick": "==>",
}
DIRECTIONS = ("TD", "LR", "BT", "RL")
LAYOUT_PREFIX = "%% forge-layout:"

_ID = re.compile(r"[A-Za-z_][\w]*")
# Longest openers first so "([" wins over "(".
_OPENERS = sorted(((o, name) for name, (o, _c) in SHAPES.items()), key=lambda p: -len(p[0]))
_ARROW = re.compile(
    r"\s*(?:"
    r"(?P<arrow>-\.->|-->|---|==>|-\.-|===)\s*(?:\|(?P<pipe>[^|]*)\|)?"
    r"|--\s+(?P<text>[^-][^>]*?)\s+-->"
    r"|==\s+(?P<thicktext>[^=][^>]*?)\s+==>"
    r")\s*"
)
_STYLE_OF = {"-->": "arrow", "---": "line", "-.->": "dotted", "-.-": "dotted", "==>": "thick",
             "===": "thick"}  # fmt: skip
_UNSUPPORTED = ("subgraph", "end", "style ", "classDef", "class ", "click ", "linkStyle")


class FlowchartError(ValueError):
    pass


@dataclass
class Node:
    id: str
    label: str
    shape: str = "rect"
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0  # 0: sized to fit the text
    h: float = 0.0


@dataclass
class Edge:
    source: str
    target: str
    label: str = ""
    style: str = "arrow"


@dataclass
class Flowchart:
    direction: str = "TD"
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def new_id(self) -> str:
        """A short unused node id: A, B, ... Z, A1, B1, ..."""
        used = {n.id for n in self.nodes}
        number = 0
        while True:
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                candidate = letter + (str(number) if number else "")
                if candidate not in used:
                    return candidate
            number += 1


# Writing ------------------------------------------------------------------------------


def _quote(label: str) -> str:
    """Labels with brackets, quotes or other syntax go in quotes."""
    if re.fullmatch(r"[\w .,:;!?'/+*-]*", label) and label.strip() == label and label:
        return label
    return '"' + label.replace('"', "#quot;") + '"'


def to_mermaid(chart: Flowchart) -> str:
    lines = [f"flowchart {chart.direction}"]
    for node in chart.nodes:
        opening, closing = SHAPES.get(node.shape, SHAPES["rect"])
        lines.append(f"    {node.id}{opening}{_quote(node.label)}{closing}")
    for edge in chart.edges:
        arrow = EDGES.get(edge.style, EDGES["arrow"])
        label = f"|{edge.label.replace('|', '/')}|" if edge.label else ""
        lines.append(f"    {edge.source} {arrow}{label} {edge.target}")
    layout = {
        n.id: [round(n.x), round(n.y)] + ([round(n.w), round(n.h)] if n.w and n.h else [])
        for n in chart.nodes
    }
    lines.append(f"    {LAYOUT_PREFIX} {json.dumps(layout, separators=(',', ':'))}")
    return "\n".join(lines) + "\n"


# Reading ------------------------------------------------------------------------------


def _read_label(text: str, pos: int, closing: str) -> tuple[str, int]:
    if text.startswith('"', pos):
        end = text.find('"', pos + 1)
        if end < 0:
            raise FlowchartError("a label has no closing quote")
        label = text[pos + 1 : end].replace("#quot;", '"')
        pos = end + 1
        if not text.startswith(closing, pos):
            raise FlowchartError(f"expected {closing} after a label")
        return label, pos + len(closing)
    end = text.find(closing, pos)
    if end < 0:
        raise FlowchartError(f"a node has no closing {closing}")
    return text[pos:end].strip(), end + len(closing)


def _read_node(text: str, pos: int, chart: Flowchart) -> tuple[str, int]:
    match = _ID.match(text, pos)
    if match is None:
        raise FlowchartError(f"expected a node at {text[pos : pos + 12]!r}")
    node_id = match.group(0)
    pos = match.end()
    for opening, shape in _OPENERS:
        if text.startswith(opening, pos):
            label, pos = _read_label(text, pos + len(opening), SHAPES[shape][1])
            existing = chart.node(node_id)
            if existing is None:
                chart.nodes.append(Node(node_id, label, shape))
            else:
                existing.label, existing.shape = label, shape
            break
    else:
        if chart.node(node_id) is None:
            chart.nodes.append(Node(node_id, node_id))
    return node_id, pos


def parse(code: str) -> Flowchart:
    """A Flowchart from Mermaid source; FlowchartError when Forge cannot draw it."""
    chart = Flowchart()
    layout: dict[str, object] = {}
    header_seen = False
    for raw in code.splitlines():
        line = raw.strip().rstrip(";")
        if not line:
            continue
        if line.startswith(LAYOUT_PREFIX):
            try:
                layout = json.loads(line[len(LAYOUT_PREFIX) :])
            except ValueError:
                layout = {}
            continue
        if line.startswith("%%"):
            continue
        if not header_seen:
            words = line.split()
            if words[0] not in ("flowchart", "graph"):
                raise FlowchartError(f"{words[0]} diagrams cannot be drawn, only flowcharts")
            direction = words[1].upper() if len(words) > 1 else "TD"
            chart.direction = "TD" if direction == "TB" else direction
            if chart.direction not in DIRECTIONS:
                raise FlowchartError(f"unknown direction {direction}")
            header_seen = True
            continue
        if line.startswith(_UNSUPPORTED) or line == "end":
            raise FlowchartError(f"{line.split()[0]} is not supported in the drawing")
        if "&" in line and '"' not in line:
            raise FlowchartError("node lists with & are not supported in the drawing")
        source, pos = _read_node(line, 0, chart)
        while pos < len(line):
            arrow = _ARROW.match(line, pos)
            if arrow is None:
                raise FlowchartError(f"cannot read {line[pos:]!r}")
            symbol = arrow.group("arrow") or ("==>" if arrow.group("thicktext") else "-->")
            label = arrow.group("pipe") or arrow.group("text") or arrow.group("thicktext") or ""
            target, pos = _read_node(line, arrow.end(), chart)
            chart.edges.append(Edge(source, target, label.strip(), _STYLE_OF.get(symbol, "arrow")))
            source = target
    if not header_seen:
        raise FlowchartError("empty diagram")
    if not isinstance(layout, dict):
        layout = {}
    missing = [n for n in chart.nodes if n.id not in layout]
    for node in chart.nodes:
        place = layout.get(node.id)
        if isinstance(place, list) and len(place) in (2, 4):
            node.x, node.y = float(place[0]), float(place[1])
            if len(place) == 4:
                node.w, node.h = float(place[2]), float(place[3])
    if missing:
        auto_layout(chart, only=missing if len(missing) < len(chart.nodes) else None)
    return chart


# Layout --------------------------------------------------------------------------------

LAYER_GAP = 130.0
NODE_GAP = 190.0


def auto_layout(chart: Flowchart, only: list[Node] | None = None) -> None:
    """Place nodes in layers along the flow (longest path from a start node)."""
    targets: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = defaultdict(int)
    for edge in chart.edges:
        if edge.source != edge.target:
            targets[edge.source].append(edge.target)
            incoming[edge.target] += 1
    depth: dict[str, int] = {}
    order = [n.id for n in chart.nodes]
    queue = [n for n in order if incoming[n] == 0] or order[:1]
    for start in queue:
        depth.setdefault(start, 0)
    visits = 0
    while queue and visits < len(order) * len(order) + 10:
        visits += 1
        current = queue.pop(0)
        for target in targets[current]:
            if depth.get(target, -1) < depth[current] + 1 and depth[current] + 1 < len(order):
                depth[target] = depth[current] + 1
                queue.append(target)
    for node_id in order:
        depth.setdefault(node_id, 0)
    layers: dict[int, list[str]] = defaultdict(list)
    for node_id in order:
        layers[depth[node_id]].append(node_id)
    horizontal = chart.direction in ("LR", "RL")
    reverse = chart.direction in ("BT", "RL")
    deepest = max(layers) if layers else 0
    moving = {n.id for n in only} if only is not None else None
    for layer, ids in layers.items():
        offset = (len(ids) - 1) / 2
        for index, node_id in enumerate(ids):
            node = chart.node(node_id)
            if node is None or (moving is not None and node_id not in moving):
                continue
            along = (deepest - layer if reverse else layer) * (
                NODE_GAP if horizontal else LAYER_GAP
            )
            across = (index - offset) * (LAYER_GAP if horizontal else NODE_GAP)
            node.x, node.y = (along, across) if horizontal else (across, along)


# Finding a block in Markdown --------------------------------------------------------


def block_at(lines: list[str], line: int) -> tuple[int, int] | None:
    """(first, last) line of the ```mermaid block around ``line``, fences included."""
    fence_start: int | None = None
    for index, text in enumerate(lines):
        stripped = text.strip()
        if fence_start is None and re.match(r"^(```|~~~)\s*mermaid\b", stripped):
            fence_start = index
        elif fence_start is not None and stripped in ("```", "~~~"):
            if fence_start <= line <= index:
                return fence_start, index
            fence_start = None
    return None
