import streamlit as st

import theme
from loaders import data

results = data("results.json")
funnel = {f["label"]: f["value"] for f in results["funnel"]}
links = results["links"]

theme.label("Kuku AI Generalist assignment · Problem 1 · Nithish Ravikkumar (23123028)")
st.html('<h1 class="pf-hero">From 50 scripts to the <em>10&nbsp;promos</em> worth posting.</h1>')
st.html('<p class="pf-lede">Promo Finder reads a microdrama\'s timestamped screenplays and finds the 20–60 second '
        'stretches that make a good promo: a hook in the first three seconds, a punch in the middle and an ending '
        'that leaves one question open. It re-cuts each strong moment, tests every cut on a simulated audience, '
        'picks the best cut in head-to-head duels and hands an editor a ranked posting slate. No human labels.</p>')
theme.stats([(str(funnel["promos proposed"]), "promos found in 50 episodes"),
             (str(funnel["moments tested"]), "moments tested"),
             (str(funnel["versions scored"]), "cuts scored by the audience"),
             (str(funnel["head-to-head duels"]), "head-to-head duels"),
             (str(funnel["promos to post"]), "promos to post")])

STEPS = [
    ("01", "Find", ("An AI model reads ten episodes at a time and proposes promos by citing script block ids. Code "
                   "checks every rule: length, hook within 3 seconds, clean cuts.")),
    ("02", "Test", ("Each strong moment gets three re-cuts. Two simulated viewers react line by line, and code turns "
                   "their reactions into an engagement score.")),
    ("03", "Pick", ("The viewers compare cuts two at a time, in both orders. The cut that wins most duels goes into a "
                   "70 / 20 / 10 posting slate.")),
]
for col, (num, head, body) in zip(st.columns(3), STEPS):
    with col:
        st.html(f'<div class="pf-card"><span class="pf-num">{num}</span><h4>{head}</h4>'
                f'<p>{theme.esc(body)}</p></div>')

st.write("")
a, b, c = st.columns(3)
a.page_link("views/demo.py", label="Watch the demo", icon=":material/play_circle:")
b.page_link(links["repo"], label="Code on GitHub", icon=":material/code:")
c.page_link(links["solution_doc"], label="Read the solution doc", icon=":material/description:")
