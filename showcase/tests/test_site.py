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
