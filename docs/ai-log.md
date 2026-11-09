# AI usage log

Kept during the build; the solution doc asks which tools were used and where they got it wrong.

Tools used:
- Claude Code: research, design spec, implementation plan, code, tests and the showcase site
- gpt-5.6-sol via AgentRouter, run through the Codex CLI: the product's finder, quick screen, promo editor and
  simulated audience

## Where AI got it wrong

| Date | Tool | What it got wrong | How it was caught | Fix |
|------|------|-------------------|-------------------|-----|
| 2026-11-06 | Claude Code | The build plan set `readme = "README.md"` in pyproject.toml but only wrote README.md in the last task, so `uv sync` failed on the first step | `uv sync` build error | Added a stub README in the first task |
| 2026-11-06 | Claude Code | The plan's smoke-test snippet called `load_dotenv()` from `python -` (stdin), where python-dotenv cannot locate the caller and crashes | AssertionError in `find_dotenv` | Use `load_dotenv(".env")` there; CLI and app use `find_dotenv(usecwd=True)` |
| 2026-11-08 | gpt-5.6-sol (simulated audience) | Rated almost every clip at the top of every scale: punch 1.0 on all 14 versions, viewer-A sinker 0.94-0.99, so two of the four score parts ranked nothing (the same leniency the finder's self-scores showed in the first version) | Reading the score components of the 5-episode dev run | Calibrated the prompt with anchors ("strength 3 is rare, at most one line per clip"; "need-to-know 5 is about 1 clip in 10"; honest 80/20 likelihoods). Punch then ranged 0.67-1.0 and sinker A 0.68-0.87 |
| 2026-11-08 | Claude Code | The design budgeted the full run at ~$4.10 from the first version's numbers, but the audience and editor calls produce ~8-10K hidden reasoning tokens each; the measured projection was ~$5.70, more than the credit left | Billing delta of the dev run ($1.30 for 5 episodes) | Fewer, larger calls (10 episodes per finder call, 50 promos per screen call), 6 moments instead of 12, cap at $4.90 |
| 2026-11-08 | Claude Code | Two plan tests had wrong expectations: a report string missed the Markdown bold (`**Still watching:**`) and the expected test count was off by one | Running the tests | Fixed the test string; counts noted |
| 2026-11-08 | Claude Code | The spending cap reserved $0.30 per call, so a $1.00/$1.50 dev cap blocked the last (reliability) call even though real spend was well under | Dev runs ended `partial` | Dev caps set with that headroom in mind; documented |
| 2026-11-08 | gpt-5.6-sol (simulated audience) | Its scores were too noisy to pick between versions of one moment: 23 identical versions scored in two runs agreed at r = 0.18 (mean change 5.0 points, max 19.5), and the same winner came out in only 1 of 6 moments. The first run's "cold opens win 3 of 4" was noise (0 of 6 in the second) | Comparing the 6-moment and 12-moment runs, which re-scored the same versions | Winners now picked in one-on-one comparisons, each pair in both orders (`duels.py`): the two orders agree on 86% of picks (absolute scores: 61% of pairs), first-shown cut wins 49%, each order alone picks the same winner in 8 of 12 moments |
| 2026-11-08 | Claude Code | Estimated the comparison stage at ~$2.50 (12 calls); it took 14 calls, because each order of the refine comparisons needs its own call, and each call carried ~30K prompt tokens (24 clips plus Codex instructions). Billed $2.94 | Billing delta after the run | Cost noted in the doc; the cap ($4) held with room to spare |
| 2026-11-09 | Claude Code | The showcase demo player's DOM helper passed plain text to `appendChild`, so the Audience and Compare stages rendered empty; it also first laid the excerpt's script lines out in a squeezed column (the page sanitiser dropped a wrapper element) | Headless-Chrome screenshots of every page and every demo stage, at desktop and phone widths | Helper switched to `append` (takes text and nodes); script lines placed with CSS grid, no wrapper; every stage re-shot until clean |
| 2026-11-09 | gpt-5.6-sol (editor) | On the artificial demo show, 4 of its 12 re-cuts broke the rules (2 overlapping segments, 2 malformed replies) | The code's rule checks rejected them | Shown in the demo's Versions stage as rejected cuts; the remaining 8 re-cuts were scored and compared |
