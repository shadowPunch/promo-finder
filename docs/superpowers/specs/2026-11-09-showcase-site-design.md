# Showcase site: design

**Goal:** a light, simple, good-looking website that explains Promo Finder to Kuku reviewers and replaces a recorded demo
video. Hosted on Streamlit Community Cloud from the public repo `shadowPunch/promo-finder`.

## Decisions (agreed with the user)

| Topic | Decision |
|---|---|
| Tabs | Home · Methodology · Outputs · Demo, as Streamlit pages in a top navigation bar |
| Demo content | An **artificial** 4-episode microdrama we write ourselves, never the Kuku scripts |
| Demo behaviour | Replays the real tool's output on that artificial show; no live model calls from the site |
| Outputs tab | Summary numbers, charts and the slate, **two** promos in full as excerpts, then a link to GitHub for the rest |
| Look | "Screenplay paper": warm paper, serif headings, typewriter script lines, one cinema-red accent; no gradients, no dark mode |
| Repo | Public (the user made it public). The committed results folder quotes script excerpts; the user accepted this |

## What the site never contains

The Kuku episode files, `raw_llm.jsonl` (full prompts with whole episodes), `screened.json`, API keys or W&B
credentials. The site reads two small JSON files and needs only `streamlit` to run.

## Architecture

```
.streamlit/config.toml            theme; Community Cloud reads config only from the repo root
site/
  streamlit_app.py                entry: page config, shared CSS, st.navigation(position="top")
  requirements.txt                streamlit
  theme.py                        load CSS, small shared HTML helpers (stat row, section label, script block)
  style.css                       paper / ink / red styles, font imports
  pages/home.py, methodology.py, outputs.py, demo.py
  player/player.html              the demo animation: one self-contained HTML/CSS/JS file
  data/results.json               real run 155bsnqx: summary, slate, two excerpts, links
  data/demo.json                  artificial show: episodes plus the full tool output on it
  tests/test_site.py              every page renders; player gets valid data
v2/examples/demo-show/            the artificial scripts (Kuku format)
v2/src/promo_finder_v2/site_data.py   run folder (+ episodes) -> results.json / demo.json
v2/results/155bsnqx/              committed run files for the download link
```

**Data flow:** the tool runs as usual and writes a run folder → `promo-finder-v2 export-site` (new CLI subcommand,
backed by `site_data.py`) turns a run folder into `site/data/*.json` → the site renders the JSON. The site has no
dependency on the `promo_finder_v2` package, so it builds fast on Community Cloud and can't call a model by accident.

**Demo player:** `demo.py` reads `player.html`, injects `demo.json` (with `</` escaped so the JSON can't close the
script tag) and shows it with `st.components.v1.html` at a fixed height. Pure HTML/CSS/JS, no libraries, no network
except Google Fonts. It plays on its own once started, so each viewer costs the server nothing.

## Pages

1. **Home:** headline ("From 50 scripts to the 10 promos worth posting"), one paragraph on what the tool does, the
   funnel as big numbers (93 found → 12 tested → 140 duels → 10 to post), three one-line steps, author (Nithish
   Ravikkumar, 23123028), links to the GitHub repo and the solution doc.
2. **Methodology:** the pipeline as a step diagram, each step marked *model* or *code*; the engagement score's four
   parts and the confusion penalty; how duels work and why (pick agreement 61% → 86%, same winner 1 of 6 → 8 of 12,
   first-shown bias 49%); business frameworks; limits (the issue tree from the solution doc).
3. **Outputs:** run facts (id, model, spend); funnel; win rate by re-cut type (bar chart); reliability checks
   table; the 10-promo posting slate (title, role, segments, score, duels won, engine); **two** promos in full
   (#1 and #2: hook, sinker, still-watching curves, the versions tried, script lines in typewriter font); a
   "Download all outputs" button linking to `v2/results/155bsnqx/` on GitHub.
4. **Demo:** the animated replay (below), with a caption saying the show is artificial and the output is real.

## Demo animation

A stage rail across the top (clickable), play / pause / replay and a 1× / 2× speed toggle. Stages:

1. **Scripts in:** four episode "script pages" slide in; blocks show timecode, speaker and line in typewriter font.
2. **Find:** the blocks of each proposed promo light up; a card flies out per promo with title, engine tag
   (explosive / funny / puzzling / shocking) and its open question.
3. **Rule checks:** each card gets a stamp: PASS, FIXED (snapped to a block edge) or REJECTED with the reason.
4. **Versions:** for each tested moment, the original plus three re-cuts appear as bars on an episode timeline,
   labelled by change (new hook / new ending / new length or structure).
5. **Audience:** two viewer lanes draw a "still watching" curve per version, line by line; the score counts up.
6. **Duels:** pairs appear as X vs Y in both orders; each viewer's pick drops a tally mark; the winner is crowned.
7. **Promo:** a 9:16 phone frame plays the winning promo as captions timed to the script timestamps; a "hook"
   marker covers 0–3 s; it ends on a card with the open question and "Watch episode N".

Responsive down to a 380 px wide phone screen (stacked layout).

## The artificial show

An original 4-episode English microdrama (about 2.5 minutes per episode, 40–60 timed blocks each) in the Kuku
format the parser reads. Story: a bride is thrown out on her wedding day when her father's ruin is exposed, and
returns five years later as the owner of the family's company. It uses the genre's usual beats (public humiliation,
hidden identity, a comic sidekick, a betrayal, a cliffhanger every episode) so all four engines can appear. It is
written for this project and copies nothing from the Kuku pack or any real show.

**Demo run** (real model, logged to W&B with tag `demo-show`):
`--per-call 4 --shortlist 4 --versions 3 --refine-top 0 --reliability 0 --duel-batch 24 --max-cost 2`.
About 8 model calls; estimated $1.00–1.60 of the ~$4.59 credit left, hard cap $2. If the cap stops the run, stop
and tell the user before rerunning.

## Look

- Colours: paper `#FAF7F0`, card `#FFFFFF`, ink `#1C1B19`, muted `#6B6560`, rules `#E4DED3`, accent red `#B42318`
  (stamps, active stage, key numbers only).
- Fonts (Google Fonts): Fraunces for headings, IBM Plex Sans for body, Courier Prime for script lines and timecodes.
- Thin 1 px rules, generous white space, max content width ~1100 px, no shadows heavier than a 1–2 px soft edge.
- Charts follow the same palette: ink bars, red for the highlighted bar, no gridline clutter.

## Errors

- Missing or malformed data file: the page shows a short message naming the file and how to regenerate it
  (`promo-finder-v2 export-site ...`) instead of a stack trace.
- Export: a run folder missing a required file fails with the file name; a demo export without the episodes folder
  fails with a clear message.

## Testing

- `v2/tests/test_site_data.py`: export from a small fake run folder built on the fixture show; checks both JSON
  shapes, that the two excerpts are the requested ranks, and that the demo episodes' block ids match the candidates.
- `site/tests/test_site.py`: Streamlit `AppTest` runs each page with the committed data and asserts no exceptions;
  the player HTML contains the injected JSON and survives a `</script>` string in the data.
- Manual check: run locally from the repo root (`streamlit run site/streamlit_app.py`), screenshot every page at
  desktop and phone widths with headless Chrome, and watch the demo end to end.

## Release

1. Merge `v2-duels` and the site branch into `main` and push (only after the user says so).
2. The user signs in at share.streamlit.io and deploys: repo `shadowPunch/promo-finder`, branch `main`, main file
   `site/streamlit_app.py`. Public repo → public app.
3. Root README and `site/README.md` describe the site, how to run it and how to refresh its data.
