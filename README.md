# PyMermaid

A small Mermaid rendering engine written in Python. It generates SVG files and currently supports `flowchart`/`graph` and `sequenceDiagram`. Flowcharts use Graphviz (`dot`) when available; the Windows package includes its own Graphviz runtime so its layout stays consistent with Linux and macOS packages. If Graphviz is unavailable, a Python fallback renderer is used.

Install the PDF and preview dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usage

```python
from mermaid_renderer import MermaidRenderer

svg = MermaidRenderer().render("""flowchart TD
    A[Start] --> B{Choice?}
    B -->|Yes| C[End]
    B -->|No| D[Try again]
""")
open("diagramme.svg", "w", encoding="utf-8").write(svg)
```

Command line:

```bash
python pymermaid.py diagram.mmd diagram.svg
```

Graphical application:

```bash
.venv/bin/python pymermaid_app.py
```

Or simply:

```bash
python3 pymermaid_app.py
```

The application automatically uses `.venv` when necessary. You can also start it with the `launch_pymermaid.sh` script.

The application lets you open or enter a diagram, displays a live preview after each modification, scales the image to fit the available space while preserving its proportions, and exports directly to SVG or PDF. PDF export and preview use the CairoSVG Python library, without Inkscape.

The interface is available in French, English, German, Spanish, and Italian through the `Language` menu.

SVG output can be opened directly in a web browser. PDF and PNG conversion is available through CairoSVG in the virtual environment.

For a source launch on Windows, install Graphviz or set `GRAPHVIZ_BIN` to the directory containing `dot.exe`. The packaged application discovers its bundled executable automatically.

This project is distributed under the GNU GPL v3 license (see `LICENSE`).

## CI packages

The Linux artifact includes both `PyMermaid-Linux-x64.tar.gz` and a native `PyMermaid-Debian-Ubuntu-amd64.deb` package. The Debian package targets amd64 and declares Graphviz and the required graphical libraries as dependencies.

Every push, pull request, or manual workflow run builds packages for Linux, Windows, and macOS. Download them from the workflow's **Artifacts** section on GitHub Actions.
