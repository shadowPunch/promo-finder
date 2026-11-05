# Promo Finder: Kuku AI Generalist, Problem 1

**Name** · **Roll no** · **Branch** · Repo (with run steps): `<link>` · Raw outputs (Drive): `<link>` · Video: `<link>`

## Why this problem

Picking promos is the most repetitive editor task in microdrama. Every episode of every weekly show gets watched just to
find 20–60 s clips. The output can be checked (exact timestamps, a 3-second hook, an unresolved ending), and it feeds
user acquisition directly. A good tool turns hours of watching per show into a short review of a ranked list.

## Assumptions

1. Screenplay timestamps match the final cut closely enough for an editor to trim from.
2. "Hook in the first 3 s": the hook line or action starts ≤ 3.0 s after the clip starts.
3. "Ends on a cliffhanger": the clip ends on the cliffhanger block, with at most 2 s of tail.
4. 1–3 segments, 20–60 s in total. Joins across episodes only within one batch of 5 consecutive episodes.
5. Earlier episodes get a small bonus (+0.25 for episodes 1–10), because an ad should land a new viewer at the start of
   the show. This is a bonus, not a filter.
6. Viewers never see character names, so "makes sense on its own" can't rely on them.
7. Model: `gpt-5.6-sol` via AgentRouter with a $10 quota, the access I had. AgentRouter only serves approved agent
   clients, so the tool sends prompts through the real Codex CLI. An `openai` backend covers any normal API.
8. The pack is confidential: it is never committed or logged to W&B, and goes only to the model provider.

## How it works

```
parser (code) → finder (LLM, 5 episodes/call) → validator (code) → scorer + dedupe (code)
             → cold-viewer judge (LLM) → ranker (code) → JSON/CSV/report + W&B run → editor review (human)
```

- **AI does the taste:** it proposes promos and scores hook, cliffhanger and standalone. A second "cold-viewer" pass
  sees only the clip text, with no show context, and says what it thinks is happening and whether it would keep watching.
- **Code does everything checkable:** the model cites block ids (`E03L045`), never timestamps. Code turns ids into exact
  times and enforces the rules: 20–60 s, hook ≤ 3 s, end on the cliffhanger, no line cut mid-sentence. It applies small
  repairs automatically and rejects anything else with a reason. It also scores, dedupes and ranks.
- **Ranking:** `0.4·hook + 0.3·cliffhanger + 0.3·standalone − spoiler penalty + early bonus`, plus the judge's 1–5. The
  hook weighs most because an ad that doesn't stop the scroll is never watched.
- **Human in the loop:** the editor reviews the ranked list (report or local app), marks post / maybe / reject, and
  checks timing against the video. Those labels are the eval set.
- **Swappable model:** two backends behind one interface. Switching model or provider is a `.env` edit.

## Results on the 50-episode pack

One run over all 50 episodes (W&B run `k3ehwr16`, raw outputs in the Drive folder):

- **97 proposed → 95 passed the rules → 93 unique.** Rejected: one at 19.4 s (too short), and one whose hook landed past
  3 s once the cut was widened to keep a line whole. Durations run from 20.2 to 59.7 s (median 37 s). 80 are single
  stretches, 13 join 2–3 moments, and 2 of those cross episodes.
- **Cost and time:** 11 model calls (10 finder, 1 judge), 18 min 46 s, **$2.18 billed**. That's 417K input tokens, of
  which ~186K are Codex's fixed instructions, plus 80K output tokens.

**Post these first:**

| # | Segments | Hook → cliffhanger | Why first |
|---|---|---|---|
| 1 | E05 00:54.0–01:04.6 + 01:09.0–01:40.8 (42 s) | Stepfamily throws the heroine's late mother's keepsake into the mud → her quiet new husband turns on her ex-fiancé | Judge 5/5. Public humiliation plus a protector, which is the show's promise. The 4 s skipped between segments tightens it. |
| 2 | E01 00:33.8–01:14.3 (40 s) | Bride sees her groom holding another woman's hand at the altar → cuts before she learns how long it's been going on | Judge 4/5. Needs zero context, and it's episode 1, so viewers start at the beginning. |
| 3 | E10 00:02.1–00:28.0 (26 s) | Husband bursts in covered in blood → cuts before the wound is revealed | Judge 4/5. A different trope (danger) from #1–2, so the three test which hook type converts. |

## How I know it's good, and where it fails

- **Rules hold by construction:** every cut lands on a real block edge, and the hook, length and ending rules are checked
  in code (50 unit tests). I hand-checked two promos' start and end times against the screenplay, and both were exact.
- **The cold-viewer judge separates promos; self-scores don't.** The finder rated its own hook 4–5 on 92 of 93 promos,
  and standalone 4–5 on all of them, so its scores barely rank anything. The judge, which sees only the clip, spread its 15
  verdicts from 2 to 5 (mean 3.3). It's the judge that orders the top of the list.
- **Human check:** _(after labelling the top 20: precision@5 / @10 for "post" and "post or maybe", the reject-reason
  counts, and the mean judge score for "post" vs "reject" from `eval.json`)_
- **Where it picks badly (seen in this run):**
  1. *Near-duplicate beats:* #2 and #7 are both the altar rejection (episodes 1 and 2). #5 and #8 overlap for 6 s in
     episode 7. Dedupe only catches promos that share over half their footage.
  2. *Optimistic "standalone":* the judge's summaries use character names, which a scrolling viewer never sees, so
     clarity is overrated. Its own "unclear" notes often flag a relationship that isn't set up in the clip.
  3. *Same model as finder and judge:* the key allows one model, so the judge may favour its own picks.
  4. *Script, not video:* it can't tell whether a visual hook lands, or whether script times match the final cut.

## Scale to every show

- **Per show:** ~11 calls, ~19 min and ~$2 on this setup. Running the 10 finder calls in parallel would bring it to about
  2 min. Codex's fixed instructions are ~45% of the input tokens, so with the `openai` backend on a direct API (e.g.
  Kuku's own), the same run sends roughly half the input.
- **Weekly pipeline:** one job per new show folder; ranked promos go to the editor's review queue (CSV or the local app).
  Editor decisions accumulate as labels. They become a regression test whenever the prompt or model changes, and later
  few-shot examples.
- **Not yet handled:** merging similar beats across episodes, other languages (the parser is format-based, the prompts
  are English), and checking against the actual video.

## AI tools used, and where they got it wrong

- **Claude Code** wrote the design, plan, code and tests. I reviewed the decisions and steered the model choice.
- **gpt-5.6-sol** (via Codex CLI) is the product's finder and judge.
- **Where AI got it wrong:** Claude's build plan pointed `pyproject.toml` at a README it only created in the last task,
  so the first install failed. Its smoke-test snippet also called `load_dotenv()` in a way that crashes when Python reads
  code from stdin. Both were caught by running the steps, not by reading them. Full log: `docs/ai-log.md`.
