"""Convert screenplay timecodes ("mm:ss.cc", optionally "h:mm:ss.cc") to seconds and back."""
import re

_TC = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)$")


def parse_tc(text: str) -> float:
    match = _TC.match(text.strip())
    if not match:
        raise ValueError(f"bad timecode: {text!r}")
    hours, minutes, seconds = match.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + float(seconds)


def format_tc(seconds: float) -> str:
    minutes, centis = divmod(round(seconds * 100), 6000)
    return f"{minutes:02d}:{centis / 100:05.2f}"
