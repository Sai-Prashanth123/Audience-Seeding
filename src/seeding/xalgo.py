"""X's published ranking rules, as features and as plain-language reasons.

Source: xai-org/x-algorithm @ 07d159b, summarised in
~/.claude/skills/x-algorithm/references/algorithm-weights.md. The trained models are not
published and live experiments can override defaults, so these are the *published*
mechanics only.
"""

from __future__ import annotations

# Home-mixer action weights. Applied in X to predicted per-viewer probabilities; we can only
# apply them to public counts of the observable actions.
ACTION_WEIGHTS = {"reply": 5.0, "quote": 5.0, "repost": 1.0, "like": 0.66}

AUTHOR_DIVERSITY = [1.0, 0.625, 0.4375]  # 1st, 2nd, 3rd post by an author in a viewer's feed
AUTHOR_DIVERSITY_FLOOR = 0.25
OUT_OF_NETWORK_FACTOR = 0.75
CANDIDATE_MAX_AGE_H = 48
COLD_START_MAX_FOLLOWERS = 50_000       # exploration slots: <50k followers, <2h old, <200 impressions
MUTUAL_REPLY_BOOST = 15.0


def day_decay(position: int) -> float:
    """Multiplier for the n-th post by the same author on the same day (1-based)."""
    if position <= len(AUTHOR_DIVERSITY):
        return AUTHOR_DIVERSITY[position - 1]
    return AUTHOR_DIVERSITY_FLOOR


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
