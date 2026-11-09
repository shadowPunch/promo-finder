import pytest
from pydantic import BaseModel

from helpers import FakeClient, fake_llm
from promo_finder.budget import Budget, BudgetExceeded
from promo_finder.llm import LLM, LLMConfig


class Answer(BaseModel):
    value: int


def priced_llm(replies, cache_dir, budget):
    """$1 per prompt token, so FakeClient's chars // 4 token count gives predictable spend."""
    cfg = LLMConfig(model="fake-model", base_url="http://x", api_key="k", price_in_per_m=1_000_000)
    return LLM(cfg, client=FakeClient(replies), cache_dir=cache_dir, budget=budget)


def test_budget_blocks_a_call_that_could_cross_the_cap():
    budget = Budget(cap_usd=1.0, max_call_cost=0.3)
    budget.check("a")
    budget.add(0.75)
    with pytest.raises(BudgetExceeded, match="cap"):
        budget.check("b")
    assert budget.exhausted


def test_no_cap_never_blocks():
    budget = Budget(cap_usd=None)
    budget.add(1e6)
    budget.check("a")
    assert not budget.exhausted


def test_llm_adds_spend_and_stops_at_the_cap(tmp_path):
    budget = Budget(cap_usd=3.0, max_call_cost=0.0)
    llm = priced_llm(['{"value": 1}', '{"value": 2}'], tmp_path, budget)
    llm.complete_json("s", "a" * 8, Answer, tag="t1")  # 9 chars -> 2 tokens -> $2
    llm.complete_json("s", "b" * 8, Answer, tag="t2")
    assert budget.spent == pytest.approx(4.0)
    with pytest.raises(BudgetExceeded):
        llm.complete_json("s", "c" * 8, Answer, tag="t3")
    assert len(llm.client.requests) == 2


def test_cached_replies_skip_the_budget(tmp_path):
    fake_llm(['{"value": 1}'], tmp_path).complete_json("s", "u", Answer, tag="t")
    llm = priced_llm([], tmp_path, Budget(cap_usd=0.0))
    assert llm.complete_json("s", "u", Answer, tag="t").value == 1
