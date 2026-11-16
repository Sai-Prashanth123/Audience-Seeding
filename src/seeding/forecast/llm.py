"""Claude layers of the forecaster: a content grader, an in-context forecaster, and a real-person audience panel.

All three use Claude Opus 5.5 through the Message Batches API (half price) for backtests, with structured JSON
output (reviewer._request / reviewer.run_batch). Nothing here is trusted by default: each output becomes a
candidate member or feature, and is kept only if it passes the protocol in reports/3_protocol.md.

  grader      scores a post's text: hook, specificity, novelty, contrarian take, emotion, practical value,
              call to action, engagement bait, negative-signal risk (a proxy for X's NotInterested / Mute /
              Report weights, which are never public), reply invitation.
  forecaster  in-context forecasting [Gruver et al. 2023]: Claude sees the client's last 40 matured posts WITH
              their real results, then estimates each action for the new post, with an 80% range.
  panel       silicon samples [Argyle et al. 2023] of REAL people from our data (past engagers + seed-map
              members): Claude role-plays each, from their own bio and posts, deciding scroll / like / reply /
              repost / quote. Persona and action schema after OASIS [Yang et al. 2024].
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import ledger

ACTIONS = ["views", "likes", "replies", "reposts", "quotes", "bookmarks"]
GRADE_FIELDS = ["hook", "specificity", "novelty", "contrarian", "emotion", "practical_value", "cta", "bait",
                "negative_risk", "reply_invite"]
ledger.SCHEMAS["llm_grades"] = (["tweet_id", "model", "graded_at"] + GRADE_FIELDS, ["tweet_id"])

# ------------------------------------------------------------------ grader
GRADE_SYSTEM = """You grade X (Twitter) posts for a content team. Score the post text only, each 0-10 (integers):
hook: how strongly the first line makes a scrolling reader stop.
specificity: concrete numbers, names, steps, examples (10) vs vague generalities (0).
novelty: a fresh idea or angle for its audience (10) vs a recycled take (0).
contrarian: goes against common belief in its niche.
emotion: emotional intensity of any kind.
practical_value: a reader can act on it today.
cta: strength of any call to action (comment, repost, follow, link, DM).
bait: engagement bait (comment-to-get, giveaways, "like if", rage bait, follow-for-follow).
negative_risk: how likely typical readers are to hit "not interested", mute, block or report (spammy, offensive,
  misleading, off-putting self-promotion).
reply_invite: how naturally it invites replies (open question, debate, ask for opinions).
Judge the text as written. Do not guess the author's popularity."""

GRADE_SCHEMA = {"type": "object", "additionalProperties": False, "required": GRADE_FIELDS,
                "properties": {f: {"type": "integer"} for f in GRADE_FIELDS}}


def grade_requests(posts: pd.DataFrame) -> list:
    from ..reviewer import _request
    out = []
    for r in posts.itertuples():
        text = (f"[article] {r.article_title}\n" if isinstance(getattr(r, "article_title", None), str) else "") + \
               (r.text or "")
        out.append(_request(f"g{r.tweet_id}", GRADE_SYSTEM, f"Post:\n{text[:2500]}", GRADE_SCHEMA,
                            max_tokens=1024, effort="low"))
    return out


def grade(posts: pd.DataFrame, client=None, chunk: int = 10_000) -> dict:
    """Grade posts not graded yet; results are appended to data/ledger/llm_grades.csv (paid for once)."""
    import anthropic

    from ..reviewer import MODEL, run_batch
    done = set(ledger.load("llm_grades").tweet_id)
    todo = posts[~posts.tweet_id.astype(str).isin(done)]
    client = client or anthropic.Anthropic()
    stats = {"requested": len(todo), "graded": 0, "cost_usd": 0.0}
    for i in range(0, len(todo), chunk):
        part = todo.iloc[i:i + chunk]
        res, st = run_batch(client, grade_requests(part), GRADE_SCHEMA, poll=60)
        now = pd.Timestamp.now(tz="UTC").isoformat()
        rows = [{"tweet_id": k[1:], "model": MODEL, "graded_at": now, **{f: v[f] for f in GRADE_FIELDS}}
                for k, v in res.items() if v.get("status") == "ok"]
        stats["graded"] += ledger.append("llm_grades", rows)
        stats["cost_usd"] += st.get("cost_usd", 0.0)
        print(f"graded chunk {i // chunk + 1}: {len(rows)} ok of {len(part)}; cost so far ${stats['cost_usd']:.2f}",
              flush=True)
    return stats


def grades_frame() -> pd.DataFrame:
    g = ledger.load("llm_grades")
    for f in GRADE_FIELDS:
        g[f"g_{f}"] = pd.to_numeric(g[f], errors="coerce")
    return g[["tweet_id"] + [f"g_{f}" for f in GRADE_FIELDS]]


