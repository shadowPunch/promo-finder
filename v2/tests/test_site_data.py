import json

import pytest
from helpers import FIXTURE_SHOW, fake_llm, fixture_episodes, pipeline_reply

from promo_finder_v2 import site_data
from promo_finder_v2.cli import main
from promo_finder_v2.models import Segment
from promo_finder_v2.pipeline import Settings, run
from promo_finder_v2.transcript import segment_lines

EPISODES = fixture_episodes()


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    """A real run folder: the full pipeline on the fixture show with a fake model."""
    tmp = tmp_path_factory.mktemp("run")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PROMO_WANDB", "0")
        result = run(FIXTURE_SHOW, tmp / "out", fake_llm(pipeline_reply, tmp / "c1"),
                     fake_llm(pipeline_reply, tmp / "c2"), Settings())
    return result.out_dir


def test_segment_lines_times_lines_from_the_clip_start():
    lines = segment_lines([Segment(1, 0.0, 26.0)], EPISODES)
    assert lines[0].line == "L01" and lines[0].start == 0.0 and not lines[0].cut_before


def test_load_run_names_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="promos.json"):
        site_data.load_run(tmp_path)


def test_results_data_has_funnel_slate_checks_and_excerpts(run_dir):
    data = site_data.results_data(site_data.load_run(run_dir), EPISODES, excerpt_ranks=(1,))
    assert [f["value"] for f in data["funnel"]] == [3, 2, 2, 6, 8, 2]
    assert [r["rank"] for r in data["slate"]] == [1, 2] and data["slate"][0]["role"] == "proven"
    assert data["checks"]["n"] == 8 and "split_half_same_winner" in data["checks"]
    assert {w["change"] for w in data["win_rates"]} >= {"original", "sinker", "refine"}
    (excerpt,) = data["excerpts"]
    assert excerpt["rank"] == 1 and excerpt["lines"] and excerpt["curve_a"]
    assert {"t0", "t1", "kind", "label", "text", "cut_before"} <= set(excerpt["lines"][0])
    assert data["links"]["repo"].startswith("https://github.com/")


def test_demo_data_links_candidates_to_episode_blocks(run_dir):
    data = site_data.demo_data(site_data.load_run(run_dir), EPISODES, title="Fixture")
    block_ids = {b["id"] for e in data["show"]["episodes"] for b in e["blocks"]}
    assert len(data["candidates"]) == 3  # 2 valid + 1 rejected as too short
    assert {c["status"] for c in data["candidates"]} >= {"rejected"}
    for c in data["candidates"]:
        assert c["blocks"] and set(c["blocks"]) <= block_ids
    assert len(data["moments"]) == 2 and all(m["duels"] for m in data["moments"])
    assert data["promo"]["lines"] and data["promo"]["next_episode"] >= 2


def test_export_site_cli_writes_json(run_dir, tmp_path):
    out = tmp_path / "demo.json"
    assert main(["export-site", "--kind", "demo", "--run", str(run_dir), "--input", str(FIXTURE_SHOW),
                 "--out", str(out), "--title", "Fixture"]) == 0
    assert json.loads(out.read_text())["show"]["title"] == "Fixture"
