import json
import re

from helpers import FIXTURE_SHOW, fake_llm, make_candidate
from promo_finder_v2 import prompts
from promo_finder_v2.pipeline import Settings, run


def _reply(request):
    system, user = request["messages"][0]["content"], request["messages"][1]["content"]
    if system == prompts.JUDGE_SYSTEM:
        clips = re.findall(r"### CLIP (C\d+)", user)
        return json.dumps({"verdicts": [{"clip": c, "understood": "x", "stops_scroll": 3, "needs_next": 3,
                                         "overall": 3} for c in clips]})
    return json.dumps({"candidates": [
        make_candidate().model_dump(),
        make_candidate(segments=[{"start": "E01L003", "end": "E01L004"}],
                       hook_ref="E01L003", cliffhanger_ref="E01L004").model_dump(),  # 7 s: too short
        make_candidate(title="The portrait", segments=[{"start": "E02L001", "end": "E02L004"}],
                       hook_ref="E02L001", cliffhanger_ref="E02L004").model_dump(),
    ]})


def test_run_end_to_end_with_fake_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMO_WANDB", "0")
    result = run(FIXTURE_SHOW, tmp_path / "out", fake_llm(_reply, tmp_path / "c1"),
                 fake_llm(_reply, tmp_path / "c2"), Settings(judge_top=5))

    counts = result.meta["counts"]
    assert (counts["proposed"], counts["valid"], counts["unique"], counts["judged"]) == (3, 2, 2, 2)
    assert counts["rejected_by_reason"] == {"too_short": 1}
    assert [p.rank for p in result.ranked] == [1, 2]
    assert result.meta["usage"]["finder"]["calls"] == 1 and result.meta["usage"]["judge"]["calls"] == 1
    for name in ("promos.json", "promos.csv", "report.md", "rejected.json", "raw_llm.jsonl", "run_meta.json"):
        assert (result.out_dir / name).exists(), name
