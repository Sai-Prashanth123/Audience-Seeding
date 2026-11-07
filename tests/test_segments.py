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
