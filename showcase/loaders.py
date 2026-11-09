"""Read the exported data files. Regenerate them with `promo-finder export-site` (see showcase/README.md)."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

DATA = Path(__file__).parent / "data"


@st.cache_data
def read(name: str, modified: float) -> dict | None:
    """Parsed file. `modified` is only part of the cache key: a redeploy that changes the file gets a fresh read."""
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def data(name: str) -> dict:
    """The file's contents, or a short error on the page (and the page stops) if it can't be read."""
    path = DATA / name
    found = read(name, path.stat().st_mtime if path.exists() else 0.0)
    if found is None:
        st.error(f"Couldn't read `showcase/data/{name}`. Regenerate it with `promo-finder export-site` "
                 "(see showcase/README.md).")
        st.stop()
    return found
