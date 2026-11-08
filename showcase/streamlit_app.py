"""Promo Finder showcase. Run from the repo root: streamlit run showcase/streamlit_app.py"""
import streamlit as st

import theme

st.set_page_config(page_title="Promo Finder", page_icon="🎬", layout="wide")
theme.css()
pages = [
    st.Page("views/home.py", title="Home", default=True),
    st.Page("views/methodology.py", title="Methodology", url_path="methodology"),
    st.Page("views/outputs.py", title="Outputs", url_path="outputs"),
    st.Page("views/demo.py", title="Demo", url_path="demo"),
]
st.navigation(pages, position="top").run()
