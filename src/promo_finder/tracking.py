"""Weights & Biases tracking for every run. PROMO_WANDB=0 runs untracked (e.g. offline).

Only configs, metrics and timestamp tables are logged: the screenplays are confidential."""
from __future__ import annotations

import os


class Tracker:
    def __init__(self, job_type: str, config: dict, tags: list[str] | None = None, notes: str | None = None):
        self.run = None
        if os.environ.get("PROMO_WANDB", "1") == "0":
            return
        try:
            import wandb

            self.run = wandb.init(project=os.environ.get("WANDB_PROJECT", "kuku-promo-finder"),
                                  job_type=job_type, config=config, tags=tags or [], notes=notes)
        except Exception as err:  # any W&B failure must stop the run, never silently skip tracking
            raise SystemExit(f"W&B unavailable ({err}). Fix `wandb login`/network, "
                             f"or set PROMO_WANDB=0 to run untracked.") from err

    @property
    def url(self) -> str | None:
        return self.run.url if self.run else None

    def log(self, metrics: dict) -> None:
        if self.run:
            self.run.log(metrics)

    def summary(self, values: dict) -> None:
        if self.run:
            self.run.summary.update(values)

    def table(self, name: str, columns: list[str], rows: list[list]) -> None:
        if self.run:
            import wandb

            self.run.log({name: wandb.Table(columns=columns, data=rows)})

    def finish(self, failed: bool = False) -> None:
        if self.run:
            self.run.finish(exit_code=1 if failed else 0)
