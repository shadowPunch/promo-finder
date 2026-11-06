# Promo Finder — Design (Kuku AI Generalist assignment, Problem 1)

Date: 2026-11-06 · Status: draft, awaiting review · Build plan: `docs/superpowers/plans/2026-11-05-promo-finder.md`

## 1. The problem

An editor currently watches every episode of every show to hand-pick promo moments, and Kuku ships new shows every week.
The tool takes a folder of timestamped screenplays and returns a **ranked list of 20–60 s promo clips**. Each clip comes with
the episode and exact start/end time of every segment, the hook, the cliffhanger, and one line on why it works. It must also
be **re-runnable on a new show in the interview**, with the **model easy to swap**.

## 2. The input (measured on the pack)

- 50 `.txt` episodes, each 1:10–3:20 long; 3,727 timed blocks; ~530 KB. In the compact form sent to the model it is
  ~110K tokens: ~2.2K per episode (largest 3.3K), plus ~2.8K for all 50 loglines.
- Each block has a type (`CAMERA` 47%, dialogue 40%, `ACTION` 10%, `SOUND FX` 3%), a `Start: (mm:ss.cc) | End: (mm:ss.cc)`
  line with episode-relative times, and one line of text.
- Header case varies between episodes (`Scene start` vs `SCENE START`). Characters appear under several names (a name, a
  title, a description), so the parser must not rely on names.
- Every file has an `EPISODE LOGLINE`, which gives a free series summary.

## 3. Assumptions (the brief is silent on these)

1. **Script times ≈ cut times.** The tool outputs screenplay timestamps; the editor confirms against the video.
2. **"Hook in the first 3 seconds"** means the hook block starts ≤ 3.0 s after the promo starts.
3. **"Ends on a cliffhanger"** means the promo ends on the cliffhanger block, with at most 2 s of tail (e.g. a reaction shot).
4. **Shape:** 1–3 segments, 20–60 s in total. Cross-episode joins are allowed only between episodes in the same LLM call
   (5 consecutive episodes by default).
5. **Earlier episodes are slightly preferred** (+0.25 for episodes 1–10). An ad should drop a new viewer at the start of the
   story, where apps usually give episodes away free. Late moments need more backstory and risk spoilers. This is a bonus,
   not a filter.
6. **Viewers never see character names** (only faces and lines), so the standalone check must not lean on names.
7. **Model access:** `gpt-5.6-sol` through AgentRouter, with a $10 quota on the user's account. AgentRouter only accepts
   requests from approved agent clients, so the tool sends prompts through the real Codex CLI (see "Model choice").
   No local models.
8. **The pack is confidential.** It is never committed and never sent to W&B. It goes only to the model provider, which
   the brief allows. AgentRouter is a third-party relay, which the solution doc states openly.

## 4. How it works

```
screenplay folder
  │  parser (code): tolerant regexes → Episodes of timed Blocks, each with an id like E03L045
  ▼
finder (LLM): 5 episodes per call + all 50 loglines as context → candidates that cite block IDs, never raw times
  ▼
validator (code): ids → exact times · hook ≤ 3 s · end on cliffhanger · no dialogue cut mid-line · 20–60 s
                  → small repairs are applied automatically, anything else is rejected with a reason code
  ▼
scorer (code): 0.4·hook + 0.3·cliffhanger + 0.3·standalone − spoiler penalty + early-episode bonus; drop overlapping duplicates
  ▼
cold-viewer judge (LLM): sees ONLY the clip text, shuffled, with no show context
                  → "what's happening?", stops-scroll 1–5, needs-next 1–5, overall 1–5
  ▼
ranker (code) → promos.json · promos.csv · report.md · rejected.json · raw_llm.jsonl · run_meta.json   (+ one W&B run)
  ▼
editor (human): review in report.md or the local Streamlit app → post / maybe / reject → labels.csv → eval metrics
```

### Key decisions

