from pathlib import Path

from streamlit.testing.v1 import AppTest

from helpers import FIXTURE_SHOW, fake_llm, pipeline_reply
from promo_finder.pipeline import run

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_renders_the_upload_page():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value == "Promo Finder"


def test_app_reviews_a_run(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMO_WANDB", "0")
    result = run(FIXTURE_SHOW, tmp_path / "out", fake_llm(pipeline_reply, tmp_path / "c"))
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    assert len(at.expander) == len(result.winners)
