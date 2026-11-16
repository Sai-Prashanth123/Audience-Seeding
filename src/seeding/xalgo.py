"""X's published ranking rules, as features and as plain-language reasons.

Source: github.com/xai-org/x-algorithm (Apache-2.0) @ commit 30647a8 (14 Nov 2026), read directly:
  home-mixer/params/param.rs        action weights (rust_home_mixer_*_weight defaults)
  vm-ranker/params.rs               AuthorDiversityDecay 0.5, AuthorDiversityFloor 0.25, OonWeightFactor 0.75
  xai-value-model/scoring.rs        diversity_multiplier = (1 - floor) * decay**k + floor
Earlier versions of this file cited 07d159b and used like = 0.66 and a hard floor after the 3rd post.
In X these weights multiply each viewer's *predicted probability* of an action; we can only apply them
to public counts of the observable actions, so our X score is an approximation of X's own value.
"""

from __future__ import annotations

X_ALGO_COMMIT = "30647a8"

# Every published action weight (param.rs defaults). Negative actions are never public, which is why the
# forecaster estimates a negative-signal *risk* from the text instead.
PARAM_WEIGHTS = {
    "favorite": 0.708, "reply": 5.0, "retweet": 1.0, "quote": 5.0, "share": 2.118, "share_via_dm": 5.0,
    "share_via_copy_link": 0.0, "follow_author": 4.0, "click": 0.274, "open_link": 0.2, "profile_click": 0.0,
    "photo_expand": 0.05, "dwell": 0.05, "vqv": 0.0, "quoted_click": 0.05,
    "bidirectional_follow_reply_boost": 15.0,
    "not_interested": -53.07, "block_author": -31.2, "mute_author": -58.8, "report": -234.0, "not_dwelled": -0.02,
}

# The observable ones, keyed by our count columns (tweets table).
ACTION_WEIGHTS = {"reply": PARAM_WEIGHTS["reply"], "quote": PARAM_WEIGHTS["quote"],
                  "repost": PARAM_WEIGHTS["retweet"], "like": PARAM_WEIGHTS["favorite"]}
COUNT_WEIGHTS = {"reply_count": ACTION_WEIGHTS["reply"], "quote_count": ACTION_WEIGHTS["quote"],
                 "retweet_count": ACTION_WEIGHTS["repost"], "like_count": ACTION_WEIGHTS["like"]}

AUTHOR_DIVERSITY_DECAY = 0.5
AUTHOR_DIVERSITY_FLOOR = 0.25
OUT_OF_NETWORK_FACTOR = 0.75
CANDIDATE_MAX_AGE_H = 48
COLD_START_MAX_FOLLOWERS = 50_000       # exploration slots: <50k followers, <2h old, <200 impressions
MUTUAL_REPLY_BOOST = PARAM_WEIGHTS["bidirectional_follow_reply_boost"]


def day_decay(position: int) -> float:
    """X's author-diversity multiplier for the n-th post by the same author a viewer sees (1-based):
    (1 - floor) * decay**(n-1) + floor  ->  1.0, 0.625, 0.4375, 0.344, 0.297, ... -> 0.25."""
    k = max(int(position), 1) - 1
    return (1 - AUTHOR_DIVERSITY_FLOOR) * AUTHOR_DIVERSITY_DECAY ** k + AUTHOR_DIVERSITY_FLOOR


def cold_start_eligible(followers: float | None) -> bool:
    return followers is not None and followers == followers and followers < COLD_START_MAX_FOLLOWERS


def reasons(day_position: int, followers: float | None, has_link: bool) -> list[str]:
    out = []
    if day_position >= 2:
        out.append(f"post #{day_position} today: X shows it to repeat viewers at ×{day_decay(day_position)}")
    if cold_start_eligible(followers):
        out.append("under 50k followers: eligible for X's first-2-hours exploration slots")
    if has_link:
        out.append("has a link: no link penalty exists in X's published code; link opens carry little weight")
    return out
