import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from explain import client_findings, label, rel_words, shared_lessons  # noqa: E402


def _posts(client, spec):
    """spec: list of (n, hook, format, day_slot, rel, niche)"""
    rows = []
    for n, hook, fmt, slot, rel, niche in spec:
        rows += [{"client": client, "hook": hook, "format": fmt, "day_slot": slot, "topic": "gtm / x / y",
                  "length": "1,000+", "hour_block": "12-17 UTC", "rel_perf": rel, "niche_share": niche}] * n
    return pd.DataFrame(rows)


def test_reach_but_wrong_audience_is_flagged():
    p = _posts("a", [(10, "giveaway / comment-to-get", "long-form post", "1st post of day", 10.0, 0.2),
                     (30, "statement", "long-form post", "1st post of day", 1.0, 0.4)])
    f = client_findings(p)
    top = f["reach_only"][0]
    assert top["text"].startswith("Giveaways") and "right audience" in top["note"]


def test_small_groups_never_recommended_and_third_post_rule():
    p = _posts("a", [(3, "question", "article", "1st post of day", 9.0, 0.5),       # only 3 posts
                     (20, "statement", "quote post", "1st post of day", 1.0, 0.3),
                     (8, "statement", "quote post", "3rd+", 0.5, 0.3)])
    f = client_findings(p)
    assert all("question" not in d["text"].lower() for d in f["do_more"])
    assert "max 2 posts a day" in f["plan"]
    assert f["few_posts"]


def test_shared_lesson_needs_every_client():
    a = _posts("a", [(10, "statement", "quote post", "1st post of day", 0.5, 0.3),
                     (10, "statement", "article", "1st post of day", 1.2, 0.3)])
    b = _posts("b", [(10, "statement", "quote post", "1st post of day", 0.6, 0.3),
                     (10, "statement", "article", "1st post of day", 1.0, 0.3)])
    lessons = shared_lessons(pd.concat([a, b]))
    assert any("Quote posts" in s and "every client" in s for s in lessons)
    assert not any("Articles" in s for s in lessons)


def test_words():
    assert label("topic", "cold / cold email / email") == 'Posts about cold, email'
    assert rel_words(0.54) == "0.54× (46% worse than usual)"
    assert rel_words(11.6).startswith("11.6×")


def test_plan_never_defaults_to_reach_only_content():
    p = _posts("a", [(10, "giveaway / comment-to-get", "long-form post", "1st post of day", 10.0, 0.2),
                     (10, "story", "long-form post", "1st post of day", 1.4, 0.4),
                     (30, "statement", "long-form post", "1st post of day", 1.0, 0.4)])
    plan = client_findings(p)["plan"]
    assert "open with a story" in " ".join(plan).lower()
    assert not any(x.startswith("open with giveaways") for x in plan)
    assert any("now and then, for reach" in x for x in plan)
