# Promo Finder v2: Engagement Tournament (design)

Date: 2026-11-08. Status: awaiting user review.

## 1. Goal

v1 finds promos that follow the rules (20–60 s, hook in 3 s, ends on a cliffhanger) but can't say whether they are
*good*. v2 adds a measurable, transcript-based **engagement score** and uses it to **try several versions of each
promo and keep the best**, with the ending ("sinker") planned to leave the viewer as curious as possible.

### What the user asked for

- Promos that maximise engagement: explosive, funny, or genuinely puzzling or shocking.
- A score built from the transcript: expected emotions plus a moment-by-moment guess at viewer reactions.
- Several versions per promo, scored, the best kept.
- The sinker planned for maximum curiosity ("hook, line and sinker").
- Simulated audience: 65% the show's likely ad audience, 35% newcomers who might not watch this genre yet.
- Build it in a new `v2/` folder; apply marketing and consulting frameworks; stay within budget.

### Assumptions

- Still script-only, clips still cut straight from the episodes (no narration, music or text added), 20–60 s.
- The score is a *prediction* of real ad metrics (hook rate, hold rate, completion). True numbers only exist after
  posting, so the score is used to compare versions, not as ground truth.
- Same single model as v1 (`gpt-5.6-sol` via the Codex CLI), swappable through `.env` as before.
- Budget: AgentRouter balance $7.17 at design time. Full run ≈ $4.10, dev runs ≈ $1.50, ≥ $1 kept for the interview.
- v1 stays frozen as the submitted baseline. v2 is a self-contained copy of the project in `v2/` (own `pyproject.toml`,
  package `promo_finder_v2`, CLI `promo-finder-v2`). Code shared with v1 is copied, not imported, so v1 never changes.

## 2. Research basis

Industry practice (how promos are made):
- Promos are cut straight from episodes, open on conflict in the first 2–3 s and cut at the peak before the reveal.
  ReelShort's formula: "conflict + reversal = enjoyment" ([AppGrowing](https://appgrowing.net/blog/reelshort/)).
