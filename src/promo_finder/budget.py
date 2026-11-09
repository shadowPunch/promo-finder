"""A spending cap shared by every model client in a run.

Spend is estimated from token counts and the configured prices (in v1 this ran ~20% above actual billing, so it errs
on the safe side). Cached replies cost nothing and are never blocked."""
from __future__ import annotations


class BudgetExceeded(RuntimeError):
    """The next model call could push spending over the cap."""


class Budget:
    def __init__(self, cap_usd: float | None, max_call_cost: float = 0.30):
        self.cap_usd = cap_usd          # None = no cap
        self.max_call_cost = max_call_cost
        self.spent = 0.0
        self.exhausted = False

    def check(self, tag: str) -> None:
        if self.cap_usd is not None and self.spent + self.max_call_cost > self.cap_usd:
            self.exhausted = True
            raise BudgetExceeded(f"{tag}: spending cap ${self.cap_usd:.2f} reached (spent ${self.spent:.2f})")

    def add(self, usd: float) -> None:
        self.spent += usd