# ------------------------------------------------------------------ in-context forecaster
FORECAST_SYSTEM = """You forecast how an X (Twitter) post will perform for its author, from the author's own history.
You get the author's recent posts with their FINAL results (counts at least 48 hours after posting), oldest first,
then a new post and when it will go out. Estimate the new post's final counts.
Reason from this author's own numbers: their typical level, how format, topic, opening line and timing moved
their results before. Most posts land near the author's usual level; move away from it only for a clear reason.
For each action give your best estimate and an 80% range (10% chance the true value is below low, 10% above high).
Keep the reason under 60 words."""

FORECAST_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ACTIONS + ["reason"],
    "properties": {**{a: {"type": "object", "additionalProperties": False, "required": ["expected", "low", "high"],
                          "properties": {"expected": {"type": "number"}, "low": {"type": "number"},
                                         "high": {"type": "number"}}} for a in ACTIONS},
                   "reason": {"type": "string"}}}

COUNT_COLS = {"views": "view_count", "likes": "like_count", "replies": "reply_count", "reposts": "retweet_count",
              "quotes": "quote_count", "bookmarks": "bookmark_count"}


def history_block(hist: pd.DataFrame) -> str:
    lines = ["date (UTC) | format | views likes replies reposts quotes bookmarks | text"]
    for r in hist.itertuples():
        counts = " ".join(str(int(getattr(r, COUNT_COLS[a]) or 0)) for a in ACTIONS)
        text = " ".join(str(r.text or "").split())[:280]
        lines.append(f"{pd.Timestamp(r.ts):%Y-%m-%d %H:%M} | {r.format} | {counts} | {text}")
    return "\n".join(lines)


def forecast_prompt(author: str, hist: pd.DataFrame, text: str, when: pd.Timestamp, fmt: str) -> str:
    med = {a: int(np.median(hist[COUNT_COLS[a]].fillna(0))) for a in ACTIONS} if len(hist) else {}
    return (f"Author: @{author}\nUsual (median of these posts): " + ", ".join(f"{a} {v}" for a, v in med.items())
            + f"\n\nHistory ({len(hist)} posts):\n{history_block(hist)}\n\n"
            f"NEW POST (goes out {pd.Timestamp(when):%Y-%m-%d %H:%M} UTC, format: {fmt}):\n{text[:2500]}")


def forecast_request(custom_id: str, prompt: str):
    from ..reviewer import _request
    return _request(custom_id, FORECAST_SYSTEM, prompt, FORECAST_SCHEMA, max_tokens=6000, effort="medium")


def matured_history(posts: pd.DataFrame, author: str, before: pd.Timestamp, n: int = 40) -> pd.DataFrame:
    """The author's latest n posts that had at least 48h to mature before `before` (same rule as the features)."""
    h = posts[(posts.author == author) & (posts.ts <= before - pd.Timedelta(hours=48))]
    return h.sort_values("ts").tail(n)


# ------------------------------------------------------------------ audience panel
PANEL_SYSTEM = """You simulate how real X (Twitter) users react to one post. You get a list of real people, each with
their own bio, a few of their recent posts, and their past interactions with the author. For EACH person, imagine the
post appears in their feed and decide what that specific person would most likely do, judging from what they
actually write about and care about. Be realistic: on X most people scroll past most posts; a like is far more
common than a reply; reposts and quotes are rare. Give probabilities, not certainties.
action: the single most likely action. p_engage: chance they like, reply, repost or quote. p_reply: chance they
reply or quote. reply: what they would most likely write if they replied (under 25 words, in their voice), or ""
if a reply is unlikely. Finally list up to 3 objections or doubts readers would raise, and say in one sentence who
reacts most."""

PANEL_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["people", "objections", "who_reacts"],
    "properties": {
        "people": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["handle", "action", "p_engage", "p_reply", "reply"],
            "properties": {"handle": {"type": "string"},
                           "action": {"type": "string", "enum": ["scroll", "like", "reply", "repost", "quote"]},
                           "p_engage": {"type": "number"}, "p_reply": {"type": "number"},
                           "reply": {"type": "string"}}}},
        "objections": {"type": "array", "items": {"type": "string"}},
        "who_reacts": {"type": "string"}}}


