import json
from pathlib import Path

import pytest

from helpers import fake_llm
from promo_finder.captions import Brief, character_names, check_captions, write_captions
from promo_finder.parser import parse_show
from promo_finder.transcript import ClipLine

DEMO_SHOW = Path(__file__).parents[1] / "examples" / "demo-show"
LINES = [ClipLine("L01", 0.0, 2.0, "MEERA: I'm back.", False), ClipLine("L02", 2.0, 5.0, "ARJUN: Meera?", False)]
GOOD = {"story": "They threw her out at the altar. Five years later she walked back in.",
        "you": "POV: the bride they threw out just walked into your wedding. Now what?",
        "meme": "Me at 2 AM pretending I'm not invested in a jilted bride's comeback like it's prestige TV.",
        "reaction": "I gasped at who she brought with her."}


def _reply(**promos) -> str:
    return json.dumps({"promos": [{"promo": promo_id, **captions} for promo_id, captions in promos.items()]})


def test_good_captions_pass_the_checks():
    assert check_captions(GOOD, {"Meera"}).story == GOOD["story"]


def test_captions_over_the_word_limit_are_rejected():
    long = " ".join(["word"] * 17)
    with pytest.raises(ValueError, match="story has 17 words"):
        check_captions({**GOOD, "story": long}, set())


def test_character_names_are_rejected_but_not_inside_other_words():
    with pytest.raises(ValueError, match="reaction uses the name Meera"):
        check_captions({**GOOD, "reaction": "I gasped when meera walked in."}, {"Meera"})
    check_captions({**GOOD, "reaction": "I gasped at the Meeran palace."}, {"Meera"})


def test_names_are_speakers_who_are_addressed_and_never_written_in_lower_case():
    episodes = {e.number: e for e in parse_show(DEMO_SHOW)}
    # roles such as DOCTOR, GUEST or INSPECTOR also speak, but they are common words, not names
    assert character_names(episodes) == {"Arjun", "Bunty", "Kabir", "Meera", "Savitri", "Sharma", "Tanya"}


def test_a_rejected_promo_is_retried_once_with_the_reason(tmp_path):
    named = {**GOOD, "story": "Meera came back five years later."}
    llm = fake_llm([_reply(P01=GOOD, P02=named), _reply(P01=GOOD)], tmp_path)
    briefs = [Brief("a", "hook a", "question a", LINES), Brief("b", "hook b", "question b", LINES)]
    written, failed = write_captions(briefs, {"Meera", "Arjun"}, llm)
    assert set(written) == {"a", "b"} and failed == []
    first, retry = (r["messages"][1]["content"] for r in llm.client.requests)
    assert "Never use these character names: Arjun, Meera" in first and "### PROMO P02" in first
    assert "### PROMO P01\nHOOK: hook b" in retry and "story uses the name Meera" in retry


def test_a_promo_that_fails_twice_is_left_out(tmp_path):
    named = {**GOOD, "you": "POV: you are Meera."}
    written, failed = write_captions([Brief("a", "h", "q", LINES)], {"Meera"},
                                     fake_llm([_reply(P01=named), _reply(P01=named)], tmp_path))
    assert written == {} and failed == []


def test_a_failed_call_is_recorded(tmp_path):
    written, failed = write_captions([Brief("a", "h", "q", LINES)], set(), fake_llm(["bad"] * 3, tmp_path))
    assert written == {} and failed == ["captions-01"]


def test_a_finished_run_gets_captions_json_and_nothing_else_changes(tmp_path, monkeypatch):
    from helpers import CAPTIONS, FIXTURE_SHOW, pipeline_reply
    from promo_finder.captions import caption_run
    from promo_finder.pipeline import Settings, run

    monkeypatch.setenv("PROMO_WANDB", "0")
    done = run(FIXTURE_SHOW, tmp_path / "out", fake_llm(pipeline_reply, tmp_path / "c1"),
               settings=Settings(captions=False))
    before = {f.name: f.read_bytes() for f in done.out_dir.iterdir()}
    out = caption_run(done.out_dir, done.episodes, fake_llm(pipeline_reply, tmp_path / "c2"))
    saved = json.loads((done.out_dir / "captions.json").read_text())
    assert saved == out and out["n_promos"] == 2 and out["failed_calls"] == []
    assert set(out["captions"]) == {p.promo_id for p in done.winners}
    assert all(c == CAPTIONS for c in out["captions"].values())
    assert {f.name: f.read_bytes() for f in done.out_dir.iterdir() if f.name != "captions.json"} == before
