import streamlit as st

import theme
from loaders import data

links = data("results.json")["links"]

theme.label("Kuku AI Generalist assignment · Problem 1 · Nithish Ravikkumar (23123028)")
st.html('<h1 class="pf-hero">From scripts to <em>promos</em></h1>')
st.html('<p class="pf-lede">Promo Finder reads a microdrama\'s timestamped screenplays and finds the 20–60 second '
        'stretches that make a good promo: a hook in the first three seconds, a punch in the middle and an ending '
        'that leaves one question open. It re-cuts each strong moment, tests every cut on a simulated audience, '
        'picks the best cut through clip-by-clip comparisons and outputs a ranked list of recommended promos.</p>')
st.write("")

STEPS = [
    ("01", "Find", ("An AI model reads the episodes, ten at a time, and suggests moments that could work as a promo. "
                   "Then a few simple checks make sure each one is the right length, grabs you in the first three "
                   "seconds and cuts cleanly.")),
    ("02", "Test", ("Every strong moment gets three alternative cuts. Two simulated viewers watch each cut line by "
                   "line, and how long they stay hooked becomes its engagement score.")),
    ("03", "Pick", ("The viewers then look at the cuts two at a time and choose the one they would keep watching. "
                   "The winners become a ranked list of promos worth posting.")),
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