def build_panel(con, client: str, before: pd.Timestamp, n: int = 30, engager_share: float = 0.6,
                seed: int = 0) -> pd.DataFrame:
    """Real people for the panel, using only interactions before `before`.

    ~60% past engagers of the client (most frequent first), ~40% seed-map members in the client's niche who never
    engaged with the client (the new audience the seeding work targets). Each needs a bio or posts to read."""
    from ..engage import load_config
    segs = load_config()["client_segments"].get(next((k for k in load_config()["client_segments"]
                                                      if k.lower() == client.lower()), client), [])
    eng = con.execute("""SELECT lower(src) handle, count(*) n FROM edges
                         WHERE lower(dst) = lower(?) AND created_at < ? AND lower(src) <> lower(?)
                         GROUP BY 1 ORDER BY n DESC""", [client, before.to_pydatetime(), client]).df()
    seeds = con.execute("""SELECT lower(username) handle FROM seed_map WHERE seg IN (SELECT unnest(?::VARCHAR[]))
                           ORDER BY rank""", [segs]).df() if segs else pd.DataFrame(columns=["handle"])
    seeds = seeds[~seeds.handle.isin(eng.handle)]
    rng = np.random.default_rng(seed)
    n_eng = min(len(eng), int(round(n * engager_share)))
    pick_eng = eng.head(max(n_eng * 2, n_eng)).sample(n=n_eng, random_state=seed) if n_eng else eng.head(0)
    pool = seeds.head(300)
    pick_seed = pool.sample(n=min(len(pool), n - n_eng), random_state=int(rng.integers(1e9))) if len(pool) else pool
    people = pd.concat([pick_eng.assign(kind="past engager"), pick_seed.assign(kind="seed map", n=0)])
    if people.empty:
        return people
    con.execute("CREATE OR REPLACE TEMP TABLE _panel AS SELECT * FROM people")
    info = con.execute("""
        WITH posts AS (SELECT lower(username) u, text, row_number() OVER (PARTITION BY lower(username)
                                                                          ORDER BY created_at DESC) rn
                       FROM tweets WHERE lower(username) IN (SELECT handle FROM _panel) AND created_at < ?
                         AND NOT coalesce(is_retweet, false) AND length(text) > 30)
        SELECT p.handle, p.kind, p.n AS past_interactions, pr.description bio, s.segment,
               list(posts.text ORDER BY posts.rn) FILTER (WHERE posts.rn <= 4) AS recent
        FROM _panel p LEFT JOIN profiles pr ON pr.handle = p.handle
        LEFT JOIN account_segments s ON s.username = p.handle
        LEFT JOIN posts ON posts.u = p.handle
        GROUP BY ALL""", [before.to_pydatetime()]).df()
    info = info[info.bio.notna() | info.recent.map(lambda x: isinstance(x, (list, np.ndarray)) and len(x) > 0)]
    return info.reset_index(drop=True)


def panel_prompt(client: str, people: pd.DataFrame, text: str) -> str:
    cards = []
    for r in people.itertuples():
        recent = [" ".join(str(t).split())[:200] for t in (r.recent if isinstance(r.recent, (list, np.ndarray)) else [])]
        cards.append(f"@{r.handle} ({r.segment or 'niche unknown'}; {r.kind}; "
                     f"{int(r.past_interactions or 0)} past replies/quotes to @{client})\n"
                     f"bio: {(r.bio or '').strip()[:300]}\nrecent posts: " + " || ".join(recent))
    return (f"Author: @{client}\n\nPOST:\n{text[:2500]}\n\nPEOPLE ({len(people)}):\n\n" + "\n\n".join(cards))


def panel_request(custom_id: str, prompt: str):
    from ..reviewer import _request
    return _request(custom_id, PANEL_SYSTEM, prompt, PANEL_SCHEMA, max_tokens=12000, effort="medium")


def panel_summary(res: dict, people: pd.DataFrame) -> dict:
    """Aggregate one panel answer: engagement and reply rates overall and by niche, plus sample replies."""
    ppl = pd.DataFrame(res.get("people", []))
    if ppl.empty:
        return {}
    ppl["handle"] = ppl.handle.str.lstrip("@").str.lower()
    ppl = ppl.merge(people[["handle", "segment", "kind"]], on="handle", how="left")
    for c in ("p_engage", "p_reply"):
        ppl[c] = ppl[c].clip(0, 1)
    by_seg = ppl.groupby(ppl.segment.fillna("unknown")).p_engage.mean().round(3).to_dict()
    by_kind = ppl.groupby(ppl.kind.fillna("unknown")).p_engage.mean().round(3).to_dict()
    samples = ppl[ppl.reply.str.len() > 0].sort_values("p_reply", ascending=False).head(3)
    return {"n": len(ppl), "engage_rate": float(ppl.p_engage.mean()), "reply_rate": float(ppl.p_reply.mean()),
            "actions": ppl.action.value_counts().to_dict(), "engage_by_niche": by_seg, "engage_by_kind": by_kind,
            "sample_replies": [{"handle": r.handle, "reply": r.reply} for r in samples.itertuples()],
            "objections": res.get("objections", []), "who_reacts": res.get("who_reacts", "")}


def to_quantiles(res: dict) -> dict:
    """Forecaster answer -> log1p quantiles per action, plus a derived X score."""
    from .. import xalgo
    out = {}
    for a in ACTIONS:
        v = res.get(a, {})
        e, lo, hi = (max(float(v.get(k, 0) or 0), 0.0) for k in ("expected", "low", "high"))
        lo, hi = min(lo, e), max(hi, e)
        out[a] = {0.1: np.log1p(lo), 0.5: np.log1p(e), 0.9: np.log1p(hi)}
    w = {"likes": xalgo.ACTION_WEIGHTS["like"], "replies": xalgo.ACTION_WEIGHTS["reply"],
         "reposts": xalgo.ACTION_WEIGHTS["repost"], "quotes": xalgo.ACTION_WEIGHTS["quote"]}
    out["xscore"] = {q: np.log1p(sum(np.expm1(out[a][q]) * wt for a, wt in w.items())) for q in (0.1, 0.5, 0.9)}
    return out


def dumps(x) -> str:
    return json.dumps(x, default=str)
