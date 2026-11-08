import streamlit as st
import streamlit.components.v1 as components

import theme
from demo_player import build
from loaders import data

demo = data("demo.json")
run = demo["run"]

theme.label("Demo · an artificial show, the real tool")
st.title("Watch four episodes become a promo")
st.write(f"*{demo['show']['title']}* is a four-episode microdrama written for this demo, because the Kuku scripts "
         f"are confidential. Everything the player shows is the tool's real output on it: run `{run['id']}`, "
         f"{run['calls']} model calls, about ${run['cost_usd']:.2f}. Press **Play**, or jump to any step.")
components.html(build(demo, autoplay="autoplay" in st.query_params), height=880, scrolling=True)

with st.expander("Read the four scripts"):
    for ep in demo["show"]["episodes"]:
        st.markdown(f"**Episode {ep['number']}** · {ep['logline']}")
        st.code("\n".join(f"{b['start']:06.2f}  {(b['speaker'] or b['kind']).upper():<10}  {b['text']}"
                          for b in ep["blocks"]), language=None, wrap_lines=True)
st.caption(f"Tracked in W&B: [{run['id']}]({run['wandb_url']}). The scripts are in the repo under "
           "`v2/examples/demo-show/`.")
