"""Automatic AI reviewer (Claude Opus 5.5) with a small human check.

1A: label accounts B2B / AI / Tech / none from bio + posts, using the same written rubric as the
    model's segments. Labels go to data/labels/1A_ai_labels.csv (grader "ai", never mixed with
    human labels). Accounts where the model and the AI disagree, plus 10 random agreed accounts a
    week (the audit that keeps the AI honest), go to reports/1A_human_queue.csv for people.
2A: judge each Engage-list post "worth @client replying to?" -> engage_ai table.

Sent through the Message Batches API (50% cheaper; results keyed by custom_id). Refusals, errors
and malformed answers are recorded as 'skipped' with the reason, never guessed.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from .seedmap import ROOT, load_config

MODEL = "claude-opus-5-5"
SEGMENTS = ["b2b", "ai", "tech", "none"]
AI_LABELS = ROOT / "data" / "labels" / "1A_ai_labels.csv"
HUMAN_QUEUE = ROOT / "reports" / "1A_human_queue.csv"
AUDIT_PER_WEEK = 10
# Opus 5.5 list price per million tokens; the Batches API bills half
PRICE_IN, PRICE_OUT, BATCH_DISCOUNT = 4.00, 20.00, 0.5

SEGMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "segment": {"type": "string", "enum": SEGMENTS},
        "also": {"type": "string", "enum": ["b2b", "ai", "tech", ""]},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["segment", "also", "confidence", "reason"],
    "additionalProperties": False,
}
LIST_SCHEMA = {
    "type": "object",
    "properties": {"worth": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["worth", "reason"],
    "additionalProperties": False,
}


def has_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


# ------------------------------------------------------------------ prompts
def segment_system(cfg: dict) -> str:
    seg = cfg["segments"]
    lines = [
        "You label X (Twitter) accounts for an agency that grows founders' audiences on X.",
        "Decide which audience segment the account belongs to, judging from its bio and its own posts.",
        "",
        "Segments:",
    ]
    for key in ["b2b", "ai", "tech"]:
        lines.append(f"- {key}: {' '.join(seg[key]['description'].split())}")
    lines += [
        "- none: not clearly any of the above. This includes these off-topic kinds of accounts:",
    ]
    for name, text in (cfg.get("exclude") or {}).items():
        lines.append(f"  - {name}: {text}")
    lines += [
        "",
        "Rules:",
        "- Judge what the account actually posts about, not buzzwords alone. An account that only mentions AI "
        "while promoting crypto tokens or giveaways is 'none'.",
        "- 'also' is a second segment only when the account genuinely belongs to two (e.g. an AI founder selling "
        "to businesses: segment ai, also b2b). Otherwise use an empty string.",
        "- confidence: 0 to 1, how sure you are of 'segment'. Use below 0.6 when the evidence is thin.",
        "- reason: one short sentence a non-expert can check against the bio and posts.",
    ]
    return "\n".join(lines)


def account_prompt(username: str, bio: str | None, posts: list[str]) -> str:
    shown = "\n".join(f"- {p[:400]}" for p in posts[:3]) or "- (no posts available)"
    return f"Account: @{username}\nBio: {bio or '(no bio)'}\nTop posts:\n{shown}"


def list_system() -> str:
    return "\n".join([
        "You check a daily list of X posts that an agency's team may reply to on behalf of a client.",
        "Decide if replying to the post is worth the client's time: the post should be on a topic the client's "
        "audience cares about, and leave room for a real, useful reply (a point, a number, a question, a short "
        "story). Personal life updates, jokes, news with nothing to add, giveaways and engagement bait are not worth it.",
        "reason: one short sentence.",
    ])


def list_prompt(client: str, audience: str, author: str, text: str) -> str:
    return (f"Client: @{client}\nClient's audience: {audience}\n\nPost by @{author}:\n{(text or '')[:1200]}\n\n"
            "Is this post worth the client replying to?")


# ------------------------------------------------------------------ batches
def _request(custom_id: str, system: str, user: str, schema: dict, max_tokens: int = 2048, effort: str = "low"):
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    return Request(custom_id=custom_id, params=MessageCreateParamsNonStreaming(
        model=MODEL,
        max_tokens=max_tokens,
        # the rubric is identical for every request: cache it
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    ))


def parse_result(result, schema: dict) -> dict:
    """One batch result -> {'status': 'ok', **fields} or {'status': 'skipped', 'reason': ...}."""
    kind = result.result.type
    if kind != "succeeded":
        detail = getattr(getattr(result.result, "error", None), "type", "") or ""
        return {"status": "skipped", "reason": f"batch result {kind} {detail}".strip()}
    msg = result.result.message
    if msg.stop_reason == "refusal":
        cat = getattr(getattr(msg, "stop_details", None), "category", None)
        return {"status": "skipped", "reason": f"model declined ({cat or 'no category'})"}
    if msg.stop_reason == "max_tokens":
        return {"status": "skipped", "reason": "answer cut off (max_tokens)"}
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"status": "skipped", "reason": "answer was not valid JSON"}
    missing = [k for k in schema["required"] if k not in data]
    if missing:
        return {"status": "skipped", "reason": f"answer missing {missing}"}
    for k, spec in schema["properties"].items():
        if "enum" in spec and data[k] not in spec["enum"]:
            return {"status": "skipped", "reason": f"invalid {k}: {data[k]!r}"}
    return {"status": "ok", **data}


def _retry(fn, tries: int = 8, wait: float = 15):
    """A dropped connection while waiting must not lose a batch that is still running at Anthropic."""
    import anthropic
    for i in range(tries):
        try:
            return fn()
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.InternalServerError):
            if i == tries - 1:
                raise
            time.sleep(wait * (i + 1))


def run_batch(client, requests: list, schema: dict, poll: float = 30, timeout: float = 4 * 3600,
              resume_id: str | None = None) -> tuple[dict, dict]:
    """Submit (or, with resume_id, pick up an already-submitted) batch, wait, and parse the results."""
    if not requests and not resume_id:
        return {}, {"requests": 0, "cost_usd": 0.0}
    if resume_id:
        batch = _retry(lambda: client.messages.batches.retrieve(resume_id))
        print(f"batch {batch.id}: resumed")
    else:
        batch = client.messages.batches.create(requests=requests)
        print(f"batch {batch.id}: {len(requests)} requests")
    end = time.time() + timeout
    while True:
        batch = _retry(lambda: client.messages.batches.retrieve(batch.id))
        if batch.processing_status == "ended":
            break
        if time.time() > end:
            raise TimeoutError(f"batch {batch.id} still {batch.processing_status}")
        time.sleep(poll)
    out, tin, tout = {}, 0, 0
    for r in _retry(lambda: list(client.messages.batches.results(batch.id))):
        out[r.custom_id] = parse_result(r, schema)
        if r.result.type == "succeeded":
            u = r.result.message.usage
            tin += (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)
            tin += 0.1 * (getattr(u, "cache_read_input_tokens", 0) or 0)  # cache reads bill at ~10%
            tout += u.output_tokens or 0
    cost = (tin * PRICE_IN + tout * PRICE_OUT) / 1e6 * BATCH_DISCOUNT
    counts = batch.request_counts
    return out, {"requests": len(requests) or counts.succeeded + counts.errored, "succeeded": counts.succeeded, "errored": counts.errored,
                 "cost_usd": round(cost, 4)}


# ------------------------------------------------------------------ 1A accounts
def _account_inputs(con: duckdb.DuckDBPyConnection, usernames: list[str]) -> pd.DataFrame:
    con.execute("CREATE OR REPLACE TEMP TABLE _rv AS SELECT unnest(?::VARCHAR[]) AS u", [usernames])
    return con.execute("""
        WITH posts AS (
            SELECT lower(username) u, text,
                   row_number() OVER (PARTITION BY lower(username) ORDER BY like_count DESC NULLS LAST) rn
            FROM tweets WHERE lower(username) IN (SELECT u FROM _rv) AND NOT coalesce(is_retweet, false)
              AND length(text) > 30)
        SELECT r.u AS username, p.description AS bio, list(posts.text ORDER BY posts.rn) AS posts
        FROM _rv r LEFT JOIN profiles p ON p.handle = r.u
        LEFT JOIN posts ON posts.u = r.u AND posts.rn <= 3
        GROUP BY 1, 2""").df()


def build_queue(ai: pd.DataFrame, model: pd.DataFrame, human_done: set[str], week_seed: int,
                audit_n: int = AUDIT_PER_WEEK) -> pd.DataFrame:
    """Disagreements (AI segment is neither the model's main nor 2nd) + a random audit of agreed ones."""
    m = ai[ai.status == "ok"].merge(model[["username", "segment", "also"]].rename(
        columns={"segment": "model_segment", "also": "model_also"}), on="username", how="inner")
    m = m[~m.username.isin(human_done)]
    agree = (m.segment == m.model_segment) | (m.segment == m.model_also.fillna(""))
    disagree = m[~agree].assign(kind="AI and model disagree")
    pool = m[agree]
    audit = pool.sample(min(audit_n, len(pool)), random_state=week_seed).assign(kind="random audit")
    return pd.concat([disagree, audit], ignore_index=True)


def review_accounts(con: duckdb.DuckDBPyConnection, client, limit: int = 300, resume_id: str | None = None) -> dict:
    cfg = load_config()
    sample = pd.read_csv(ROOT / "reports" / "1A_segment_sample.csv")
    done = set(pd.read_csv(AI_LABELS, dtype=str).query("status == 'ok'").username.str.lower())         if AI_LABELS.exists() else set()
    # 1) the fixed sample (once), then 2) fresh random accounts with a bio, different every week, so the
    # evidence behind the model's accuracy keeps growing instead of re-asking about the same 150 accounts.
    targets = [u for u in dict.fromkeys(sample.username.str.lower()) if u not in done]
    week = date.today().isocalendar()
    fresh = con.execute("""SELECT s.username FROM account_segments s JOIN profiles p ON p.handle = s.username
                           WHERE p.description IS NOT NULL AND length(p.description) > 20
                           ORDER BY hash(s.username || ?)""", [str(week.year * 100 + week.week)]).df().username
    targets += [u for u in fresh if u not in done and u not in set(targets)][:max(0, limit - len(targets))]
    targets = targets[:limit]
    inputs = _account_inputs(con, targets)
    system = segment_system(cfg)
    reqs = [_request(f"acct-{r.username}"[:64], system,
                     account_prompt(r.username, r.bio if isinstance(r.bio, str) else None,
                                    [p for p in (r.posts if r.posts is not None else []) if isinstance(p, str)]),
                     SEGMENT_SCHEMA)
            for r in inputs.itertuples()]
    results, stats = run_batch(client, [] if resume_id else reqs, SEGMENT_SCHEMA, resume_id=resume_id)
    rows = [{"username": cid[len("acct-"):], **res} for cid, res in results.items()]
    ai = pd.DataFrame(rows)
    ai["reviewed_at"] = date.today().isoformat()
    ai["model"] = MODEL
    for col in ["segment", "also", "confidence", "reason"]:
        if col not in ai.columns:
            ai[col] = None
    # keep the latest AI answer per account
    prior = pd.read_csv(AI_LABELS, dtype=str) if AI_LABELS.exists() else pd.DataFrame(columns=ai.columns)
    merged = pd.concat([prior[~prior.username.isin(ai.username)], ai.astype(str)], ignore_index=True)
    AI_LABELS.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(AI_LABELS, index=False)

    from .segments import LABELS
    labels = pd.read_csv(LABELS, dtype=str)
    human_done = set(labels[labels.grader == "user"].username)
    model = con.execute("SELECT username, segment, also FROM account_segments").df()
    week = date.today().isocalendar()
    queue = build_queue(ai.assign(confidence=pd.to_numeric(ai.confidence, errors="coerce")), model, human_done,
                        week_seed=week.year * 100 + week.week)
    queue = queue.merge(inputs[["username", "bio"]], on="username", how="left")
    queue["url"] = "https://x.com/" + queue.username
    cols = ["kind", "username", "url", "model_segment", "model_also", "segment", "also", "confidence", "reason", "bio"]
    queue = queue[cols].rename(columns={"segment": "ai_segment", "also": "ai_also", "reason": "ai_reason",
                                        "confidence": "ai_confidence"})
    queue.to_csv(HUMAN_QUEUE, index=False, encoding="utf-8-sig")
    ok = ai[ai.status == "ok"]
    return {**stats, "labelled": len(ok), "skipped": int((ai.status != "ok").sum()),
            "queue_disagree": int((queue.kind == "AI and model disagree").sum()),
            "queue_audit": int((queue.kind == "random audit").sum())}


# ------------------------------------------------------------------ 2A list
def review_list(con: duckdb.DuckDBPyConnection, client, limit: int | None = None,
                timeout: float = 4 * 3600) -> dict:
    cfg = load_config()
    # audiences live in config (GitHub runners have no access to the local content-agent index)
    audience = {k.lower(): v for k, v in (cfg.get("client_audience") or {}).items()}
    lst = con.execute("""SELECT client, tweet_id, author, text FROM engage_list
                         WHERE list_date = (SELECT max(list_date) FROM engage_list)""").df()
    done = set(con.execute("SELECT tweet_id FROM engage_ai").df().tweet_id) if con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name='engage_ai'").fetchall() else set()
    lst = lst[~lst.tweet_id.isin(done)]
    if limit:
        lst = lst.head(limit)
    system = list_system()
    reqs = [_request(f"post-{r.tweet_id}", system,
                     list_prompt(r.client, audience.get(r.client.lower(), "founders and operators in the client's "
                                                        "niche (see the client's segments)"), r.author, r.text),
                     LIST_SCHEMA)
            for r in lst.itertuples()]
    results, stats = run_batch(client, reqs, LIST_SCHEMA, timeout=timeout)
    rows = pd.DataFrame([{"tweet_id": cid[len("post-"):], "status": res["status"],
                          "worth": res.get("worth"), "reason": res.get("reason")} for cid, res in results.items()])
    if len(rows):
        rows["reviewed_at"] = date.today().isoformat()
        con.execute("""CREATE TABLE IF NOT EXISTS engage_ai (tweet_id VARCHAR, status VARCHAR, worth BOOLEAN,
                       reason VARCHAR, reviewed_at VARCHAR)""")
        con.execute("INSERT INTO engage_ai SELECT tweet_id, status, worth, reason, reviewed_at FROM rows")
    ok = rows[rows.status == "ok"] if len(rows) else rows
    return {**stats, "judged": len(ok), "worth": int(ok.worth.sum()) if len(ok) else 0}
