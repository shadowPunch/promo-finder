# Showcase site

**Live: [promo-finder-nrk.streamlit.app](https://promo-finder-nrk.streamlit.app/)**

A four-page Streamlit site that explains Promo Finder and replaces a recorded demo video:

| Page | What it shows |
|---|---|
| **Home** | What the tool does, in three steps |
| **Methodology** | The stages (model steps vs code steps), the engagement score, why cuts are compared side by side, model and cost, frameworks, weaknesses |
| **Outputs** | The submitted run (`155bsnqx`): headline numbers, which re-cuts win, trust checks, the ranked promos, two promos in full, a link to download everything |
| **Demo** | An animated replay of the real tool running on an artificial 4-episode show: scripts → promos found → rule checks → re-cuts → simulated audience → side-by-side comparisons → the winning promo playing as captions on a phone |


## Run it

From the **repo root** (Streamlit Community Cloud also runs from there, and reads the theme from `.streamlit/config.toml`):

```bash
uv run streamlit run showcase/streamlit_app.py
```

Add `?autoplay=1` to the Demo page URL to start the animation on load (used for headless screenshots).

## Where the data comes from

The site reads two JSON files and nothing else. It never imports the `promo_finder` package or calls a model, so it
deploys with `streamlit` only (`showcase/requirements.txt`) and costs nothing per visitor.

| File | Made from | Command (run from the repo root) |
|---|---|---|
| `data/results.json` | Kuku run `155bsnqx` (+ the pack, for the two excerpts) | `uv run promo-finder export-site --kind results --run "outputs/<show>/155bsnqx" --input "<pack folder>" --out showcase/data/results.json` |
| `data/demo.json` | Demo run `c11ks0xy` on `examples/demo-show/` | `uv run promo-finder export-site --kind demo --run outputs/demo-show/c11ks0xy --input examples/demo-show --out showcase/data/demo.json --title "The Bride They Threw Out"` |

The demo show (*The Bride They Threw Out*) was written for this site because the Kuku scripts are confidential. The
demo run used `--per-call 4 --shortlist 4 --versions 3 --refine-top 0 --reliability 0 --duel-batch 24` (8 model
calls, $1.31 billed) and is tracked in W&B as `c11ks0xy`. `results.json` quotes two short Kuku promo excerpts; the
full run files are in `results/155bsnqx/`.

## Code map

| File | Job |
|---|---|
| `streamlit_app.py` | Page config, shared CSS, top navigation |
| `views/*.py` | The four pages |
| `theme.py` | CSS loader and small HTML helpers (stat row, label, screenplay excerpt) |
| `charts.py` | The two Altair charts on Outputs |
| `loaders.py` | Reads `data/*.json`; shows a short error instead of a stack trace if a file is missing |
| `demo_player.py` | Inlines `demo.json` into the player page (escaping `</` so data can't close the script tag) |
| `assets/player.html` | The demo animation: one self-contained HTML/CSS/JS file, no libraries |
| `assets/style.css` | Paper theme styles |
| `tests/test_site.py` | Every page renders through the real navigation; friendly error on missing data; safe data inlining |

## Design decisions

- **One HTML file for the demo.** The animation runs in the visitor's browser, so it is smooth, works on phones and
  needs no server work per viewer. Animating through Streamlit reruns would be choppy and tie up the server.
- **Replay, not live.** The demo replays a finished run: free, instant, and it can't fail while a reviewer watches.
- **Look:** warm paper `#FAF7F0`, ink `#1C1B19`, one red accent `#B42318`; Fraunces headings, IBM Plex Sans body,
  Courier Prime for script lines. Viewer B's curves use blue `#1F63A8`, because near-black ink fails the colour
  checks for a data series (checked with the dataviz palette validator).
- **Folder name:** `showcase/`, not `site/`, which would shadow Python's built-in `site` module.

## Deploy (Streamlit Community Cloud)

share.streamlit.io → Create app → repo `shadowPunch/promo-finder`, branch `main`, main file
`showcase/streamlit_app.py` → Deploy. The repo is public, so the app is public. Deployed at
https://promo-finder-nrk.streamlit.app/; every push to `main` redeploys it. Apps sleep after 12 hours without
visitors; anyone can wake one with "Yes, get this app back up!".
