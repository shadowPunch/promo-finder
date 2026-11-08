# Promo Finder v2: Kuku AI Generalist, Problem 1

**Nithish Ravikkumar** · Roll no. 23123028

## The answer

v2 doesn't just find promos, it tests them. For each strong moment it cuts three more versions (new opening, new
ending, new length or structure). A blind, simulated two-viewer audience scores every version line by line, then picks
the best cut of each moment in **head-to-head duels**. On the 50-episode pack: 93 promos found → 12 moments tested in
50 versions and 140 duels → **a re-cut beat the original in 7 of 12 moments**. The lever that works is a stronger
opening (it won 5 of 11 tries); new endings, lengths and cold opens won none. The duels are what make this trustworthy:
absolute scores were too noisy to pick a winner (same winner in 1 of 6 moments across two passes), while each duel
order alone picks the same winner in 8 of 12.

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
  → engagement score (code) → head-to-head duels, both orders (LLM) → winner
  → refine top 5 (must win its duel) → posting slate + report + W&B
```

- **Finder:** each promo names its engine (explosive, funny, puzzling or shocking) and a *sinker*: one open question
  with 2–4 believable answers that the show really answers later (no fake-outs).
- **Simulated audience:** for every line, the emotion, its strength (0–3) and the % of each viewer who scrolls away;
  at the end, 2–4 imagined next scenes with likelihoods and "need to know what happens next" (1–5).
- **Engagement (per viewer, 0–100):** 25 × hook (share still watching at 3 s) + 25 × completion + 25 × punch (peak of
  the strongest engine) + 25 × sinker (need-to-know × spread of the imagined answers) − up to 15 for confusion.
  Blend 0.65 A + 0.35 B. It ranks winners across moments, fills the slate and tells the editor what to fix.
- **Duels:** every pair of versions of a moment is shown to the same two viewers, who each pick the cut they'd engage
  with more. Each pair runs twice, once in each order and in separate calls, so a bias towards the first cut cancels
  out. The winner has the highest weighted share of wins.
- **Research:** early surprise holds attention (Teixeira et al. 2012); suspense = how much the next moment could
  change beliefs (Ely et al. 2015), estimated from imagined continuations (Fong 2024).

**Business frameworks:** score parts = **AIDA**; engagement = a **North Star** whose drivers map to platform metrics;
65/35 viewers = **STP/Ansoff**; cheap-wide then expensive-narrow = **stage-gate**; one change per version =
**test-and-learn**; a **70/20/10** posting slate; no fake-out sinkers = **jobs to be done**.

## Results on the 50-episode pack

| # | Segments | Hook → sinker | Score (A / B) · duels won |
|---|---|---|---|
| 1 | E41 01:21.0–01:36.1 + E42 00:11.2–00:28.8 (33 s, refined) | A blast tears open the cathedral → who is the stranger the guards obey? | 78.5 (80.5 / 74.9) · 100% |
| 2 | E36 02:14.5–02:43.0 + 02:59.5–03:16.8 (46 s, new hook) | He learns his wife will be executed → what will he do at the wedding? | 72.2 (77.0 / 63.3) · 91% |
| 3 | E12 00:57.3–01:24.7 (27 s, new hook) | Ordered to fetch it with bare hands → can she survive and save her husband? | 72.0 (77.1 / 62.6) · 73% |

- **Funnel:** 93 proposed → 92 valid → 12 shortlisted → 50 versions scored (12 originals, 34 re-cuts, 4 refined)
  → 140 duels (70 pairs × 2 orders, none lost) → 12 winners → a 10-promo slate.
- **Version types that won:** hook 5 of 11, original 5 of 12, refine 2 of 4, length 0 of 6, sinker 0 of 11,
  structure 0 of 6. Duels changed the pick in 9 of 12 moments; newcomers (B) score 6–16 points below viewer A.

## How I know it's good, and where it fails

- **Rules by construction:** every cut lands on a block edge; 96 unit tests with fake models.
- **Picking is reliable now (the earlier weak link):**

  | Check | Absolute scores | Duels |
  |---|---|---|
  | Same order for a pair of versions, judged twice (chance 50%) | 61% | 86% (A 83%, B 89%) |
  | Same winner from two independent judgments | 1 of 6 moments | 8 of 12 (half the evidence each) |
  | Bias towards the first-shown cut (none = 50%) | n/a | 49% |

- **Where it picks badly (issue tree):**
    1. *Wrong moment:* the finder labelled no promo funny; episodes 6, 10 and 17 got none (10 episodes per call).
    2. *Wrong cut:* only openings helped; the editor's new endings, lengths and cold opens never won a duel.
    3. *Wrong ranking across moments:* duels compare cuts of one moment; slate order still uses absolute scores
       (rank correlation 0.12–0.17 between passes), so close slate ranks are ties.
    4. *Wrong audience:* the simulated viewer reads speaker names a real viewer never sees; published tests find AI
       viewers agree only weakly with humans (ICC 0.14 vs 0.29 human–human).
    5. *Model bias:* one model finds, edits and judges. Refined cuts won 2 of 4 duels though absolute scores had them
       9 points worse: more proof that absolute scores can't pick.

## Unit economics and scale

- **Per show:** about $9–10 and ~45 min for 12 moments: ~$6–7 to find, cut and score, ~$3 for duels (14 calls).
  Most cost is ~17K tokens of Codex instructions per call plus hidden reasoning; a direct API removes that.
- **Next:** duel winners across moments to order the slate; fit the score weights to real hook rate and completion;
  test duel winners against originals in a live A/B.

## AI tools used, and where they got it wrong

**Claude Code:** research, design, code, tests. **gpt-5.6-sol:** finder, screen, editor, audience, duels. **Wrong:**
the AI audience rated nearly everything top of scale (fixed with anchors) and its absolute scores were too noisy to
pick versions (fixed with duels); Claude's budgets missed reasoning tokens. Log: `v2/docs/ai-log.md`.

**Sources:** Teixeira et al., *JMR* 2012 · Ely et al., *JPE* 2015 · Berger & Milkman, *JMR* 2012 · Warren & McGraw,
*PNAS* 2015 · Fong, arXiv 2412.15239 · AppGrowing · AdMapix · Meta × Kuku TV (Storyboard18, 2026).
