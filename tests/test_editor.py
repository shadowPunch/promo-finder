import json

from helpers import fake_llm, fixture_episodes, make_candidate, make_promo
from promo_finder.editor import make_versions, refine, scene_context
from promo_finder.models import Moment
from promo_finder.validate import validate

EPISODES = fixture_episodes()


def _moment():
    original = validate(make_candidate(), EPISODES)  # E01 0-26 s
    return Moment("M01", original, [original])


def _seg(start, end):
    return [{"start": start, "end": end}]


def test_scene_context_covers_the_padded_window():
    text = scene_context(make_promo([(1, 20.0, 26.0)]), EPISODES, pad=5.0)
    assert text.splitlines()[0] == "=== EPISODE 1 ==="
    assert "E01L007 [00:20.00-00:26.00]" in text and "E01L008" in text
    assert "E01L005" not in text


def test_make_versions_validates_and_attaches_versions(tmp_path):
    moment = _moment()
    versions = [
        make_candidate(segments=_seg("E01L001", "E01L008"), cliffhanger_ref="E01L008", change="sinker").model_dump(),
        make_candidate(segments=_seg("E01L003", "E01L004"), hook_ref="E01L003", cliffhanger_ref="E01L004",
                       change="length").model_dump(),
        make_candidate(change="hook").model_dump(),                                  # same cut as the original
        make_candidate(segments=_seg("E01L002", "E01L007")).model_dump(),           # names no change
    ]
    llm = fake_llm([json.dumps({"moments": [{"moment": "M01", "versions": versions}]})], tmp_path)
    rejections, failed = make_versions([moment], EPISODES, llm, n_versions=4)
    assert failed == []
    assert [v.candidate.change for v in moment.versions] == ["original", "sinker"]
    assert moment.versions[1].moment_id == "M01"
    assert [r.reason.split()[0] for r in rejections] == ["too_short", "duplicate_version", "missing_change"]
    assert {r.moment_id for r in rejections} == {"M01"}
    user = llm.client.requests[0]["messages"][1]["content"]
    assert "## MOMENT M01" in user and "E01L008" in user and "write 4 new versions" in user


def test_extra_versions_are_ignored(tmp_path):
    moment = _moment()
    first = make_candidate(segments=_seg("E01L001", "E01L008"), cliffhanger_ref="E01L008", change="sinker")
    second = make_candidate(segments=_seg("E01L002", "E01L007"), change="hook")
    reply = json.dumps({"moments": [{"moment": "M01", "versions": [first.model_dump(), second.model_dump()]}]})
    make_versions([moment], EPISODES, fake_llm([reply], tmp_path), n_versions=1)
    assert [v.candidate.change for v in moment.versions] == ["original", "sinker"]


def test_failed_editor_call_keeps_only_the_original(tmp_path):
    moment = _moment()
    rejections, failed = make_versions([moment], EPISODES, fake_llm(["bad"] * 3, tmp_path))
    assert failed == ["versions-01"] and moment.versions == [moment.original]


def test_refine_stores_the_improved_version(tmp_path):
    moment = _moment()
    moment.winner = moment.original
    improved = make_candidate(segments=_seg("E01L002", "E01L007"), change="hook").model_dump()
    llm = fake_llm([json.dumps({"moments": [{"moment": "M01", "versions": [improved]}]})], tmp_path)
    rejections, failed = refine([moment], EPISODES, llm, {"M01": "Biggest drop: L03"})
    assert moment.refined is not None and moment.refined.candidate.change == "refine"
    assert moment.refined in moment.versions
    user = llm.client.requests[0]["messages"][1]["content"]
    assert "AUDIENCE TEST: Biggest drop: L03" in user and "write 1 improved version" in user
