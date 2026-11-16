import pandas as pd

from seeding.forecast import collect, ledger


def test_append_only_never_rewrites_and_dedupes(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER", tmp_path)
    row = {"pred_id": "a", "client": "x", "action": "views", "expected": "100"}
    assert ledger.append("predictions", [row]) == 1
    before = ledger.path("predictions").read_text()
    # same id with a different value (e.g. re-predicted after the result is known): ignored, file unchanged
    assert ledger.append("predictions", [{**row, "expected": "999"}]) == 0
    assert ledger.path("predictions").read_text() == before
    assert ledger.append("predictions", [{**row, "pred_id": "b"}, {**row, "pred_id": "b"}]) == 1
    df = ledger.load("predictions")
    assert list(df.pred_id) == ["a", "b"] and df.expected.tolist() == ["100", "100"]


def test_pred_id_is_stable():
    assert ledger.pred_id("prepost", "1", "m", "views") == ledger.pred_id("prepost", "1", "m", "views")
    assert ledger.pred_id("prepost", "1", "m", "views") != ledger.pred_id("prepost", "1", "m", "likes")


def test_snapshot_due_schedule():
    assert not collect.due(0.2, [])                 # too young
    assert collect.due(0.6, [])                     # passed 30m, nothing taken
    assert not collect.due(0.9, [0.55])             # 30m already taken, 1h not reached
    assert collect.due(1.1, [0.55])                 # passed 1h
    assert not collect.due(30, [24.3])              # 24h taken, 48h not reached
    assert collect.due(49, [24.3])
    assert not collect.due(60, [])                  # too old to matter


def test_snapshot_rows_split_post_and_replies():
    now = pd.Timestamp("2026-11-16T12:00Z")
    post = pd.Series({"tweet_id": "1", "username": "Alex", "created": pd.Timestamp("2026-11-16T10:00Z")})
    detail = [{"tweet_id": "1", "username": "Alex", "view_count": 500, "like_count": 9, "reply_count": 2},
              {"tweet_id": "2", "username": "Bob", "created_at": "2026-11-16T11:00Z"},
              {"tweet_id": "3", "username": "alex", "created_at": "2026-11-16T11:05Z"}]   # author's own thread reply
    snap, eng = collect.snapshot_rows(post, detail, now)
    assert snap["views"] == 500 and snap["age_h"] == 2.0 and snap["client"] == "alex"
    assert [e["engager"] for e in eng] == ["bob"]
    assert collect.snapshot_rows(post, [], now) == (None, [])
