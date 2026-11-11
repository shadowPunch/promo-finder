import streamlit as st

import charts
import theme
from loaders import data

results = data("results.json")
STYLES = {"story": "Story hook", "you": "You / POV", "meme": "Self-aware meme", "reaction": "Reaction"}


def md(text: str) -> str:
    """Model-written text for st.markdown: a "$" would otherwise start a maths formula."""
    return text.replace("$", "\\$")


run, checks, links = results["run"], results["checks"], results["links"]
funnel = {f["label"]: f["value"] for f in results["funnel"]}

st.title("Results on the 50-episode show")
theme.stats([(str(funnel["promos proposed"]), "promo ideas found"),
             (str(funnel["moments tested"]), "moments tested"),
             (str(funnel["versions scored"]), "cuts tested"),
             (str(funnel["promos to post"]), "promos recommended")])

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("Which re-cuts win")
    st.altair_chart(charts.win_rates(results["win_rates"]), theme=None, width="stretch")
    st.caption("Share of moments each kind of cut won, among moments where it was tried. A new opening is the only "
               "change that reliably beats the original.")
with right:
    st.subheader("Can we trust the choice?")
    st.table([{"Check": "Same choice in both orders", "Result": theme.pct(checks["order_agreement"]),
               "Chance": "50%"},
              {"Check": "Same best cut from each half", "Result": theme.pct(checks["split_half_same_winner"]),
               "Chance": "–"},
              {"Check": "First-shown cut wins", "Result": theme.pct(checks["first_shown_win_rate"]),
               "Chance": "50%"}])
    st.caption(f"From {checks['n']} side-by-side comparisons. 50% on the last row means no pull towards whichever "
               "cut is shown first.")

st.subheader("Recommended promos, ranked")
# st.table, not st.dataframe: it wraps long captions instead of cutting them off
st.table([{"#": r["rank"], "Promo (story caption)": r["title"], "Cut": r["change"], "Segments": r["segments"],
           "Sec": f"{r['duration_s']:.0f}", "Score": f"{r['score']:.1f}", "Won": theme.pct(r["win_share"])}
          for r in results["slate"]])
st.caption("Won: share of one-on-one comparisons won against other cuts of the same moment. Promos with close "
           "scores are effectively tied.")

st.subheader("Two promos in full")
for ex in results["excerpts"]:
    with st.container(border=True):
        theme.label(f"#{ex['rank']} · {ex['change']} · {ex['duration_s']:.0f} seconds · {ex['segments']}")
        st.markdown(f"### {md(ex['title'])}")
        script_col, info_col = st.columns([3, 2], gap="large")
        with script_col:
            theme.script(ex["lines"])
        with info_col:
            st.markdown(f"**Hook:** {ex['hook']}  \n**Open question:** {ex['sinker_question']}")
            if ex.get("captions"):
                st.markdown("**Captions to test:**  \n" + "  \n".join(f"*{STYLES.get(k, k)}:* {md(v)}"
                                                                     for k, v in ex["captions"].items()))
            a, b, c = st.columns(3)
            a.metric("Score", f"{ex['score']:.1f}", help="65% viewer A + 35% viewer B")
            b.metric("Viewer A", f"{ex['viewer_a']:.1f}")
            c.metric("Comparisons won", theme.pct(ex["win_share"]))
            st.altair_chart(charts.still_watching(ex["curve_a"], ex["curve_b"]), theme=None, width="stretch")
            tried = [f"{v['label']} {theme.pct(v['win_share'])}" for v in ex["versions"]]
            tried = [f"**{t}**" if v["winner"] else t for t, v in zip(tried, ex["versions"])]
            st.caption("Cuts tried, with their share of comparisons won: " + " · ".join(tried))

st.write("")
st.link_button("Download all outputs on GitHub", links["results"], type="primary", icon=":material/download:")
st.caption(f"All 12 best cuts, every version and comparison, the full report and the run settings. "
           f"Tracked in W&B: [{run['id']}]({run['wandb_url']}).")
