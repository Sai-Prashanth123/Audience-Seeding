"""Slack: post `@client <draft>` in the #predict channel, get the forecast back in the thread.

Runs as a short GitHub Actions job every ~10 minutes (no server to host). Each run reads the channel's recent
messages, answers the ones it hasn't answered (it marks answered messages with a ✅ reaction, so it never needs
its own state file), and stops.

Setup (once): a Slack app with bot scopes channels:history, chat:write, reactions:write, reactions:read, invited to
the channel; GitHub secrets SLACK_BOT_TOKEN and SLACK_PREDICT_CHANNEL (the channel id, e.g. C0123ABCD).
"""

from __future__ import annotations

import os
import re

import pandas as pd

DONE = "white_check_mark"
LOOKBACK_H = 24
HANDLE = re.compile(r"^\s*(?:predict\s+)?@?([A-Za-z0-9_]{2,15})\s*[:\-–]?\s+(.+)$", re.S | re.I)


def parse(text: str, clients: list[str]) -> tuple[str, str] | None:
    """'@itsalexvacca Cold email isn't dead...' -> ('itsalexvacca', draft). None if it isn't a forecast request."""
    text = re.sub(r"<@[A-Z0-9]+>", "", text or "").strip()     # drop an @-mention of the bot itself
    text = re.sub(r"<https?://x\.com/([A-Za-z0-9_]+)\|?[^>]*>", r"@\1", text)
    m = HANDLE.match(text)
    if not m:
        return None
    lower = {c.lower(): c for c in clients}
    handle = m.group(1).lower()
    if handle not in lower:
        return None
    draft = m.group(2).strip()
    return (lower[handle], draft) if len(draft) >= 10 else None


def format_slack(res: dict) -> str:
    names = {"views": "Views", "likes": "Likes", "replies": "Replies", "reposts": "Reposts", "quotes": "Quotes",
             "bookmarks": "Bookmarks", "xscore": "X score"}
    v = res["actions"]["views"]
    head = (f"*Forecast for @{res['client']}* ({res['format']}, {res['hook']} opening, post #{res['day_position']} "
            f"of the day)\n*Views: ~{v['expected']:,.0f}* (80% range {v['low']:,.0f}–{v['high']:,.0f}; usual "
            f"{v['usual']:,.0f}" + (f", {v['vs_usual']:.2f}× usual)" if v["vs_usual"] else ")"))
    rows = [f"{names[a]}: ~{x['expected']:,.0f} ({x['low']:,.0f}–{x['high']:,.0f}), usual {x['usual']:,.0f}"
            for a, x in res["actions"].items() if a != "views"]
    why = ("\n_Why:_ " + "; ".join(f"{n} {d} it ~{p}%" for n, d, p in res["drivers"])) if res["drivers"] else ""
    rules = "".join(f"\n_X rule:_ {r}" for r in res["x_rules"])
    return head + "\n```" + "\n".join(rows) + "```" + why + rules + \
        "\n_An estimate from real past posts; 8 in 10 posts land inside the range. Not a guarantee._"


def run(history: pd.DataFrame, clients: list[str], token: str | None = None, channel: str | None = None) -> dict:
    from slack_sdk import WebClient

    from .forecast import serve
    token = token or os.environ["SLACK_BOT_TOKEN"]
    channel = channel or os.environ["SLACK_PREDICT_CHANNEL"]
    sc = WebClient(token=token)
    me = sc.auth_test()["user_id"]
    oldest = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=LOOKBACK_H)).timestamp()
    msgs = sc.conversations_history(channel=channel, oldest=str(oldest), limit=200)["messages"]
    answered = 0
    for m in msgs:
        if m.get("bot_id") or m.get("user") == me or m.get("thread_ts", m["ts"]) != m["ts"]:
            continue
        if any(r["name"] == DONE and me in r.get("users", []) for r in m.get("reactions", [])):
            continue
        req = parse(m.get("text", ""), clients)
        if req is None:
            continue
        client, draft = req
        try:
            res = serve.predict(history[history.author == client.lower()], client, draft)
            reply = format_slack(res)
        except ValueError as e:
            reply = f"Couldn't forecast this one: {e}"
        sc.chat_postMessage(channel=channel, thread_ts=m["ts"], text=reply)
        sc.reactions_add(channel=channel, timestamp=m["ts"], name=DONE)
        answered += 1
    return {"seen": len(msgs), "answered": answered}
