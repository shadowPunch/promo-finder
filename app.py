"""Streamlit front end: upload a show's screenplay .txt files, find promos, review and label them.

Local: `uv run streamlit run app.py` (reads .env). Streamlit Cloud: set the same keys as app secrets."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import find_dotenv, load_dotenv

from promo_finder.evaluate import labels_csv
from promo_finder.llm import LLM, LLMConfig
from promo_finder.pipeline import RunResult, Settings, run
from promo_finder.report import segments_text
from promo_finder.transcript import render_promo

REVIEW_LIMIT = 25


def load_settings_into_env() -> None:
    load_dotenv(find_dotenv(usecwd=True))  # .env from the folder you run in
    try:
        for key, value in st.secrets.items():
            os.environ.setdefault(key, str(value))
    except Exception:  # no secrets file when running locally
        pass


def run_finder(files, settings: Settings) -> RunResult:
    cfg = LLMConfig.from_env("LLM")
    judge_cfg = LLMConfig.from_env("JUDGE", fallback=cfg)
    bar = st.progress(0.0, text="Reading episodes…")
    with tempfile.TemporaryDirectory() as tmp:
        show_dir = Path(tmp) / "uploaded-show"
        show_dir.mkdir()
        for f in files:
            (show_dir / f.name).write_bytes(f.getvalue())
        return run(show_dir, Path("outputs"), LLM(cfg), LLM(judge_cfg) if settings.judge_top else None, settings,
                   tags=["app"], progress=lambda i, n, tag: bar.progress(i / n, text=f"{tag} ({i}/{n})"))


def review(result: RunResult) -> None:
    counts = result.meta["counts"]
    st.success(f"{len(result.ranked)} promos from {result.meta['n_episodes']} episodes "
               f"({counts['proposed']} proposed, {counts['rejected']} rejected by rules)")
    left, right = st.columns(2)
    left.download_button("Download promos.csv", (result.out_dir / "promos.csv").read_bytes(), "promos.csv")
    right.download_button("Download promos.json", (result.out_dir / "promos.json").read_bytes(), "promos.json")
    reviewed = []
    for p in result.ranked[:REVIEW_LIMIT]:
        c = p.candidate
        with st.expander(f"#{p.rank} · {c.title} · {p.duration:.0f}s · {segments_text(p)}", expanded=p.rank <= 3):
            st.markdown(f"**Hook:** {c.hook}  \n**Cliffhanger:** {c.cliffhanger}  \n**Why:** {c.why}")
            if p.verdict:
                st.markdown(f"**Cold viewer ({p.verdict.overall}/5):** {p.verdict.understood}")
            st.code(render_promo(p, result.episodes), language=None)
            label = st.radio("Editor decision", ["unreviewed", "post", "maybe", "reject"],
                             horizontal=True, key=f"label-{p.promo_id}")
            reason = st.text_input("Reason (optional)", key=f"reason-{p.promo_id}")
            if label != "unreviewed":
                reviewed.append([p.rank, p.promo_id, c.title, label, reason])
    if reviewed:
        st.download_button(f"Download labels.csv ({len(reviewed)} reviewed)", labels_csv(reviewed), "labels.csv")


def main() -> None:
    st.set_page_config(page_title="Promo Finder", layout="wide")
    load_settings_into_env()
    st.title("Promo Finder")
    st.caption("Upload a microdrama's timestamped screenplays and get ranked 20–60 s promo clips with exact cut points.")
    with st.sidebar:
        st.markdown(f"**Model:** `{os.environ.get('LLM_MODEL', 'not set')}`")
        settings = Settings(
            per_call=st.slider("Episodes per LLM call", 1, 10, 5),
            per_episode=st.slider("Candidates per episode", 1, 4, 2),
            judge_top=st.slider("Cold-viewer judge on top N (0 = off)", 0, 25, 15),
        )
    files = st.file_uploader("Screenplay .txt files (one per episode)", type="txt", accept_multiple_files=True)
    if files and st.button("Find promos", type="primary"):
        try:
            st.session_state["result"] = run_finder(files, settings)
        except (Exception, SystemExit) as err:
            st.error(f"Run failed: {err}")
    if "result" in st.session_state:
        review(st.session_state["result"])


main()