| Decision | Why |
|---|---|
| The LLM cites **block IDs**; code turns them into times | Models misquote timestamps. With IDs, every cut lands on a real block edge and can be checked. |
| **Hard rules in code** (length, hook window, end on cliffhanger, no mid-line cuts) | Code is deterministic, free and testable, and LLMs are bad at arithmetic on times. |
| **Separate cold-viewer judge** | The finder's self-scores bunch up at 4–5. A judge with no show context tests "makes sense on its own" directly. The key only allows one model, so the judge is the same model in a different role (a known limit). |
| **Two backends behind one interface** | `codex`: runs `codex exec` read-only in an empty folder, for gateways that only accept approved agent clients (AgentRouter). `openai`: calls any OpenAI-compatible HTTP API (Kuku's interview APIs, Mistral, DeepSeek, Groq...). Swapping is a `.env` change; the rest of the pipeline doesn't know which backend runs. |
| **5 episodes per call** | Codex adds ~17K tokens of its own instructions to every call (measured: ~6.8¢ each), so fewer, larger calls stretch the $10 quota. That's 10 finder calls + 1 judge call per show. The prompts (~15K tokens) are well within the model's context window. |
| **Disk cache of raw replies** | Reruns cost nothing and are reproducible, and a crashed run resumes where it stopped. This matters on a $10 budget. |

### Model choice (tested)

| Option | Result |
|---|---|
| **AgentRouter `gpt-5.6-sol` via Codex CLI (chosen)** | Works through `codex exec`. Plain HTTP calls are refused (`unauthorized client`). Measured on a tiny prompt: ~17K input tokens, 6–14 s and ~6.8¢ per call, no prompt caching. |
| DeepSeek API | Key valid, but the account balance is $0. |
| Groq free tier | Works, but only 8K tokens/min per model, below one 15K-token prompt. It would force 1 episode per call and ~1 h runs. |
| Local models | Ruled out by the user. |

### Who does what

- **AI:** judging drama: spotting hooks and cliffhangers, saying why a clip works, reading it as a new viewer would.
- **Code:** parsing, timestamps, every hard rule, the scoring formula, dedupe, outputs, tracking.
- **Human:** the final pick and the timing check against the video. Their labels become the eval set and, later, few-shot
  examples for the prompts.

## 5. Ranking: what to post first

`final = rule score + judge overall (1–5)`. Judged promos rank above unjudged ones. The hook carries the most weight
because a promo that doesn't stop the scroll is never watched. The cliffhanger and standalone scores decide whether a viewer
taps through. The spoiler penalty protects the series' main twist, and the early-episode bonus applies assumption 5.

## 6. Quality checking

1. **Unit tests** for the parser, rules, ranking, both backends (fakes, no network) and the end-to-end pipeline, run on
   synthetic fixtures (never Kuku content).
2. **Automatic run stats**, logged to W&B: proposed → valid → unique counts, rejections by reason, auto-fix rate, mean
   duration, tokens, cost, request count.
3. **Human labels:** label the top 20 as post / maybe / reject, with a reason. This gives precision@5/10/20 and a histogram
   of reject reasons, which answers "where does it pick badly".
4. **Judge–human agreement:** the mean judge score for "post" vs "reject" shows whether the automatic judge can be trusted
   at scale.

> **Update 2026-11-06:** steps 3–4 are dropped for the submission. The labeller isn't a promo editor, and the first
> labels judged the model's working titles rather than the clips (W&B run `7wjnqkdk`, tagged `invalid`). Quality rests
> on steps 1–2 and the cold-viewer judge. `promo-finder eval` stays for when an editor labels a run.

Failure modes to look for (to be confirmed by the runs):
- Standalone scores come out too high because the judge reads character names that viewers never see.
- Visual hooks (a slap that exists only in an ACTION line) are over- or under-rated.
- Self-scores bunch together, so the rule score can't separate candidates well.
- Promos end on a moment the next line resolves.
- Time arithmetic errors (too_long / too_short).
- Duplicate moments retold with different timestamps.
- The judge favours its own picks, since it's the same model.

## 7. Scale and cost

- **Per show (now):** 10 + 1 calls, ~350K input tokens (~190K of them Codex overhead) and ~30K output. Estimated
  $1.5–2 and 10–20 min; W&B and the AgentRouter billing delta give the measured numbers. The $10 quota covers the dev
  runs, one or two full runs and the interview rerun, so the budget is tracked per run.
- **Every show:** a weekly batch job runs the CLI once per show folder. At volume, the `openai` backend against a direct API
  removes the ~17K-token Codex overhead per call, so cost becomes just the content tokens. Results go into the editor's
  review queue. Editor decisions build up as labels, which become a regression eval whenever the prompt or model changes.
- **Other languages:** the parser works from the format, not the language. The prompts are in English and the model can read
  other languages, but this is untested.

## 8. Deliverables

| Brief item | What gets submitted |
|---|---|
| Solution doc (PDF, ≤ 2 pages) | `docs/solution-doc.md` → Google Docs → PDF |
| Prototype link | Public GitHub repo (no input pack) with clear run steps. A hosted app isn't possible because the Codex backend needs a local CLI, and the brief accepts a repo. The Streamlit review app runs locally. |
| Raw outputs | `outputs/<show>/<run_id>/` from the full 50-episode run, shared as a Drive folder (it quotes the script, so it stays out of the public repo) |
| Walkthrough video (optional) | ≤ 3 min Loom: CLI run → report → local Streamlit review |
| "Which AI tools, and where they got it wrong" | `docs/ai-log.md`, kept during the build |

## 9. Out of scope / known limits

- No video, so the tool can't check that visual hooks land or that script times match the cut.
- Cross-episode joins are limited to the batch window (5 episodes).
- The same moment retold in a recap, with different timestamps, isn't caught as a duplicate.
- The finder and the judge are the same model.
- Budget-bound: $10 total and ~$1.5–2 per full run.
- English prompts, tested on one show.
