import numpy as np
import pandas as pd

from seeding.forecast import who


def test_candidates_use_only_engagements_before_the_post():
    ev = pd.DataFrame({"client": "c", "engager": ["a", "a", "b"], "tweet_id": ["1", "2", "3"],
                       "engaged_at": pd.to_datetime(["2026-01-01", "2026-03-01", "2026-06-01"], utc=True)})
    c = who.candidates(ev, {"s"}, "c", pd.Timestamp("2026-04-01", tz="UTC")).set_index("engager")
    assert c.loc["a", "n_past"] == 2 and "b" not in c.index      # b engaged later: unknown at post time
    assert c.loc["s", "n_past"] == 0 and c.loc["s", "is_seed"] == 1
    assert c.loc["s", "recency"] == np.log1p(who.NEVER_DAYS)


def test_recall_at_k_pools_over_posts():
    rows = pd.DataFrame({"tweet_id": ["1"] * 3 + ["2"] * 3, "y": [1, 0, 1, 0, 0, 1], "n_actual": [3] * 3 + [1] * 3,
                         "s": [0.9, 0.8, 0.1, 0.9, 0.5, 0.1]})
    assert who.recall_at(rows, "s", 1) == 1 / 4      # post 1 finds 1 of 3, post 2 finds 0 of 1


def test_rank_prefers_topic_fit_and_history():
    v = np.eye(3, dtype=np.float32)
    cands = pd.DataFrame({"engager": ["fan", "stranger"], "segment": ["b2b", "ai"], "n_past": [5, 0],
                          "log_past": [np.log1p(5), 0.0], "recency": [1.0, np.log1p(400)], "past_90d": [1.0, 0.0],
                          "is_seed": [0.0, 1.0], "vec": [v[0], v[1]]})
    coef = {"log_past": 0.3, "recency": -0.6, "past_90d": 1.0, "topic_fit": 2.4, "is_seed": 0.6}
    r = who.rank(cands, coef, -5.5, v[0], k=2)
    assert r["top"][0]["engager"] == "fan" and abs(sum(r["niche_mix"].values()) - 1) < 1e-6
