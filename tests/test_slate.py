from helpers import make_engagement, make_promo
from promo_finder.slate import build_slate


def _winner(promo_id, score, engine="explosive", b_score=None):
    promo = make_promo([(1, 0.0, 26.0)], promo_id=promo_id)
    promo.engagement = make_engagement(score, engine, b_score)
    return promo


def test_slate_is_proven_challengers_and_a_wild_card():
    winners = [_winner(f"p{s}", s) for s in range(90, 81, -1)]                 # 90..82, all explosive
    winners += [_winner("funny", 81, "funny"), _winner("puzzle", 80, "puzzling"),
                _winner("newcomer", 79, b_score=99)]
    slate = build_slate(winners)
    assert [p.promo_id for p in slate] == ["p90", "p89", "p88", "p87", "p86", "p85", "p84",
                                           "funny", "puzzle", "newcomer"]
    assert [p.slate_role for p in slate] == ["proven"] * 7 + ["challenger", "challenger", "wild card"]
    chosen = {p.promo_id for p in slate}
    assert all(p.slate_role is None for p in winners if p.promo_id not in chosen)


def test_small_or_uniform_pools_fall_back_to_proven():
    winners = [_winner("a", 80), _winner("b", 70), _winner("c", 60)]
    slate = build_slate(winners, size=10)
    assert [(p.promo_id, p.slate_role) for p in slate] == [("a", "proven"), ("b", "proven"), ("c", "proven")]
