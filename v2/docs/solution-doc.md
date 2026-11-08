# Promo Finder v2: Kuku AI Generalist, Problem 1

**Nithish Ravikkumar** · Roll no. 23123028

## The answer

v2 doesn't just find promos, it tests them. For each strong moment it cuts three more versions (new opening, new
ending, new length or structure), scores every version with a blind, simulated two-viewer audience, line by line, and
keeps the winner. On the 50-episode pack: 93 promos found → 6 moments tested in 23 versions → **a re-cut beat the
original in 5 of 6 moments** (+5.7 points on a 0–100 engagement score), and **cold opens won 3 of the 4 times they were
tried**. One full run: 26 min, $4.72. Caveat: re-scoring the same clips moves scores by ~3.9 points, so small gaps are
noise.

## Assumptions

1. Script only; promos are cut straight from episodes (no narration, music or text), 20–60 s, hook ≤ 3 s, ending on the
   sinker. Code owns every timestamp and rule; the model only cites block ids.
2. The score *predicts* platform metrics (hook rate, completion, click-through); true numbers exist only after posting.
3. Audience: 65% the likely ad audience (women 25–44 who like romance and revenge drama), 35% newcomers. One model
   (`gpt-5.6-sol` via AgentRouter, through the Codex CLI) does every AI step, under a spending cap in code.

## How it works

```
find (LLM) → rule checks → quick screen (LLM) → shortlist (1 per episode)
  → 3 versions each (LLM editor) → simulated audience (LLM, blind, line by line)
  → engagement score (code) → best version → posting slate + report + W&B
```

- **Finder:** each promo names its engine (explosive, funny, puzzling or shocking) and a *sinker*: one open question
  with 2–4 believable answers that the show really answers later (no fake-outs).
- **Simulated audience:** for every line, the emotion, its strength (0–3) and the % of each viewer who scrolls away;
  at the end, 2–4 imagined next scenes with likelihoods and "need to know what happens next" (1–5).
- **Engagement (per viewer, 0–100):** 25 × hook (share still watching at 3 s) + 25 × completion + 25 × punch (peak of
  the strongest engine, bonus for an early surprise or rising and falling emotion) + 25 × sinker (need-to-know ×
  spread of the imagined answers) − up to 15 for confusion. Blend: 0.65 × viewer A + 0.35 × viewer B.
- **Research basis:** early surprise holds attention, rising joy retains (Teixeira et al. 2012); suspense = how much
  the next moment could change beliefs (Ely et al. 2015), estimated from imagined continuations (Fong 2024).

**Business frameworks:** score parts = **AIDA**; engagement = a **North Star** whose drivers map to platform metrics;
65/35 viewers = **STP/Ansoff**; cheap-wide then expensive-narrow = **stage-gate**; one change per version =
**test-and-learn**; a **70/20/10** posting slate; no fake-out sinkers = **jobs to be done**.

## Results on the 50-episode pack

| # | Segments | Hook → sinker | Score (A / B) |
|---|---|---|---|
| 1 | E18 01:03.0–01:08.0 + 00:36.5–01:02.5 (31 s, cold open) | Burning beams split overhead → will she flee, or risk everything for the ledger? | 76.7 (79.7 / 71.0) |
| 2 | E28 01:01.3–01:10.2 + 01:26.5–02:08.7 (51 s, cold open) | The only witness to the poison is the maid → can the accused stop her mother's book condemning her? | 72.0 (75.2 / 66.1) |
| 3 | E36 02:10.8–02:43.0 + 02:59.5–03:16.8 (50 s, original) | He learns his wife is condemned to die → what will he do at the wedding before her execution? | 70.1 (72.8 / 65.1) |

- **Funnel:** 93 proposed → 92 passed the rules (1 hook landed late) → 6 shortlisted → 17 editor versions + 6
  originals, all scored → 6 winners. Engines found: 37 explosive, 37 shocking, 18 puzzling, 0 funny.
- **What the tournament learned:** winning change type: structure 3 of 4, hook 1 of 5, sinker 1 of 6, original 1 of 6,
  length 0 of 2. Newcomers (B) score 8–15 points below the core audience (A) on every winner.
- **Calibration mattered:** in the first test the AI audience gave punch 1.0 to all 14 versions; with anchored scales
  ("strength 3 is rare") punch ranged 0.67–1.0 and sinker 0.68–0.87, so all four parts rank.

## How I know it's good, and where it fails

- **Rules by construction:** every cut lands on a block edge (checked for the top two); 86 unit tests with fake models.
- **Reliability:** the 6 winners re-scored in a new order: rank correlation 0.43, mean change 3.9 points. Picking the
  best of 3–4 noisy scores also inflates a winner by ~3 points, so only part of the +5.7 gain is real. Next step:
  average 2–3 audience passes per version.
- **Where it picks badly (issue tree):**
    1. *Wrong moment:* no funny moments; episodes 6, 10 and 17 got no promo (10 episodes per call lets some slip).
    2. *Wrong cut:* completion falls with every line, so a long cut must earn its length.
    3. *Weak ending:* imagined answers stay evenly spread (spread 0.8–0.95), so the sinker part separates little.
    4. *Wrong audience:* the simulated viewer reads speaker names a real viewer never sees; AI viewers agree only weakly
       with humans in published tests (ICC 0.14 vs 0.29 human–human).
    5. *Model bias:* one model finds, edits and scores. The refine round lowered scores in both tests and was cut for
       budget, as were 6 of the 12 planned moments, so the 70/20/10 slate had no challengers yet.

## Unit economics and scale

- **Per show:** $4.72 and 26 min for 6 tested moments (~$0.79 per tested promo). Most cost is hidden reasoning tokens
  plus ~17K tokens of Codex instructions per call; a direct API (e.g. Kuku's own) removes the overhead.
- **Weekly pipeline:** one job per new show; an editor reviews the slate; posted promos' real hook rate and completion
  fit the four weights.

## AI tools used, and where they got it wrong

- **Claude Code:** research, design, plan, code, tests. **gpt-5.6-sol:** finder, screen, editor, audience.
- **Where AI got it wrong:** the AI audience rated almost everything at the top of every scale (fixed with anchors);
  Claude's budget missed hidden reasoning tokens ($4.10 planned vs $5.70 projected), so the run was slimmed to 6
  moments. Log: `v2/docs/ai-log.md`.

**Sources:** Teixeira, Wedel & Pieters, *JMR* 2012 · Ely, Frankel & Kamenica, *JPE* 2015 · Berger & Milkman, *JMR*
2012 · Warren & McGraw, *PNAS* 2015 · Fong, arXiv 2412.15239 · AppGrowing (ReelShort) · AdMapix (DramaBox) · Meta ×
Kuku TV playbook (Storyboard18, 2026).
