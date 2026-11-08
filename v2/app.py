"""Streamlit front end for v2: upload a show's screenplays, run the engagement tournament, review the slate.

Local: `uv run streamlit run app.py` (reads .env). Streamlit Cloud: set the same keys as app secrets."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import find_dotenv, load_dotenv

from promo_finder_v2.evaluate import labels_csv
from promo_finder_v2.llm import LLM, LLMConfig
from promo_finder_v2.pipeline import RunResult, Settings, run
from promo_finder_v2.report import aida_timeline, segments_text, sparkline
from promo_finder_v2.transcript import clip_lines, render_clip


def load_settings_into_env() -> None:
    load_dotenv(find_dotenv(usecwd=True))  # .env from the folder you run in (or a parent)
    try:
        for key, value in st.secrets.items():
            os.environ.setdefault(key, str(value))
    except Exception:  # no secrets file when running locally
        pass


def run_app(files, settings: Settings) -> RunResult:
    cfg = LLMConfig.from_env("LLM")
    judge_cfg = LLMConfig.from_env("JUDGE", fallback=cfg)
    bar = st.progress(0.0, text="Reading episodes…")
    with tempfile.TemporaryDirectory() as tmp:
        show_dir = Path(tmp) / "uploaded-show"
        show_dir.mkdir()
        for f in files:
            (show_dir / f.name).write_bytes(f.getvalue())
        return run(show_dir, Path("outputs"), LLM(cfg), LLM(judge_cfg), settings, tags=["app"],
                   progress=lambda i, n, tag: bar.progress(i / n, text=f"{tag} ({i}/{n})"))


def review(result: RunResult) -> None:
    meta, counts = result.meta, result.meta["counts"]
    st.success(f"{len(result.winners)} winners from {meta['n_episodes']} episodes · {counts['versions_scored']} "
               f"versions scored · spend ≈ ${meta['usage']['cost_usd']:.2f}")
    if meta.get("partial"):
        st.warning("Spending cap reached: this run is partial.")
    left, right = st.columns(2)
    left.download_button("Download promos.csv", (result.out_dir / "promos.csv").read_bytes(), "promos.csv")
    right.download_button("Download versions.json", (result.out_dir / "versions.json").read_bytes(), "versions.json")
    st.subheader("Recommended posting slate")
    st.table([{"role": p.slate_role, "rank": p.rank, "promo": p.candidate.title, "engagement": p.engagement.score,
               "duels won": "-" if p.win_share is None else f"{p.win_share:.0%}", "engine": p.engagement.engine,
               "segments": segments_text(p)} for p in result.slate])
    reviewed = []
    for p in result.winners:
        c, e = p.candidate, p.engagement
        with st.expander(f"#{p.rank} · {c.title} · {e.score:.1f} · {p.slate_role or 'not in slate'}",
                         expanded=p.rank <= 3):
            lines = clip_lines(p, result.episodes)
            st.markdown(f"**Segments:** {segments_text(p)}  \n**Hook:** {c.hook}  \n**Sinker:** {c.sinker_question}  \n"
                        f"**Still watching:** A `{sparkline(e.a.curve)}` · B `{sparkline(e.b.curve)}`  \n"
                        f"**AIDA:** {aida_timeline(lines, p.reaction) if p.reaction else '-'}")
            st.code(render_clip(lines), language=None)
            label = st.radio("Editor decision", ["unreviewed", "post", "maybe", "reject"],
                             horizontal=True, key=f"label-{p.promo_id}")
            reason = st.text_input("Reason (optional)", key=f"reason-{p.promo_id}")
            if label != "unreviewed":
                reviewed.append([p.rank, p.promo_id, c.title, label, reason])
    if reviewed:
        st.download_button(f"Download labels.csv ({len(reviewed)} reviewed)", labels_csv(reviewed), "labels.csv")


def main() -> None:
    st.set_page_config(page_title="Promo Finder v2", layout="wide")
    load_settings_into_env()
    st.title("Promo Finder v2")
    st.caption("Upload a microdrama's timestamped screenplays: it finds promo moments, tries versions of each, scores "
               "them with a simulated audience, picks each moment's best cut in head-to-head duels and recommends a "
               "posting slate.")
    with st.sidebar:
        st.markdown(f"**Model:** `{os.environ.get('LLM_MODEL', 'not set')}`")
        settings = Settings(
            per_call=st.slider("Episodes per finder call", 1, 10, 5),
            shortlist=st.slider("Moments for the tournament", 2, 20, 12),
            versions=st.slider("New versions per moment", 1, 4, 3),
            refine_top=st.slider("Winners refined once", 0, 8, 5),
            duels=st.toggle("Pick winners in head-to-head duels", value=True),
            max_cost=st.number_input("Spending cap (USD)", 0.5, 20.0, 5.0, step=0.5),
        )
    files = st.file_uploader("Screenplay .txt files (one per episode)", type="txt", accept_multiple_files=True)
    if files and st.button("Find promos", type="primary"):
        try:
            st.session_state["result"] = run_app(files, settings)
        except (Exception, SystemExit) as err:
            st.error(f"Run failed: {err}")
    if "result" in st.session_state:
        review(st.session_state["result"])


main()
