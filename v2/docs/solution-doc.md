# Promo Finder v2: Kuku AI Generalist, Problem 1

**Nithish Ravikkumar** · Roll no. 23123028

## The answer

v2 doesn't just find promos, it tests them. For each strong moment it cuts three more versions (new opening, new
ending, new length or structure), scores every version with a blind, simulated two-viewer audience, line by line, and
keeps the winner. On the 50-episode pack: 93 promos found → 12 moments tested in 51 versions → **a re-cut beat the
original in 9 of 12 moments** (+6 points on a 0–100 engagement score). The key lesson: **one scoring pass is too noisy
to pick between versions** (23 versions scored twice agree at r = 0.18; the same winner in only 1 of 6 moments).
Averaged over both passes, re-cuts still win in 5 of 6, by smaller margins. Next step: pairwise or averaged scoring.

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
  → engagement score (code) → best version → refine top 5 → posting slate + report + W&B
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
| 1 | E18 00:00.0–00:43.5 (44 s, original) | Flames under her door as she wakes choking → how will they escape the burning cottage? | 82.0 (83.2 / 80.0) |
| 2 | E41 01:21.0–01:36.1 + E42 00:11.2–00:28.8 (33 s, refined) | A blast tears open the cathedral entrance → who is the stranger the royal guards refuse to arrest? | 81.9 (85.7 / 74.9) |
| 3 | E36 02:10.8–02:46.8 (36 s, new sinker) | He learns his wife is condemned → will he go back alone to save her? | 79.9 (84.5 / 71.2) |

- **Funnel:** 93 proposed → 92 passed the rules → 12 shortlisted → 39 editor versions (2 more rejected) + 12
  originals, all scored → 5 refined → 12 winners → a 10-promo slate. Finder engines: 37 explosive, 37 shocking,
  18 puzzling; the audience still felt "funny" peaks in 2 winners.
- **Version types that won:** length 3 of 6, hook 3 of 11, original 3 of 12, sinker 2 of 11, refine 1 of 5, structure
  0 of 6 (cold opens had won 3 of 4 in the first pass: noise). Newcomers (B) score 3–18 points below viewer A.
- **Calibration mattered:** in the first test the AI audience gave punch 1.0 to all 14 versions; with anchored scales
  ("strength 3 is rare") punch ranged 0.67–1.0 and sinker 0.68–0.87, so all four parts rank.

## How I know it's good, and where it fails

- **Rules by construction:** every cut lands on a block edge (checked for the top two); 86 unit tests with fake models.
- **Reliability (the weak link):** 23 versions scored in two runs: r = 0.18, mean change 5.0 points, max 19.5; 8
  winners re-scored in the same run: rank correlation 0.17. By Spearman-Brown, ~5 averaged passes would reach about
  0.5. Picking the best of 4–5 noisy scores also inflates winners, so the +6 gain is partly selection.
- **Where it picks badly (issue tree):**
    1. *Wrong moment:* the finder labelled no promo funny; episodes 6, 10 and 17 got none (10 episodes per call).
    2. *Wrong cut:* completion falls with every line, so a long cut must earn its length.
    3. *Weak ending:* imagined answers stay evenly spread (0.8–0.95), so the sinker part separates little.
    4. *Wrong audience:* the simulated viewer reads speaker names a real viewer never sees; published tests find AI
       viewers agree only weakly with humans (ICC 0.14 vs 0.29 human–human).
    5. *Model bias:* one model finds, edits and scores. The refine round lost in 4 of 5 moments (mean −12 points).

## Unit economics and scale

- **Per show:** about $6–7 and 35 min for 12 moments on this gateway (~$0.55 per tested moment). Most cost is hidden
  reasoning tokens plus ~17K tokens of Codex instructions per call; a direct API removes that overhead.
- **Next:** replace absolute scores with blind pairwise duels between versions of one moment (both orders, to cancel
  position bias), or average 5 passes; then fit the four weights to posted promos' real hook rate and completion.

## AI tools used, and where they got it wrong

- **Claude Code:** research, design, plan, code, tests. **gpt-5.6-sol:** finder, screen, editor, audience.
- **Where AI got it wrong:** the AI audience rated almost everything at the top of every scale (fixed with anchors), and
  its scores proved too noisy to pick versions (caught by re-scoring); Claude's first budget missed hidden reasoning
  tokens. Log: `v2/docs/ai-log.md`.

**Sources:** Teixeira, Wedel & Pieters, *JMR* 2012 · Ely, Frankel & Kamenica, *JPE* 2015 · Berger & Milkman, *JMR*
2012 · Warren & McGraw, *PNAS* 2015 · Fong, arXiv 2412.15239 · AppGrowing (ReelShort) · AdMapix (DramaBox) · Meta ×
Kuku TV playbook (Storyboard18, 2026).
