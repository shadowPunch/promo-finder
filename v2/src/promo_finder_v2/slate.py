"""Posting slate (70/20/10): mostly proven winners, a couple of challengers from other engines, one wild card.

Spreading the slate across engines avoids posting ten near-identical promos (creative fatigue) and keeps learning which
engine works; the wild card is the promo newcomers (viewer B) liked most."""
from __future__ import annotations

from .models import Promo

SLATE_SIZE = 10
PROVEN = 7
CHALLENGERS = 2


def build_slate(winners: list[Promo], size: int = SLATE_SIZE, proven: int = PROVEN,
                challengers: int = CHALLENGERS) -> list[Promo]:
    """Sets `slate_role` on the chosen winners and returns them in slate order."""
    ranked = sorted((w for w in winners if w.engagement), key=lambda p: p.engagement.score, reverse=True)
    slate: list[Promo] = []

    def add(p: Promo, role: str) -> None:
        p.slate_role = role
        slate.append(p)

    def free(p: Promo) -> bool:
        return all(p.promo_id != s.promo_id for s in slate)

    for p in ranked[:min(proven, size)]:
        add(p, "proven")
    engines = {p.engagement.engine for p in slate}
    for p in ranked:
        if sum(s.slate_role == "challenger" for s in slate) == challengers or len(slate) == size:
            break
        if free(p) and p.engagement.engine and p.engagement.engine not in engines:
            add(p, "challenger")
            engines.add(p.engagement.engine)
    rest = [p for p in ranked if free(p)]
    if rest and len(slate) < size:
        add(max(rest, key=lambda p: p.engagement.b.score), "wild card")
    for p in ranked:
        if len(slate) == size:
            break
        if free(p):
            add(p, "proven")
    return slate
