"""What a writer needs before picking a slot: best window, today's posts (UTC) and the last posts with their shape.

    uv run seeding winners-today --client kenny
"""

from __future__ import annotations

import re

import duckdb
import pandas as pd

from .. import store
from .score import CLIENT, NAME, TYPICAL, viral_shapes

DASH = store.DB_PATH.parent / "dashboard.duckdb"


def _fmt(r) -> str:
    if isinstance(r.article_title, str) and r.article_title:
        return "Article"
    if not re.sub(r"https?://\S+", "", r.text or "").strip():
        return "Article"   # a bare link post is how X articles arrive before their title is stored
    if r.is_quote:
        return "QRT"
    return "Tweet"


def _block(h: str) -> str:
    h = int(h)
    return f"{h:02d}:00-{(h + 3) % 24:02d}:00 UTC"


def report(client: str, n: int = 8) -> str:
    c = CLIENT[client.lower()]
    lines = []
    try:
        d = duckdb.connect(str(DASH), read_only=True)
        rec = d.execute("select strength, best_blocks, avoid_blocks from posting_recs where lower(client)=?",
                        [c]).fetchone()
        d.close()
        if rec:
            best = ", ".join(_block(b) for b in str(rec[1]).split(",") if b.strip())
            avoid = ", ".join(_block(b) for b in str(rec[2] or "").split(",") if b.strip()) or "none"
            lines.append(f"Best window: {best} ({rec[0]}). Avoid: {avoid}.")
    except Exception as e:  # noqa: BLE001
        lines.append(f"Best window: not available ({str(e).splitlines()[0][:120]}).")
    con = duckdb.connect(str(store.DB_PATH), read_only=True)
    df = con.execute("""select created_at, text, view_count, is_quote, is_long_form, article_title
                        from tweets where lower(username)=? and not coalesce(is_reply,false)
                        and not coalesce(is_retweet,false) order by created_at desc limit 60""", [c]).fetchdf()
    con.close()
    df["ts"] = pd.to_datetime(df.created_at, utc=True)
    today = pd.Timestamp.now(tz="UTC").normalize()
    t = df[df.ts >= today]
    lines.append(f"Posts today (UTC day): {len(t)}" + (" -> next one would be #%d" % (len(t) + 1)) +
                 (". A 3rd post gets about half the views: wait for tomorrow." if len(t) >= 2 else "."))
    lines.append(f"Normal post lately: ~{TYPICAL[c]['normal']:,} views. Last {n} posts (newest first):")
    for r in df.head(n).itertuples():
        f = _fmt(r)
        title = r.article_title if f == "Article" else None
        sh = viral_shapes(r.text or "", f.lower() if f != "QRT" else "qrt", False, title)
        first = (title or (r.text or "").strip().split("\n")[0])[:70]
        lines.append(f"  {r.ts:%d %b %H:%M} UTC  {NAME[f]:<10} {int(r.view_count or 0):>8,} views  "
                     f"shape: {', '.join(sh) or '-':<16} {first}")
    lines.append("Use this to avoid repeating the shape or topic of the last viral attempt. (Video posts can't be "
                 "told apart here, so short-caption video quote posts show as quote posts without a shape.)")
    return "\n".join(lines)
