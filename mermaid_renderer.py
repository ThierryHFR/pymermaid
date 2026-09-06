"""Small dependency-light Mermaid renderer written in Python.

Supporte actuellement :
  - flowchart TD/LR/RL/BT and graph TD/LR...
  - sequenceDiagram with messages, notes, and simple activations

The main API is MermaidRenderer.render(source) -> str (SVG).
"""

from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


@dataclass
class Node:
    ident: str
    label: str
    shape: str = "rect"
    x: float = 0
    y: float = 0

    @property
    def lines(self) -> list[str]:
        text = re.sub(r"<br\s*/?>", "\n", self.label, flags=re.I)
        result: list[str] = []
        for paragraph in text.splitlines() or [""]:
            current = ""
            for word in paragraph.split():
                if len(current) + len(word) + 1 <= 25:
                    current = f"{current} {word}".strip()
                else:
                    if current: result.append(current)
                    current = word
            if current: result.append(current)
        return result or [""]


@dataclass
class Edge:
    source: str
    target: str
    label: str = ""
    dashed: bool = False
    arrow: bool = True


@dataclass
class Participant:
    ident: str
    label: str
    x: float = 0


class MermaidRenderer:
    """Parse and render a practical Mermaid subset as SVG."""

    def __init__(self, *, font_family: str = "Arial, sans-serif") -> None:
        self.font_family = font_family

    def render(self, source: str) -> str:
        lines = [line.strip() for line in source.splitlines() if line.strip() and not line.strip().startswith("%%")]
        if not lines:
            raise ValueError("The Mermaid diagram is empty")
        kind = lines[0].split()[0].lower()
        if kind in {"flowchart", "graph"}:
            # Graphviz provides improved layout when installed. The Python
            # renderer remains available as a dependency-free fallback.
            if self._graphviz_executable():
                return self._render_flowchart_graphviz(lines)
            return self._render_flowchart(lines)
        if kind == "sequencediagram":
            return self._render_sequence(lines)
        raise ValueError(f"Unsupported Mermaid diagram type: {kind}")

    @staticmethod
    def _graphviz_executable() -> str | None:
        """Return the most portable Graphviz ``dot`` executable available.

        The packaged application carries its own Graphviz runtime.  It must be
        preferred over a system installation: otherwise the layout can change
        between machines (or Windows can silently fall back to the small
        Python layout when ``dot.exe`` is not on PATH).
        """
        executable_name = "dot.exe" if sys.platform == "win32" else "dot"
        candidates: list[Path] = []

        # PyInstaller's temporary extraction directory.
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            candidates.append(Path(bundle_dir) / "graphviz" / executable_name)

        # Allow source launches and custom package layouts to use an explicit
        # Graphviz installation without requiring a global PATH modification.
        graphviz_bin = os.environ.get("GRAPHVIZ_BIN")
        if graphviz_bin:
            candidates.append(Path(graphviz_bin) / executable_name)
        graphviz_root = os.environ.get("GRAPHVIZ_ROOT")
        if graphviz_root:
            candidates.append(Path(graphviz_root) / "bin" / executable_name)

        if sys.platform == "win32":
            program_files = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]
            for root in filter(None, program_files):
                candidates.append(Path(root) / "Graphviz" / "bin" / executable_name)

        # Finally use the system PATH (normal for Linux/macOS and useful for
        # developers who installed Graphviz in a non-standard Windows path).
        system_dot = shutil.which(executable_name)
        if system_dot:
            candidates.append(Path(system_dot))

        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return None

    def render_file(self, input_path: str, output_path: str) -> None:
        with open(input_path, encoding="utf-8") as stream:
            self.render_text_to_file(stream.read(), output_path)

    def render_text_to_file(self, source: str, output_path: str) -> None:
        svg = self.render(source)
        with open(output_path, "w", encoding="utf-8") as stream:
            stream.write(svg)

    def render_pdf(self, source: str, output_path: str) -> None:
        """Rend directement un diagramme en PDF via CairoSVG."""
        try:
            import cairosvg
        except ImportError as exc:
            raise RuntimeError("CairoSVG is required for PDF output: python3 -m pip install -r requirements.txt") from exc
        svg = self.render(source)
        cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=output_path)

    def _svg(self, width: int, height: int, content: str) -> str:
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><path d="M0,0 L10,3.5 L0,7 z" fill="#475569"/></marker></defs>
<rect width="100%" height="100%" fill="#ffffff"/>
<g font-family="{_esc(self.font_family)}" font-size="14">{content}</g></svg>'''

    def _render_flowchart(self, lines: list[str]) -> str:
        direction = lines[0].split()[1].upper() if len(lines[0].split()) > 1 else "TD"
        nodes: dict[str, Node] = {}
        edges: list[Edge] = []
        for line in lines[1:]:
            if line.startswith("subgraph") or line in {"end"}:
                continue
            match = re.search(r"(.+?)\s*(-->|---|-.->|==>|-\.->)\s*(.+)", line)
            if not match:
                self._node_from_text(line, nodes)
                continue
            left, operator, right = (part.strip() for part in match.groups())
            # Optional edge label: A -->|label| B
            label_match = re.search(r"\|([^|]+)\|", right)
            label = label_match.group(1).strip() if label_match else ""
            right = re.sub(r"\|[^|]+\|", "", right).strip()
            source = self._node_from_text(left, nodes)
            target = self._node_from_text(right, nodes)
            edges.append(Edge(source.ident, target.ident, label, dashed="." in operator, arrow=operator not in {"---"}))

        self._layout_flow(nodes, edges, direction)
        max_x = max((n.x for n in nodes.values()), default=0) + 220
        max_y = max((n.y for n in nodes.values()), default=0) + 100
        content: list[str] = []
        for edge in edges:
            a, b = nodes[edge.source], nodes[edge.target]
            x1, y1 = a.x + 90, a.y + 35
            x2, y2 = b.x + 90, b.y + 35
            attrs = 'stroke="#64748b" stroke-width="1.8" fill="none"'
            if edge.dashed:
                attrs += ' stroke-dasharray="6 4"'
            if edge.arrow:
                attrs += ' marker-end="url(#arrow)"'
            content.append(f'<path d="M{x1:g},{y1:g} L{x2:g},{y2:g}" {attrs}/>')
            if edge.label:
                content.append(f'<text x="{(x1+x2)/2:g}" y="{(y1+y2)/2-6:g}" text-anchor="middle" fill="#334155">{_esc(edge.label)}</text>')
        for node in nodes.values():
            fill = "#e0f2fe" if node.shape != "diamond" else "#fef3c7"
            if node.shape == "round":
                content.append(f'<rect x="{node.x:g}" y="{node.y:g}" width="140" height="50" rx="25" fill="{fill}" stroke="#0284c7"/>')
            elif node.shape == "diamond":
                content.append(f'<polygon points="{node.x+70:g},{node.y:g} {node.x+140:g},{node.y+25:g} {node.x+70:g},{node.y+50:g} {node.x:g},{node.y+25:g}" fill="{fill}" stroke="#d97706"/>')
            else:
                content.append(f'<rect x="{node.x:g}" y="{node.y:g}" width="140" height="50" rx="6" fill="{fill}" stroke="#0284c7"/>')
            lines_for_node = node.lines
            start_y = node.y + 35 - (len(lines_for_node) - 1) * 9
            for line_no, line in enumerate(lines_for_node):
                content.append(f'<text x="{node.x+90:g}" y="{start_y + line_no*18:g}" text-anchor="middle" fill="#0f172a">{_esc(line)}</text>')
        return self._svg(int(max_x), int(max_y), "".join(content))

    def _render_flowchart_graphviz(self, lines: list[str]) -> str:
        direction = lines[0].split()[1].upper() if len(lines[0].split()) > 1 else "TD"
        nodes: dict[str, Node] = {}
        edges: list[Edge] = []
        for line in lines[1:]:
            if line.startswith("subgraph") or line.lower() == "end":
                continue
            match = re.search(r"(.+?)\s*(-->|---|-.->|==>|-\.->)\s*(.+)", line)
            if not match:
                self._node_from_text(line, nodes)
                continue
            left, operator, right = (part.strip() for part in match.groups())
            label_match = re.search(r"\|([^|]+)\|", right)
            label = label_match.group(1).strip() if label_match else ""
            right = re.sub(r"\|[^|]+\|", "", right).strip()
            source = self._node_from_text(left, nodes)
            target = self._node_from_text(right, nodes)
            edges.append(Edge(source.ident, target.ident, label, dashed="." in operator, arrow=operator not in {"---"}))

        rankdir = {"TD": "TB", "BT": "BT", "LR": "LR", "RL": "RL"}.get(direction, "TB")
        dot: list[str] = [
            "digraph Mermaid {",
            f'  graph [rankdir={rankdir}, bgcolor="white", pad="0.25", nodesep="0.45", ranksep="0.75", splines=polyline, outputorder=edgesfirst];',
            '  node [fontname="Arial", fontsize=12, color="#0284c7", fontcolor="#0f172a", style="filled,rounded", fillcolor="#e0f2fe", margin="0.16,0.10"];',
            '  edge [fontname="Arial", fontsize=10, color="#64748b", fontcolor="#334155", penwidth=1.3, arrowsize=0.7];',
        ]
        for node in nodes.values():
            label = "\\n".join(node.lines)
            attrs = [f'label="{self._dot_quote(label)}"']
            if node.shape == "diamond":
                attrs += ['shape=diamond', 'fillcolor="#fef3c7"', 'color="#d97706"']
            elif node.shape == "round":
                attrs += ['shape=oval', 'fillcolor="#dcfce7"', 'color="#16a34a"']
            else:
                attrs += ['shape=box']
            dot.append(f'  "{self._dot_quote(node.ident)}" [{", ".join(attrs)}];')
        for edge in edges:
            attrs = []
            if edge.label: attrs.append(f'label="{self._dot_quote(edge.label)}"')
            if edge.dashed: attrs.append('style=dashed')
            if not edge.arrow: attrs.append('dir=none')
            dot.append(f'  "{self._dot_quote(edge.source)}" -> "{self._dot_quote(edge.target)}" [{", ".join(attrs)}];')
        dot.append("}")
        executable = self._graphviz_executable()
        if executable is None:
            raise RuntimeError("Graphviz dot executable is unavailable")
        environment = os.environ.copy()
        executable_path = Path(executable).resolve()
        graphviz_dir = executable_path.parent
        environment["PATH"] = f"{graphviz_dir}{os.pathsep}{environment.get('PATH', '')}"
        # Graphviz looks for its rendering plugins through GVBINDIR.  This is
        # required for the one-file Windows build, where the runtime is
        # extracted below _MEIPASS instead of installed system-wide.
        if getattr(sys, "_MEIPASS", None) and graphviz_dir.name.lower() == "graphviz":
            environment["GVBINDIR"] = str(graphviz_dir / "lib" / "graphviz")
            environment["GVDATADIR"] = str(graphviz_dir / "share" / "graphviz")
        try:
            result = subprocess.run([executable, "-Tsvg"], input="\n".join(dot), text=True, capture_output=True, check=True, env=environment)
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "").strip()
            message = f"Graphviz dot failed with exit code {exc.returncode}"
            if details:
                message += f": {details}"
            raise RuntimeError(message) from exc
        return result.stdout

    @staticmethod
    def _dot_quote(value: str) -> str:
        # Graphviz sequences such as ``\\n`` must remain interpretable
        # so labels can contain line breaks.
        return value.replace('"', '\\"')

    def _node_from_text(self, text: str, nodes: dict[str, Node]) -> Node:
        match = re.match(r"([\w-]+)\s*(?:([\[\(\{])(.+?)([\]\)\}]))?$", text.strip())
        if not match:
            ident, label, shape = text.strip(), text.strip(), "rect"
        else:
            ident = match.group(1)
            label = (match.group(3) or ident).strip().strip('"\'')
            opener = match.group(2)
            shape = "round" if opener == "(" else "diamond" if opener == "{" else "rect"
        node = nodes.get(ident)
        if node is None:
            node = nodes[ident] = Node(ident, label, shape)
        elif match and match.group(3):
            # A reference may appear before its complete definition:
            # A --> B followed by A[Label]. Enrich the existing node.
            node.label = label
            node.shape = shape
        return node

    def _layout_flow(self, nodes: dict[str, Node], edges: list[Edge], direction: str) -> None:
        order = list(nodes)
        incoming = {ident: 0 for ident in order}
        children = {ident: [] for ident in order}
        for edge in edges:
            if edge.source in children and edge.target in incoming:
                children[edge.source].append(edge.target)
                incoming[edge.target] += 1
        levels: dict[str, int] = {}
        queue = [ident for ident in order if incoming[ident] == 0]
        while queue:
            ident = queue.pop(0)
            for child in children[ident]:
                levels[child] = max(levels.get(child, 0), levels.get(ident, 0) + 1)
                incoming[child] -= 1
                if incoming[child] == 0: queue.append(child)
        for ident in order:
            levels.setdefault(ident, 0)
        grouped: dict[int, list[str]] = {}
        for ident in order: grouped.setdefault(levels[ident], []).append(ident)
        for ident in order:
            level = levels[ident]
            peers = grouped[level]
            index = peers.index(ident)
            x, y = index * 220, level * 120
            if direction in {"LR", "RL"}:
                x, y = level * 240, index * 120
                if direction == "RL": x = max(0, max(levels.values()) * 240 - x)
            elif direction == "BT":
                y = max(0, max(levels.values()) * 120 - y)
            nodes[ident].x, nodes[ident].y = x + 20, y + 20

    def _render_sequence(self, lines: list[str]) -> str:
        participants: dict[str, Participant] = {}
        messages: list[tuple[str, str, str, bool]] = []
        for line in lines[1:]:
            match = re.match(r"participant\s+(\w+)(?:\s+as\s+(.+))?", line, re.I)
            if match:
                ident, label = match.group(1), match.group(2) or match.group(1)
                participants.setdefault(ident, Participant(ident, label))
                continue
            match = re.match(r"(\w+)\s*(-?>>|-->>|->>|-->|-x|--x)\s*(\w+)\s*:\s*(.+)", line)
            if match:
                src, arrow, dst, label = match.groups()
                participants.setdefault(src, Participant(src, src)); participants.setdefault(dst, Participant(dst, dst))
                messages.append((src, dst, label, arrow.startswith("--")))
        gap, left, top = 180, 40, 30
        for i, participant in enumerate(participants.values()): participant.x = left + i * gap
        height = top + 75 + len(messages) * 65 + 30
        content: list[str] = []
        for participant in participants.values():
            x = participant.x
            content.append(f'<rect x="{x-55:g}" y="{top:g}" width="110" height="38" rx="6" fill="#dbeafe" stroke="#2563eb"/><text x="{x:g}" y="{top+24:g}" text-anchor="middle">{_esc(participant.label)}</text><path d="M{x:g},{top+38:g} L{x:g},{height-15:g}" stroke="#94a3b8" stroke-dasharray="5 5"/>')
        for i, (src, dst, label, dashed) in enumerate(messages):
            y = top + 75 + i * 65; x1, x2 = participants[src].x, participants[dst].x
            attrs = 'stroke="#475569" stroke-width="1.8" fill="none" marker-end="url(#arrow)"' + (' stroke-dasharray="6 4"' if dashed else '')
            content.append(f'<path d="M{x1:g},{y:g} L{x2:g},{y:g}" {attrs}/><text x="{(x1+x2)/2:g}" y="{y-8:g}" text-anchor="middle" fill="#334155">{_esc(label)}</text>')
        return self._svg(int(left + max(1, len(participants)-1)*gap + 80), int(height), "".join(content))


def render(source: str) -> str:
    return MermaidRenderer().render(source)
