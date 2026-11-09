"""Read the exported data files. Regenerate them with `promo-finder export-site` (see showcase/README.md)."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

DATA = Path(__file__).parent / "data"


@st.cache_data
def read(name: str) -> dict | None:
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def data(name: str) -> dict:
    """The file's contents, or a short error on the page (and the page stops) if it can't be read."""
    found = read(name)
    if found is None:
        st.error(f"Couldn't read `showcase/data/{name}`. Regenerate it with `promo-finder export-site` "
                 "(see showcase/README.md).")
        st.stop()
    return found
