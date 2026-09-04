#!/usr/bin/env python3
import argparse
from mermaid_renderer import MermaidRenderer


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Mermaid diagram as SVG or PDF")
    parser.add_argument("input", help=".mmd file or - for stdin")
    parser.add_argument("output", help="output SVG or PDF file")
    args = parser.parse_args()
    if args.input == "-":
        import sys
        source = sys.stdin.read()
        if args.output.lower().endswith(".pdf"):
            MermaidRenderer().render_pdf(source, args.output)
        else:
            MermaidRenderer().render_text_to_file(source, args.output)
    else:
        source = open(args.input, encoding="utf-8").read()
        if args.output.lower().endswith(".pdf"):
            MermaidRenderer().render_pdf(source, args.output)
        else:
            MermaidRenderer().render_text_to_file(source, args.output)


if __name__ == "__main__":
    main()
