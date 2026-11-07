import numpy as np

from seeding.segments import _assign

CLASSES = ["ai", "b2b", "none", "tech"]


def test_none_wins_means_no_segment():
    main, also = _assign(np.array([[0.1, 0.1, 0.7, 0.1]]), CLASSES)
    assert (main, also) == (["none"], [""])


def test_close_second_segment_is_kept():
    # B2B 0.45, AI 0.35 (>= half of 0.45 and >= 0.15) -> b2b + ai
    main, also = _assign(np.array([[0.35, 0.45, 0.1, 0.1]]), CLASSES)
    assert (main, also) == (["b2b"], ["ai"])


def test_weak_second_segment_is_dropped():
    # AI 0.80, tech 0.12: below 0.15 floor and below half of 0.80
    main, also = _assign(np.array([[0.80, 0.05, 0.03, 0.12]]), CLASSES)
    assert (main, also) == (["ai"], [""])


def test_none_is_never_a_second_segment():
    main, also = _assign(np.array([[0.5, 0.05, 0.4, 0.05]]), CLASSES)
    assert (main, also) == (["ai"], [""])


def test_training_set_people_win_and_low_confidence_ai_is_ignored(tmp_path, monkeypatch):
    import pandas as pd
    import seeding.segments as seg
    labels = tmp_path / "grades.csv"
    pd.DataFrame({"username": ["a", "b"], "expected": ["ai", "tech"], "grader": ["claude", "user"],
                  "note": ["", ""]}).to_csv(labels, index=False)
    ai = tmp_path / "ai.csv"
    pd.DataFrame({"username": ["a", "b", "c", "d"], "status": ["ok"] * 4,
                  "segment": ["b2b", "b2b", "ai", "tech"], "confidence": ["0.95", "0.95", "0.9", "0.5"]}
                 ).to_csv(ai, index=False)
    monkeypatch.setattr(seg, "LABELS", labels)
    monkeypatch.setattr(seg, "AI_LABELS", ai)
    names = ["a", "b", "c", "d"]
    lab, _, y = seg._training_set({"client_segments": {}}, names, np.zeros((4, 2)))
    got = dict(zip(lab.username, zip(lab.expected, lab.grader)))
    assert got["a"] == ("ai", "claude")       # Claude's hand label beats the AI reviewer
    assert got["b"] == ("tech", "user")       # the team's label beats everything
    assert got["c"] == ("ai", "ai")           # confident AI label is used
    assert "d" not in got                     # low-confidence AI label is ignored
