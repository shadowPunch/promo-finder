from promo_finder.tracking import Tracker


def test_tracker_is_a_no_op_when_disabled(monkeypatch):
    monkeypatch.setenv("PROMO_WANDB", "0")
    tracker = Tracker("inference", {"a": 1})
    assert tracker.run is None and tracker.url is None
    tracker.log({"x": 1})
    tracker.summary({"y": 2})
    tracker.table("t", ["c"], [[1]])
    tracker.add_tags(["partial"])
    tracker.finish()
