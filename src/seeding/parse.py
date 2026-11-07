"""Turn raw xplatform tweet records into interaction edges.

Stored tweets have no in_reply_to field. X prefixes a reply's text with the
@handles of the people in the thread it answers, so the leading run of
@mentions is the reply target list (the first one is the direct parent's author
in the common case). Mentions later in the text are not reply targets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LEADING_MENTIONS = re.compile(r"^(?:\s*@([A-Za-z0-9_]{1,15}))+")
_HANDLE = re.compile(r"@([A-Za-z0-9_]{1,15})")
_RETWEET = re.compile(r"^RT @([A-Za-z0-9_]{1,15}):")


def reply_targets(text: str | None) -> list[str]:
    """Handles in the leading @-mention block of a reply, lower-cased, in order, deduped."""
    if not text:
        return []
    m = _LEADING_MENTIONS.match(text)
    if not m:
        return []
    seen: list[str] = []
    for h in _HANDLE.findall(m.group(0)):
        h = h.lower()
        if h not in seen:
            seen.append(h)
    return seen


def retweet_source(text: str | None) -> str | None:
    """Original author of a classic 'RT @handle: ...' retweet text, if present."""
    if not text:
        return None
    m = _RETWEET.match(text)
    return m.group(1).lower() if m else None


@dataclass(frozen=True)
class Edge:
    src: str        # who acted (lower-case handle)
    dst: str        # who they acted on
    kind: str       # 'reply' | 'retweet'
    tweet_id: str
    created_at: str


def edges_from_tweet(t: dict) -> list[Edge]:
    """Interaction edges carried by one stored tweet record."""
    src = (t.get("username") or "").lower()
    if not src:
        return []
    tid = str(t.get("tweet_id", ""))
    at = t.get("created_at") or ""
    out: list[Edge] = []
    if t.get("is_reply"):
        targets = reply_targets(t.get("text"))
        # Direct parent author only; the rest of the block is thread context.
        if targets and targets[0] != src:
            out.append(Edge(src, targets[0], "reply", tid, at))
    if t.get("is_retweet"):
        rt = retweet_source(t.get("text"))
        if rt and rt != src:
            out.append(Edge(src, rt, "retweet", tid, at))
    return out
