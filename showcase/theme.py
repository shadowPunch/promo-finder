"""Shared look: the CSS file plus a few HTML snippets Streamlit has no widget for."""
from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"


def esc(text) -> str:
    return escape(str(text))


def css() -> None:
    st.html(f"<style>{(ASSETS / 'style.css').read_text(encoding='utf-8')}</style>")


def label(text: str) -> None:
    st.html(f'<p class="pf-label">{esc(text)}</p>')


def stats(items: list[tuple[str, str]]) -> None:
    """A row of big numbers with a caption under each."""
    cells = "".join(f'<div class="pf-stat"><b>{esc(v)}</b><span>{esc(k)}</span></div>' for v, k in items)
    st.html(f'<div class="pf-stats">{cells}</div>')


def pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0%}"


def script(lines: list[dict]) -> None:
    """Promo lines as a screenplay page: time from the clip start, speaker or cue, words."""
    rows = []
    for line in lines:
        if line["cut_before"]:
            rows.append('<div class="pf-cut">cut</div>')
        cue = "pf-speaker" if line["kind"] == "dialogue" else "pf-cue"
        rows.append(f'<div class="pf-line"><span class="pf-tc">{line["t0"]:04.1f}</span>'
                    f'<span class="{cue}">{esc(line["label"])}</span><p>{esc(line["text"])}</p></div>')
    st.html(f'<div class="pf-script">{"".join(rows)}</div>')
