"""Inline the demo data into the self-contained player page (assets/player.html)."""
import json
from pathlib import Path

PLAYER = Path(__file__).parent / "assets" / "player.html"


def build(data: dict, autoplay: bool = False) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # can't close the <script> tag
    page = PLAYER.read_text(encoding="utf-8")
    page = page.replace("__AUTOPLAY__", "true" if autoplay else "false")  # before the data, which could contain it
    return page.replace("__DEMO_DATA__", payload)
