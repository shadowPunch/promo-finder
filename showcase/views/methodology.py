import streamlit as st

import theme
from loaders import data

checks = data("results.json")["checks"]

theme.label("Methodology")
st.title("Multi-stage filtering and editing")

STEPS = [
    ("Parse", "code", "Screenplays become timed blocks: dialogue, action, camera and sound cues."),
    ("Find", "model", ("Ten episodes per call. Each promo names its engine (explosive, funny, puzzling or shocking) "
                       "and one open question that the show really answers later.")),
    ("Rule checks", "code", "20–60 seconds, hook within 3 seconds, cuts snapped to block edges, at most 3 segments."),
    ("Quick screen", "model", "A cold viewer rates every valid promo; the best one per episode is shortlisted."),
    ("Re-cut", "model", ("An editor writes three versions of each moment, one change each: a new hook, a new ending, "
                         "a new length or a new structure.")),
    ("Simulated audience", "model", ("Two blind viewers react line by line: the emotion, how strong it is, who "
                                     "scrolls away, and what they imagine happens next.")),
    ("Engagement score", "code", "Hook, completion, punch and sinker, 25 points each, minus up to 15 for confusion."),
    ("Side-by-side comparisons", "model", ("The viewers see two cuts of the same moment, in both orders, and pick the "
                                           "one they would keep watching. The cut that wins most often is the "
                                           "moment's best cut.")),
    ("Ranked promo list", "code", "The best cuts, ranked by engagement score: the list of recommended promos."),
]
steps = "".join(f'<div class="pf-step {kind}"><b>{theme.esc(name)}</b><span class="pf-tag {kind}">{kind}</span>'
                f'<p>{theme.esc(text)}</p></div>' for name, kind, text in STEPS)
st.html(f'<div class="pf-steps">{steps}</div>')

st.subheader("The engagement score")
st.write("Scored for each viewer from 0 to 100, then blended: 65% the core fan (a woman aged 18–30 who likes romance "
         "and revenge drama), 35% a newcomer who only stops for something explosive, funny, puzzling or shocking.")
PARTS = [("Hook", "Share still watching at 3 seconds."), ("Completion", "Share still watching at the end."),
         ("Punch", "Peak strength of the strongest engine emotion."),
         ("Sinker", "How badly they need the next episode × how spread out their guesses about it are.")]
for col, (name, text) in zip(st.columns(4), PARTS):
    with col:
        st.html(f'<div class="pf-card"><span class="pf-num">25 points</span><h4>{name}</h4>'
                f'<p>{theme.esc(text)}</p></div>')
st.caption("Research behind it: early surprise holds attention (Teixeira et al., 2012); suspense is how much the next "
           "moment could change what you believe (Ely et al., 2015), estimated here from imagined continuations "
           "(Fong, 2024).")

st.subheader("Why we compare cuts side by side")
st.write("A single score out of 100 was too noisy to choose between cuts of the same moment: two scoring passes "
         "agreed on which of two cuts was better only 61% of the time. Asking \"which of these two would you keep "
         "watching?\" gives far steadier answers, so each moment's best cut is chosen by comparison.")
st.table([
    {"Check": "Same choice when a pair is judged twice (chance: 50%)", "Single score": "61%",
     "Side-by-side": theme.pct(checks["order_agreement"])},
    {"Check": "Same best cut from two independent rounds", "Single score": "1 of 6 moments",
     "Side-by-side": f"{theme.pct(checks['split_half_same_winner'])} of moments"},
    {"Check": "Pull towards whichever cut is shown first (none: 50%)", "Single score": "–",
     "Side-by-side": theme.pct(checks["first_shown_win_rate"])},
])

st.subheader("Model and cost")
st.markdown(
    "- **Model:** every AI step (finding, screening, re-cutting, the simulated viewers and the comparisons) used "
    "`gpt-5.6-sol`, accessed through the [AgentRouter](https://agentrouter.org) API gateway and called via the Codex "
    "CLI.\n"
    "- **Cost:** everything ran on AgentRouter's free credit. Across all development and final runs the project used "
    "about **$16.40** of API credit, all covered by the free tier, with no paid spend. The final 50-episode run used "
    "about 0.5M input and 0.1M output tokens (about $3.10); the demo run about $1.30.\n"
    "- **With more resources:** specialised tools, wrappers and models built for film and video production could "
    "replace the general-purpose model, for example models that watch the footage itself instead of reading only "
    "the script.")

left, right = st.columns(2, gap="large")
with left:
    st.subheader("Business frameworks")
    st.markdown("- **AIDA:** the score's parts follow attention → interest → desire → action\n"
                "- **North Star metric:** one engagement score whose parts map to platform metrics (hook rate, "
                "completion, click-through)\n"
                "- **Stage-gate:** a cheap, wide screen first, and expensive testing only for the moments that pass\n"
                "- **Test-and-learn:** one change per version, so every win can be explained")
with right:
    st.subheader("Weaknesses")
    st.markdown("1. **Limited labels:** every promo must fit one of four engines (explosive, funny, puzzling, "
                "shocking). Not every good moment fits these, so the label set should be expanded.\n"
                "2. **Heavy dependence on the opening:** only new openings beat the original cut. New endings, "
                "lengths and structures never won, so those editing options went unused.\n"
                "3. **No human feedback and no video:** no real viewer has judged these promos, and the tool reads "
                "only the script. Video and visual information would allow much better cut decisions.")
