import pytest
from conftest import SHOWCASE
from streamlit.testing.v1 import AppTest

PAGES = ["home", "methodology", "outputs", "demo"]
APP = str(SHOWCASE / "streamlit_app.py")


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_errors(page):
    # through the entrypoint, so st.page_link / st.navigation resolve like in the real app
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page(f"views/{page}.py").run()
    assert not at.exception, at.exception


def test_missing_data_shows_a_friendly_error(monkeypatch, tmp_path):
    import loaders
    monkeypatch.setattr(loaders, "DATA", tmp_path)
    loaders.read.clear()
    at = AppTest.from_file(APP, default_timeout=30).run()
    loaders.read.clear()
    assert not at.exception and "export-site" in at.error[0].value


def test_player_inlines_data_safely():
    import json

    from demo_player import build
    html = build({"show": {"title": "</script><b>x"}}, autoplay=True)
    payload = html.split('<script id="demo-data" type="application/json">', 1)[1].split("</script>", 1)[0]
    assert json.loads(payload)["show"]["title"] == "</script><b>x"
    assert "const AUTOPLAY = true;" in html and "__" not in html.split("<script>", 1)[1][:200]
