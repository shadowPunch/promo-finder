import streamlit as st

import charts
import theme
from loaders import data

results = data("results.json")
run, checks, links = results["run"], results["checks"], results["links"]

theme.label(f"Run {run['id']} · {run['episodes']} episodes · model {run['model']} · about ${run['cost_usd']:.2f}")
st.title("What it found in the 50-episode pack")
theme.stats([(str(f["value"]), f["label"]) for f in results["funnel"]])

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("Which re-cuts win")
    st.altair_chart(charts.win_rates(results["win_rates"]), theme=None, width="stretch")
    st.caption("Share of moments each kind of cut won, among moments where it was tried. A new opening is the only "
               "change that reliably beats the original.")
with right:
    st.subheader("Can we trust the pick?")
    st.table([{"Check": "Same pick in both orders", "Result": theme.pct(checks["order_agreement"]), "Chance": "50%"},
              {"Check": "Same winner from each half", "Result": theme.pct(checks["split_half_same_winner"]),
               "Chance": "–"},
              {"Check": "First-shown cut wins", "Result": theme.pct(checks["first_shown_win_rate"]),
               "Chance": "50%"}])
    st.caption(f"{checks['n']} duels. 50% on the last row means no pull towards whichever cut is shown first.")

st.subheader("The posting slate")
st.dataframe(
    [{"#": r["rank"], "Promo": r["title"], "Role": r["role"], "Cut": r["change"], "Segments": r["segments"],
      "Sec": r["duration_s"], "Score": r["score"], "Duels won": round(100 * r["win_share"])} for r in results["slate"]],
    hide_index=True, width="stretch",
    column_config={"#": st.column_config.NumberColumn(width=30), "Role": st.column_config.TextColumn(width=75),
                   "Cut": st.column_config.TextColumn(width=85), "Sec": st.column_config.NumberColumn(width=40),
                   "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f", width=110),
                   "Duels won": st.column_config.NumberColumn(format="%d%%", width=80)})
st.caption("Proven = the core audience; wild card = aimed at newcomers. Close scores are ties: the order across "
           "moments still uses the noisier absolute score.")

st.subheader("Two promos in full")
for ex in results["excerpts"]:
    with st.container(border=True):
        theme.label(f"#{ex['rank']} · {ex['change']} · {ex['duration_s']:.0f} seconds · {ex['segments']}")
        st.markdown(f"### {ex['title']}")
        script_col, info_col = st.columns([3, 2], gap="large")
        with script_col:
            theme.script(ex["lines"])
        with info_col:
            st.markdown(f"**Hook:** {ex['hook']}  \n**Open question:** {ex['sinker_question']}")
            a, b, c = st.columns(3)
            a.metric("Score", f"{ex['score']:.1f}", help="65% viewer A + 35% viewer B")
            b.metric("Viewer A", f"{ex['viewer_a']:.1f}")
            c.metric("Duels won", theme.pct(ex["win_share"]))
            st.altair_chart(charts.still_watching(ex["curve_a"], ex["curve_b"]), theme=None, width="stretch")
            st.caption("Cuts tried, with their share of duels won: " + " · ".join(
                f"**{v['label']} {theme.pct(v['win_share'])}**" if v["winner"] else f"{v['label']} {theme.pct(v['win_share'])}"
                for v in ex["versions"]))

st.write("")
st.link_button("Download all outputs on GitHub", links["results"], type="primary", icon=":material/download:")
st.caption(f"All 12 winners, every version and duel, the full report and the run settings. "
           f"Tracked in W&B: [{run['id']}]({run['wandb_url']}).")
