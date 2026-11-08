# Promo Finder v2: engagement tournament

Finds 20–60 s promo clips in a microdrama's timestamped screenplays, re-cuts the best moments into several versions,
scores every version with a simulated audience, picks each moment's best cut in head-to-head duels, and recommends a
posting slate.

v1 (the parent folder) finds promos that follow the rules. v2 adds a measurable engagement score and uses it to try
versions and keep the winner. Design and research: `docs/superpowers/specs/2026-11-08-engagement-tournament-design.md`.

## Quick start

```bash
cd v2
uv sync
# settings: v2 uses ../.env automatically, or copy .env.example to .env
uv run promo-finder-v2 run --input "/path/to/show-scripts" --max-cost 5
uv run pytest                 # tests use fake models: no network, no cost
uv run streamlit run app.py   # optional review app
```

## How it works

```
parse (code) → find v2 (LLM) → rule checks (code) → coverage check (code)
  → quick screen (LLM) → shortlist 12 (code)
  → versions (LLM editor) → rule checks (code)
  → simulated audience (LLM, two viewers, line by line) → engagement score (code)
  → head-to-head duels per moment (LLM, both orders) → winner by win share (code)
  → refine top 5 (LLM, must win its duel) → reliability check (LLM)
  → posting slate + report + W&B (code)
```

- **Find:** each promo names its engine (explosive, funny, puzzling, shocking), a hook in the first 3 s, and a sinker:
  one open question with 2–4 believable answers that the show really answers later.
- **Screen and shortlist:** a cold-viewer pass rates every promo; the top 12 go on, at most one per episode.
- **Versions:** the editor makes 3 new versions per moment, each changing one thing (opening, sinker, length or
  structure such as a cold open).
- **Simulated audience:** two blind viewers react to each version line by line: emotion, strength and the % chance
  each scrolls away. They also imagine 2–4 next scenes and say how badly they need to know what happens next.
- **Duels:** every pair of versions of a moment is shown to the same two viewers, who each pick the cut they would
  engage with more. Each pair is judged twice, once in each order and in separate calls, so a bias towards the first
  cut cancels out. The winner has the highest win share (0.65 viewer A + 0.35 viewer B); ties go to the higher
  absolute score. Why: one absolute scoring pass was too noisy to pick versions (two passes ordered a pair the same way
  only 61% of the time; chance is 50%). The run reports how often the two orders agree and how often the first cut won.
- **Refine and reliability:** the top 5 get one improvement round driven by their weak spots; the improved cut must
  beat the winner head to head. 8 winners are re-scored in a new order to measure how stable absolute scores are.

The model only points at block ids and gives reactions. Code owns every timestamp, rule and number.

## The engagement score

Per viewer, 0–100: 25 × hook (share still watching at 3 s) + 25 × completion (share still watching at the end)
+ 25 × punch (peak of the strongest engine, with small bonuses for an early surprise and for emotions that rise and
fall) + 25 × sinker (need-to-know-next × spread of the imagined next scenes) − up to 15 for confusion.
Engagement = 0.65 × viewer A (women 25–44 who like romance and revenge drama) + 0.35 × viewer B (newcomers).
Weights are a stated assumption; every component is saved so they can be fitted to real hook rate and completion.

## Settings

| Flag | Default | What it does |
|---|---|---|
| `--shortlist` | 12 | moments that get new versions |
| `--versions` | 3 | new versions per moment |
| `--refine-top` | 5 | winners that get one improvement round (0 = off) |
| `--reliability` | 8 | winners re-scored to measure stability (0 = off) |
| `--no-duels` | | pick winners by absolute score instead of head-to-head duels |
| `--duel-batch` | 12 | duels per audience call |
| `--audience-weight` | 0.65 | weight of viewer A |
| `--max-cost` | 5 | spending cap in USD (0 = none); the run stops cleanly and is tagged `partial` |
| `--max-episodes` | all | quick dev runs on the first N episodes |
| `--tag` | | W&B tag, repeatable |

Model and provider come from `.env` (`LLM_*`; `JUDGE_*` overrides the screen and audience model). Backends: `codex`
(Codex CLI, for gateways such as AgentRouter) and `openai` (any OpenAI-compatible API). Replies are cached in
`.cache/llm`, so reruns cost nothing.

## Code map

| Module | Job |
|---|---|
| `parser.py`, `transcript.py` | screenplay → timed blocks; block ids; numbered clip lines |
| `finder.py` | finder calls (5 episodes each) and the coverage check |
| `validate.py` | every timing rule, with small automatic repairs |
| `screen.py` | quick screen, shortlist, footage dedupe |
| `editor.py` | versions and the refine round |
| `audience.py` | simulated viewers; per-clip validation and one retry |
| `duels.py` | head-to-head duels in both orders, win shares, order agreement and position bias |
| `engagement.py` | the score maths (pure functions) |
| `tournament.py` | pick winners (duels or score), refine, reliability, win rates |
| `slate.py` | 70/20/10 posting slate |
| `budget.py`, `llm.py`, `codex_client.py` | spending cap, model client, Codex backend |
| `report.py`, `tracking.py`, `pipeline.py`, `cli.py` | outputs, W&B, the run, the command |

## Outputs

`outputs/<show>/<run_id>/`: `report.md` (slate first, then each winner with its score parts, drop-off sparklines,
AIDA timeline, version history with duel win shares, and transcript), `promos.json/csv` (winners), `versions.json`
(every version with per-second curves, and every duel with both picks and the reason), `screened.json`, `rejected.json`, `raw_llm.jsonl`, `run_meta.json`.

## Business frameworks behind the design

AIDA (the four score parts), North Star metric tree (engagement split into drivers that map to platform metrics),
STP and Ansoff (65% core audience, 35% newcomers), stage-gate funnel (cheap wide stages, expensive narrow ones),
test-and-learn (one change per version; win rates per change type), 70/20/10 portfolio (posting slate), Pareto (refine
only the top), jobs to be done (no fake-out sinkers), unit economics (cost per show and per promo).

## Tracking

Every run is logged to Weights & Biases (project `kuku-promo-finder`, tag `v2`): config incl. prompt versions and
weights, counts per stage, engagement spreads, win rate per change type, refine uplift, reliability, duel order
agreement and position bias, spend against the cap, and tables of winners (with win shares) and curves. Screenplay text is never sent to W&B. `PROMO_WANDB=0` runs untracked.

## Limits

- Script only: it can't judge visuals or acting, or whether script times match the final cut.
- One model makes and scores versions; blind, shuffled scoring and the reliability check limit the bias.
- AI viewers agree only weakly with real viewers: the score ranks versions, it doesn't forecast exact metrics.
- One absolute audience pass is noisy: the same 23 versions scored twice agreed at r = 0.18. That is why winners are
  picked in duels; absolute scores still rank winners across moments and fill the slate, so treat small gaps there as
  ties.
- Weights are uncalibrated until real post-launch metrics exist.

## Troubleshooting

- `ModuleNotFoundError: osrf_pycommon` in pytest: a ROS `PYTHONPATH` leaks in; run `env -u PYTHONPATH uv run pytest`.
- `CodexError ... 403`: the key can't use `LLM_MODEL`; check the model name your gateway allows.
