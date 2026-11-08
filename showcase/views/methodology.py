import streamlit as st

import theme
from loaders import data

checks = data("results.json")["checks"]

theme.label("Methodology")
st.title("Cheap and wide first, expensive and narrow last")
st.write("Every step that needs judgement goes to an AI model; every rule, timestamp and number is code. The model "
         "only ever cites script block ids, so a promo can't start mid-line or invent a timestamp.")

STEPS = [
    ("Parse", "code", "Screenplays become timed blocks: dialogue, action, camera and sound cues."),
    ("Find", "model", "Ten episodes per call. Each promo names its engine (explosive, funny, puzzling or shocking) "
                      "and a sinker: one open question with 2–4 believable answers that the show really answers "
                      "later."),
    ("Rule checks", "code", "20–60 seconds, hook within 3 seconds, cuts snapped to block edges, at most 3 segments."),
    ("Quick screen", "model", "A cold viewer rates every valid promo; the best one per episode is shortlisted."),
    ("Re-cut", "model", "An editor writes three versions of each moment, one change each: a new hook, a new ending, "
                        "a new length or a new structure."),
    ("Simulated audience", "model", "Two blind viewers react line by line: the emotion, how strong it is, who scrolls "
                                    "away, and what they imagine happens next."),
    ("Engagement score", "code", "Hook, completion, punch and sinker, 25 points each, minus up to 15 for confusion."),
    ("Head-to-head duels", "model", "Every pair of cuts of a moment, shown in both orders in separate calls. The cut "
                                    "that wins the most duels is the moment's winner."),
    ("Posting slate", "code", "70 / 20 / 10: proven winners, wild cards for new audiences, one experiment."),
]
steps = "".join(f'<div class="pf-step {kind}"><b>{theme.esc(name)}</b><span class="pf-tag {kind}">{kind}</span>'
                f'<p>{theme.esc(text)}</p></div>' for name, kind, text in STEPS)
st.html(f'<div class="pf-steps">{steps}</div>')

st.subheader("The engagement score")
st.write("Scored for each viewer from 0 to 100, then blended: 65% the core fan (a woman aged 25–44 who likes romance "
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

st.subheader("Why duels pick the winner")
st.write("Absolute scores were too noisy to choose between cuts of the same moment: two scoring passes agreed on the "
         "order of a pair only 61% of the time, and picked the same winner in 1 of 6 moments. Judges are steadier "
         "at \"X or Y?\" than at \"rate this out of 100\", so each moment's winner is decided head to head.")
st.table([
    {"Check": "Same pick when a pair is judged twice (chance: 50%)", "Absolute scores": "61%",
     "Duels": theme.pct(checks["order_agreement"])},
    {"Check": "Same winner from two independent judgments", "Absolute scores": "1 of 6 moments",
     "Duels": f"{theme.pct(checks['split_half_same_winner'])} of moments"},
    {"Check": "Pull towards the first-shown cut (none: 50%)", "Absolute scores": "–",
     "Duels": theme.pct(checks["first_shown_win_rate"])},
])

left, right = st.columns(2, gap="large")
with left:
    st.subheader("Business frameworks")
    st.markdown("- **AIDA:** the score's parts follow attention → interest → desire → action\n"
                "- **North Star:** engagement, with drivers that map to platform metrics (hook rate, completion, "
                "click-through)\n"
                "- **STP / Ansoff:** 65% existing audience, 35% new audience\n"
                "- **Stage-gate:** cheap, wide screening before expensive testing\n"
                "- **Test-and-learn:** one change per version, so a win can be explained\n"
                "- **70 / 20 / 10:** the posting slate\n"
                "- **Jobs to be done:** no fake-out endings; the promo's promise must be kept")
with right:
    st.subheader("Where it can go wrong")
    st.markdown("1. **Wrong moment:** no promo was labelled funny, and episodes 6, 10 and 17 got none.\n"
                "2. **Wrong cut:** only new openings helped; new endings, lengths and structures never won a duel.\n"
                "3. **Wrong ranking across moments:** duels compare cuts of one moment, so the slate order still "
                "uses absolute scores. Treat close ranks as ties.\n"
                "4. **Wrong audience:** the simulated viewer reads speaker names a real viewer never sees, and AI "
                "viewers agree only weakly with humans in published tests.\n"
                "5. **Model bias:** one model finds, edits and judges.")
