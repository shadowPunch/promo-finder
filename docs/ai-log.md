# AI usage log

Kept during the build; the solution doc needs "which tools, and one place where they got it wrong".

Tools used:
- Claude Code: design, implementation plan, code and tests
- gpt-5.6-sol via AgentRouter, run through the Codex CLI: the product's finder and cold-viewer judge

## Where AI got it wrong

| Date | Tool | What it got wrong | How I caught it | Fix |
|------|------|-------------------|-----------------|-----|
| 2026-11-06 | Claude Code | The build plan set `readme = "README.md"` in pyproject.toml but only wrote README.md in the last task, so `uv sync` failed on the first step | `uv sync` build error | Added a stub README in Task 1 |
