"""Render a Markdown doc to an A4 PDF with headless Chrome, and report the page count.

Usage: uv run --with markdown --with pypdf python scripts/doc_to_pdf.py docs/solution-doc.md out.pdf "Title"."""
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown
import pypdf

CSS = """@page{size:A4;margin:1.6cm} body{font:10.5pt/1.35 Arial,sans-serif}
h1{font-size:15pt;margin:0 0 4pt} h2{font-size:12pt;margin:9pt 0 3pt} p,ul,ol{margin:3pt 0} li{margin:1pt 0}
h1,h2,p:has(+ table){break-after:avoid} table{break-inside:avoid;border-collapse:collapse;font-size:9pt}
td,th{border:1px solid #999;padding:2pt 4pt;vertical-align:top}
pre{font-size:8.5pt;background:#f4f4f4;padding:4pt;white-space:pre-wrap} code{font-size:9pt}"""


def main(src: str, out: str, title: str) -> None:
    body = markdown.markdown(Path(src).read_text(), extensions=["tables", "fenced_code"])
    html = (f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "doc.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={Path(out).resolve()}", page.as_uri()], check=True, capture_output=True)
    print(f"{out}: {len(pypdf.PdfReader(out).pages)} pages")


if __name__ == "__main__":
    main(*sys.argv[1:4])