- Winners use a few emotional engines: power reversal, dangerous protector, relationship contract under pressure.
  DramaBox's top ad drew ~75% of its top-10 impressions from one precise beat chain
  ([AdMapix](https://www.admapix.com/blog/ad-intelligence/dramabox-ad-strategy-2026)).
- Teams test many variants, one variable per test; e.g. 50 promo assets for one Kuku TV series
  ([The WordsEdge](https://www.linkedin.com/posts/the-wordsedge_thewordsedge-teenpatti-trailerproduction-activity-7468555874853306368-BWIp)),
  100+ AI trailer variants at another platform ([SurgeGrowth](https://blogs.surgegrowth.io/how-a-leading-microdrama-platform-creates-100s-of-trailers-in-just-5-minutes-with-surgegrowth/)).
- India: the first 2 seconds are the critical window (Meta x Kuku TV playbook,
  [Storyboard18](https://www.storyboard18.com/advertising/social-media-drives-microdrama-discovery-kuku-tv-meta-playbook-show-ws-lo-111705.htm));
  success shows as comments asking "What show is this?" ([afaqs](https://www.afaqs.com/news/mktg/tiny-episodes-big-hooks-how-micro-dramas-are-advertised-in-india-10971497)).
- Real metrics after posting: hook rate (2 s views / impressions on TikTok, 3 s on Meta), hold rate, completion,
  click-through, installs ([Billo](https://billo.app/blog/hook-rate-to-hold-rate)).

Science (what the score borrows):
- Surprise early concentrates attention; rising joy retains viewers; alternating highs and lows beats a sustained
  high; emotion explained ~72% of zapping ([Teixeira, Wedel & Pieters 2012](https://journals.sagepub.com/doi/10.1509/jmr.10.0207)).
- Suspense = variance of next-period beliefs; surprise = size of the belief change
  ([Ely, Frankel & Kamenica 2015](https://doi.org/10.1086/677350)).
- Expectations can be approximated by sampling imagined continuations from an LLM
  ([Fong](https://arxiv.org/html/2412.15239)).
- Curiosity is an information gap and peaks at intermediate certainty (Loewenstein 1994; Kang et al. 2009).
- High-arousal emotions (anger, anxiety, awe) drive sharing; sadness doesn't
  ([Berger & Milkman 2012](https://journals.sagepub.com/doi/10.1509/jmr.10.0353)). Humor = a benign violation
  ([Warren & McGraw 2015](https://www.pnas.org/doi/10.1073/pnas.1503836112)).
- Caveat: AI-simulated viewers agree with real ones only weakly (ICC 0.14 vs 0.29 human–human,
  [arXiv 2606.07541](https://arxiv.org/html/2606.07541v1); r ≈ 0.17 for physiological curves,
  [bioRxiv](https://www.biorxiv.org/content/10.64898/2026.04.13.716763v1.full.pdf)).

## 3. Business frameworks applied

| Framework | Where it shows up in v2 |
|---|---|
| AIDA | The four score parts are Attention (hook), Interest (completion), Desire (punch), Action (sinker). The editor brief and the report's timeline use the same stages. |
| North Star + metric tree (MECE) | The engagement score is the North Star, a proxy for "viewers who finish and want the next episode". It splits into four non-overlapping drivers that map to platform metrics (hook rate, completion, emotional peak, click-through), so weights can later be fitted on real data. |
| STP + Ansoff | Viewer A (65%) = market penetration (core romance fans). Viewer B (35%) = market development (newcomers). The report flags promos that win newcomers. |
| Stage-gate funnel | Cheap wide stages, expensive narrow ones: find ~100 → screen → 12 → ~48 versions → 5 improved. |
| Test-and-learn | Each version changes one variable; W&B logs the win rate per change type. |
| 70/20/10 portfolio | The report recommends a posting slate: ~7 proven, ~2 challengers from another engine, 1 newcomer wild card. Avoids creative fatigue. |
| 80/20 (Pareto) | Effort concentrates on making the top few excellent (refine round on the top 5). |
| Jobs to be done | Viewer's job: a quick emotional hit. The sinker question must be one the show really answers (no fake-outs), or installs churn. |
| Unit economics | Doc reports cost per show and per usable promo against editor hours saved. |
| Pyramid principle + issue tree | Doc leads with the answer; failure modes sorted into wrong moment / wrong cut / weak ending / wrong audience / model bias. |

## 4. Architecture

```
parse (code) → find v2 (LLM) → validate (code) → coverage check (code)
  → screen (LLM, all candidates) → shortlist (code)
  → versions (LLM editor) → validate (code)
  → audience (LLM, two viewers, line by line) → engagement score (code)
  → pick best per moment (code) → refine top R (LLM editor + audience) → reliability check (LLM audience)
  → slate + report + W&B (code)
```

All stages sit behind one spending cap (section 6.9). The LLM never produces timestamps; code owns every rule, time
and number, as in v1.

### Folder layout

```
v2/
  pyproject.toml        # package promo_finder_v2, script promo-finder-v2
  README.md
  .env.example
  app.py                # Streamlit review app, shows score + curve
  src/promo_finder_v2/
    timecode.py parser.py transcript.py codex_client.py tracking.py evaluate.py   # copied from v1
    llm.py              # v1 + spend cap hook
    models.py           # v1 + new schemas (finder v2, editor, audience) and dataclasses
    validate.py         # v1 rules unchanged
    prompts.py          # finder v2, screen, editor, audience prompts (each with its own version string)
    finder.py           # v1 + coverage check
    screen.py           # v1 judge, generalised to batch all candidates; shortlist
    editor.py           # NEW: builds scene context, asks for versions / refinements
    audience.py         # NEW: renders numbered clips, calls the simulated audience, validates replies
    engagement.py       # NEW: pure score maths (curve, components, blend)
    tournament.py       # NEW: versions → audience → pick → refine → reliability
    budget.py           # NEW: shared spend tracker and cap
    slate.py            # NEW: 70/20/10 posting slate
    report.py pipeline.py cli.py   # extended
  tests/                # v1 tests copied + new tests, synthetic fixtures only
  docs/
```

## 5. Stages

### 5.1 Parse, validate (unchanged from v1)

Same parser and validator. The validator already allows a "cold open" (first segment later in the episode than the
second) because it only forbids overlap; v2 relies on that for the structure change.

### 5.2 Find v2

Prompt changes from v1:
- Defines the four engines: **explosive** (confrontation, slap, public humiliation, power reversal), **funny**
  (something wrong but harmless: absurd situations, sharp comebacks, awkwardness), **puzzling** (a mystery: who, why,
  what), **shocking** (a reveal that overturns what the viewer believed).
- Each candidate names its `engine`, a `sinker_question` and 2–4 `sinker_answers` (believable answers). If the model
  can't name several answers, the ending is too obvious.
- The sinker question must be answered later in the show (no fake-outs).
- Drops the 1–5 self-scores: in v1, 92 of 93 hooks were self-rated 4–5, so they ranked nothing.

Candidate schema (v2): `title, segments[1..3], hook_ref, hook, cliffhanger_ref, cliffhanger, sinker_question,
sinker_answers[2..4], engine, why, spoiler_risk`. Batching as v1: 5 episodes per call, 2 candidates per episode.

**Coverage check (code):** episodes with zero valid candidates are listed in the report, `run_meta.json` and W&B
(`episodes_without_promo`). No automatic re-ask (YAGNI).

### 5.3 Screen and shortlist

The v1 cold-viewer judge prompt, unchanged in spirit, applied to **all** valid candidates in batches of 30, shuffled
with the run seed. It returns `overall` 1–5 per clip.

Shortlist (code): order by `overall` + 0.25 if the first segment is in episodes 1–10 (v1 assumption), then take the top
K = 12 with **at most one per episode** and no two sharing more than half their footage.

### 5.4 Versions (editor)

For each shortlisted moment the editor sees: the moment's blocks plus 30 s of context before and after each segment
(same episode), the original version, and the screen's `understood` / `confusing` notes. It returns N = 3 new
versions, each changing **one** variable, preferring a different variable per version:

- `hook`: a different opening block;
- `sinker`: a different ending block, usually cutting earlier at a stronger open question;
- `length`: a tighter (~25 s) or fuller (~50 s) cut;
- `structure`: a cold open (climax first, then rewind to the build-up), or joining 2–3 moments.

Each version carries the full candidate fields plus `change` (one of the four). The brief is written in AIDA terms and
repeats the no-fake-out rule. Batched 3 moments per call. The original counts as version 0, so each moment has up to
4 versions. Invalid versions are dropped with the validator's reason.

### 5.5 Simulated audience

System prompt: two viewers scrolling Reels with sound on, both new to this show:
- **Viewer A (weight 0.65):** a woman aged 25–44 who scrolls Reels in short breaks and likes romance and revenge drama.
- **Viewer B (weight 0.35):** someone who doesn't usually watch romance dramas and only stops for something explosive,
  funny, puzzling or shocking.

Persona text lives in `prompts.py`; weights are settings (`--audience-weight 0.65`).

Input: 8 clips per call, shuffled across moments with the run seed (versions of one moment don't sit together), with
no title, show context or editor notes. Each clip is rendered as numbered lines with clip-relative times:

```
### CLIP C03
L01 [+00.0-02.4] ACTION: ...
L02 [+02.4-05.1] NAME: ...
--- CUT ---
L03 [+05.1-08.0] ...
```

Reply (compact, to keep output tokens low):

```json
{"clips": [{
  "clip": "C03",
  "understood": "one sentence: what is happening",
  "beats": [["L01", "shock", 3, 10, 30], ["L02", "anger", 2, 5, 12]],
  "question": "the question in the viewer's head at the end",
  "next": [["what might happen next", 40], ["...", 35], ["...", 25]],
  "need_next": [5, 3]
}]}
```

- `beats`: one entry per line: line id, emotion, strength 0–3, % chance viewer A / viewer B scrolls away during it.
- Emotions: `shock, anger, amusement, intrigue, tension, joy, sadness, boredom, confusion, none`.
- `next`: 2–4 imagined next scenes with likelihoods (normalised to sum 1 in code).
- `need_next`: how badly viewer A / viewer B needs to know what happens next, 1–5.

Validation (pydantic + code): every line id appears exactly once, values in range. A reply that fails is retried with
feedback (existing `complete_json` loop). If a clip still fails, it is marked **unscored** (never guessed).

### 5.6 Engagement score (pure code, `engagement.py`)

Per viewer v ∈ {A, B}, from the line timings and the reply:

- **Survival curve:** S(t) = product of (1 − leave_v,i / 100) over every line i whose start time is before t
  (a viewer can leave during any line that has begun). A per-second curve S(0), S(1), … S(duration) is stored for the report and W&B.
- **Hook** = S(3.0). **Completion** = S(end).
- **Punch** (shared by both viewers): engine map anger→explosive, amusement→funny, intrigue→puzzling, shock→shocking.
  Peak = highest strength among lines with those emotions; the promo's measured engine is the one holding the peak
  (earliest wins ties). Punch = peak / 3, plus 0.1 if a shock or intrigue of strength ≥ 2 starts within the first 3 s,
  plus 0.1 if the dominant emotion changes at least twice between lines of strength ≥ 2. Capped at 1.
- **Sinker** = ((need_next_v − 1) / 4) × (0.5 + 0.5 × spread), where spread = entropy of the normalised `next`
  likelihoods divided by log(n). One obvious answer halves the sinker part.
- **Confusion penalty** (shared) = 15 × mean over lines of (confusion strength / 3), so at most 15 points.

Viewer score = 25·Hook + 25·Completion + 25·Punch + 25·Sinker − penalty, clipped to 0–100.
**Engagement** = 0.65 × A + 0.35 × B.

Equal weights are a stated assumption (no data to weight otherwise). Every component is stored per version so the
weights can later be fitted to real hook rate / completion once promos are posted.

### 5.7 Pick, refine, reliability (`tournament.py`)

- **Pick:** for each moment, the highest-engagement scored version wins (ties: shorter). Moments are ranked by their
  winner; the v1 footage-overlap dedupe runs on winners.
- **Refine (R = 5):** the editor gets each top-5 winner with diagnostics computed in code: the line with the biggest
  drop and its emotion, the sinker spread and its top answer's likelihood, any confusion lines. It returns one improved
  version per moment (any change type). These are validated and scored in one audience call; an improved version
  replaces the winner only if it scores higher.
- **Reliability (S = 8):** the top 8 winners are re-scored in one call with a different shuffle (seed + 1). Report
  Spearman rank correlation and mean absolute score change between the two passes.

### 5.7a Head-to-head duels (`duels.py`, added after the first full runs)

**Why:** one absolute audience pass proved too noisy to pick between versions of a moment. The same 23 versions scored
in two runs agreed at r = 0.18, ordered a pair of versions the same way only 61% of the time (chance is 50%), and
picked the same winner in 1 of 6 moments. Judges are usually far more consistent at "A or B?" than at absolute scores.

**How:**
- For each moment, every pair of scored versions is a duel: the same two blind viewers see cut X and cut Y and each
  picks the cut they would engage with more (stop in the first 3 s, watch to the end, need the next episode). Each
  duel gives a one-line reason first, then the two picks.
- Each pair is judged twice, once in each order, in different calls, so a bias towards the first (or second) cut
  cancels out. Which cut goes first in the first pass is random (seeded). 12 duels per call.
- **Win share** of a version = its share of picks across its duels, weighted 0.65 viewer A + 0.35 viewer B.
  The winner is the highest win share; ties go to the higher absolute score, then the shorter cut.
- **Refine:** the improved version duels the current winner in both orders and replaces it only with a win share
  above 0.5.
- Absolute scores stay: they drive the refine diagnostics, the curves and AIDA view in the report, the posting slate
  and the ranking across moments (duels only compare cuts of the same moment).
- A missing or invalid duel is retried once in a smaller call; if it fails again it is left out. If a moment has no
  judged duels, its winner falls back to the highest absolute score. `--no-duels` gives the old behaviour.

**Self-checks (run_meta, report, W&B):** order agreement (share of pair × viewer judgments that picked the same cut
in both orders; 50% is chance, absolute scores managed 61%), first-shown win rate (0.5 = no position bias), and how
often the duel winner equals the top absolute score.

**Cost:** about 66 pairs × 2 orders ≈ 132 duels in ~11 calls, plus one refine call pair, at about $0.20 per call:
≈ $2.50. Earlier stages hit the cache when the settings are unchanged.

### 5.8 Posting slate (`slate.py`, 70/20/10)

From the ranked winners, a slate of up to 10:
- **Proven (~7):** highest engagement.
- **Challengers (~2):** best-scoring winners whose measured engine isn't yet in the slate.
- **Wild card (1):** highest viewer-B score not already in the slate.

If there aren't enough distinct engines or winners, the remaining slots fall back to the next-highest engagement.

### 5.9 Reporting and tracking

Outputs per run (`outputs/<show>/<run_id>/`):
- `promos.json` / `promos.csv`: ranked winners with segments, hook, sinker question and answers, engine, components,
  engagement, slate role.
- `versions.json`: every version (incl. invalid/unscored with reasons), components, per-second curves, change type.
- `report.md`: slate first (pyramid principle); per promo: timestamps, hook → sinker, the four parts, a sparkline per
  viewer (e.g. `A ▇▇▆▆▅▅▄`), an emotion timeline ("0–3 s shock → 3–15 s anger → …") labelled with AIDA stages,
  and the version history with score deltas.
- `rejected.json`, `raw_llm.jsonl`, `run_meta.json` (counts, coverage, reliability, spend, cap status).

W&B (numbers and labels only, never screenplay text): config incl. prompt versions and weights; counts per stage;
engagement distribution; win rate per change type; refine uplift; reliability stats; coverage; spend vs cap; a table
of winners with timestamps, engine, components and slate role.

## 6. Cross-cutting

### 6.1 CLI

`promo-finder-v2 run --input <folder>` with v1 options plus `--shortlist 12 --versions 3 --refine-top 5
--reliability 8 --audience-weight 0.65 --max-cost 5`. `eval` is kept for future editor labels.

### 6.2 Error handling

- Broken JSON: retried with feedback (v1 behaviour).
- Finder or screen batch fails after retries: logged, run continues with what it has (v1 behaviour).
- Editor batch fails: those moments keep only their original version.
- Audience clip fails validation twice: marked unscored; can't win.
- Spending cap reached: the current stage stops, later stages are skipped, outputs are written and the W&B run is
  tagged `partial`.

### 6.3 Spending cap (`budget.py`)

One `Budget(cap_usd)` shared by every `LLM`. Spend is the token-based estimate with the configured prices (it ran
~20% above actual billing in v1, so it errs safe). Before each non-cached call, if `spent + max_call_cost > cap`
(`max_call_cost` default $0.30), it raises `BudgetExceeded`. Cached replies cost nothing.

### 6.4 Testing

- v1 tests copied and kept green.
- New unit tests with a fake LLM (no network, no cost): finder v2 schema and coverage, screen batching and shortlist
  rules, editor parsing and change types, audience reply validation (missing / duplicate lines, ranges), engagement
  maths against hand-worked examples (survival, hook at 3 s, entropy spread, punch bonuses, penalty, blend), pick /
  refine replacement rule, reliability statistic, slate roles and fallbacks, budget cap, end-to-end pipeline.
- Then a 5-episode dev run (W&B tag `dev`), then the full run (tag `submission-v2`); the v1 submission run gets a
  `superseded` note.

### 6.5 Budget plan

| Stage | Calls (full run) | Est. cost |
|---|---|---|
| Find v2 | 10 | $1.90 |
| Screen | ~4 | $0.35 |
| Versions | 4 | $0.50 |
| Audience | ~6 | $0.90 |
| Refine (editor + audience) | 2 | $0.30 |
| Reliability | 1 | $0.15 |
| **Full run** | ~27 | **≈ $4.10** |
| Dev runs (5 episodes, partly cached) | | ≈ $1.50 |

### 6.6 Docs

v2 README (how it works, settings, scoring, frameworks, limits); a v2 solution doc within 2 pages (answer first,
results, how the score works, reliability, failure modes as an issue tree, unit economics, research sources); the AI
log continues.

## 7. Limits and out of scope

- Script only: can't judge visuals, acting or whether script times match the final cut.
- One model creates and scores; blind shuffled scoring and the reliability check limit but don't remove the bias.
- AI viewers agree weakly with real viewers; the score ranks versions, it doesn't forecast exact metrics.
- Weights are uncalibrated until real post-launch metrics exist.
- Cross-episode near-duplicate beats are only limited by "one moment per episode", not detected.
- No automatic captions, music or narration; no video rendering.
