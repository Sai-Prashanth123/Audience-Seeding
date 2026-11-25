"""Check a draft against the proven X-winner rules, in plain words, plus the forecaster's expected views.

    uv run seeding winners-check --client alex --format article --text "..." [--video] [--image] [--post-no 2]

Rules come from the Mar-Nov 2026 analysis (reports/winners/). Each was found by the Bayesian model, agreed with
the same-topic post pairs, and was re-checked on the clients' last 90 days of real posts (25 Nov 2026). Rules that
no longer held there were dropped: a number in the article title, and "no number in the first line".
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

CLIENT = {"alex": "itsalexvacca", "michel": "michlieben", "mich": "michlieben", "kenny": "kenny_gtm",
          "itsalexvacca": "itsalexvacca", "michlieben": "michlieben", "kenny_gtm": "kenny_gtm"}
FORMATS = {"article": "Article", "qrt": "QRT", "quote": "QRT", "thread": "Thread", "video": "Video", "tweet": "Tweet"}

# typical (median) views per format, each client's real posts in the last 90 days (to 25 Nov 2026)
TYPICAL = {
    "itsalexvacca": {"normal": 4500, "Article": 9600, "Video": 5200, "QRT": 3100, "Thread": 2000, "Tweet": 2800},
    "michlieben": {"normal": 3300, "Article": 5000, "Thread": 3800, "QRT": 3100, "Tweet": 1600, "Video": 1100},
    "kenny_gtm": {"normal": 1900, "Article": 2600, "Thread": 2400, "QRT": 600, "Tweet": 300},
}
URL = re.compile(r"https?://\S+")
GIVEAWAY = re.compile(r"giv(e|ing) (it |it all |them |this |the whole \w+ |all of (it|them) |all \d+ )?away|"
                      r"\b(comment|reply)\b[^.\n]{0,50}\b(get|send|dm|share)\b|\bfor free\b|"
                      r"free (template|playbook|guide|access)|(^|[.!]\s+)free\.?\s*$", re.I | re.M)
HYPE = re.compile(r"\b(insane|crazy|wild|mind[- ]?blowing|unreal|game[- ]?changer|absurd)\b", re.I)
ANGER = re.compile(r"\b(stop|wrong|dead|lie|lies|scam|broken|garbage|trash|nonsense|stupid|hate|worst)\b", re.I)

NAME = {"Article": "article", "QRT": "quote post", "Thread": "thread", "Video": "video", "Tweet": "plain tweet"}

# Viral shapes: 4,358 posts from the 3 clients + 12 similar accounts (Mar-Nov 2026), split into
# "before" (Mar-Aug) and "lately" (last 90 days). All posts: typical ~2,700-2,900, 2 in 10 pass 10k, 1 in 60 hit 100k.
VIRAL = {
    "teardown": ("Breakdown of a famous company's GTM ($B company)",
                 "lately typical ~9,000 views, 4 in 10 pass 10k; about 1 in 10 ever hit 100k. Rising, and barely "
                 "used by the clients yet"),
    "thennow": ("Then vs now (\"2023: ... / today: ...\")",
                "lately typical ~7,600 views (few posts), 3 in 10 pass 10k; about 1 in 9 ever hit 100k"),
    "meme": ("Short caption over a video, quoting your own article/post",
             "lately typical ~4,900 views, 3-4 in 10 pass 10k (it was ~13,200 before: fading as they use it more, "
             "but still above a normal post)"),
    "bootstrap": ("Bootstrapped vs VC money", "lately typical ~3,500 views, 3 in 10 pass 10k; about 1 in 20 hit 100k"),
    "giveaway": ("Giveaway of a real asset",
                 "lately typical ~3,000 views, 1-2 in 10 pass 10k (it was ~7,800 before: the audience has seen many "
                 "giveaways, so only a NEW asset works)"),
    "belief": ("Quoted common belief as the first line, then the proof",
               "lately typical ~2,900 views, 1 in 10 pass 10k; a swing: about 1 in 20 ever hit 100k (Alex 292k, Michel 133k)"),
}


def _first(t: str) -> str:
    return next((line.strip() for line in t.split("\n") if line.strip()), "")


def viral_shapes(text: str, fmt: str, video: bool = False, title: str | None = None) -> list[str]:
    f = FORMATS[fmt.lower()]
    body = URL.sub("", text).strip()
    t = f"{title or ''}\n{body}"
    first = _first(body)
    out = []
    if re.search(r"\b(breakdown|teardown|inside|how|behind)\b.{0,60}\$\d+(\.\d+)?\s?B\b|\bis worth \$\d+(\.\d+)?\s?B\b|"
                 r"\$\d+(\.\d+)?\s?B\b.{0,40}\b(strategy|playbook|gtm|acquisition|outbound)\b", t, re.I):
        out.append("teardown")
    if re.search(r"(?im)^(me in )?(19|20)\d\d\s*:|back in the day|^back then:\s*$|\b(in |\()(19|20)\d\d\)?:?\s*$", t):
        out.append("thennow")
    if f == "QRT" and video and len(body.split()) <= 12:
        out.append("meme")
    if re.search(r"bootstrap|\bno vc\b|vc money|without (vc|funding)", t, re.I):
        out.append("bootstrap")
    if GIVEAWAY.search(text):
        out.append("giveaway")
    if re.match(r'^["“][^"”]{3,70}["”]\s*$', first):
        out.append("belief")
    return out


@dataclass
class Check:
    ok: bool | None          # None = does not apply
    rule: str
    why: str


def _weak(c: str, f: str) -> bool:
    """A format is weak for a client when its typical post is well under their normal post (last 90 days).
    Quote posts are the push format for Alex and Michel, so they are judged by the media rule instead."""
    t = TYPICAL[c]
    if f == "Article" or (f == "QRT" and c != "kenny_gtm"):
        return False
    return t.get(f, t["normal"]) < 0.8 * t["normal"]


def checks(text: str, client: str, fmt: str, video: bool = False, image: bool = False, post_no: int = 1,
           title: str | None = None) -> list[Check]:
    c = CLIENT[client.lower()]
    f = FORMATS[fmt.lower()]
    body = URL.sub("", text).strip()
    first = _first(body)
    words = len(body.split())
    shapes = viral_shapes(text, fmt, video, title)
    out = []
    t = TYPICAL[c]
    best = max((k for k in t if k != "normal"), key=t.get)
    if _weak(c, f) and not (f == "Thread" and "thennow" in shapes):
        extra = " Even short-caption video quote posts: his one try got under 200 views." if f == "QRT" else ""
        out.append(Check(False, f"Format: {NAME[f]} is one of this client's weaker formats",
                         f"lately a typical {NAME[f]} gets ~{t.get(f, t['normal']):,} views; a typical "
                         f"{NAME[best]} gets ~{t[best]:,}; a normal post ~{t['normal']:,}.{extra}"))
    else:
        note = " (allowed: then-vs-now shape)" if f == "Thread" and _weak(c, f) else ""
        out.append(Check(True, f"Format: {NAME[f]}{note}",
                         f"lately a typical {NAME[f]} gets ~{t.get(f, t['normal']):,} views (normal ~{t['normal']:,})"))
    if f == "QRT":
        out.append(Check(video or image, "Quote post has a video or image attached",
                         "in the last 90 days quote posts with media still beat text-only ones by about half again"))
    if f == "Article":
        tt = title or first
        out.append(Check(bool(re.search(r"\b(how to|guide|playbook|system|full course|complete|step|breakdown)\b",
                                        tt, re.I)),
                         "Article title promises a complete system or guide",
                         "titles that promise the whole system still won in the last 90 days: \"How to Build "
                         "Services-as-Software Business\" (867k), \"How to Become a GTM Engineer: The Complete Guide\" (98k)"))
    if f != "Article":
        out.append(Check(None if "belief" in shapes else not re.search(r"\byou(r)?\b", first, re.I),
                         "First line does not start with \"you\"",
                         "in same-topic pairs, 7 in 10 losing posts had \"you\" in the first line"))
        out.append(Check(not first.endswith("?"), "First line is not a question",
                         "16 of 18 same-topic pairs with a question opener lost"))
        out.append(Check(len(first.split()) <= 14, "First line is short (14 words or fewer)",
                         "winners in same-topic pairs had shorter first lines"))
        out.append(Check(None if "meme" in shapes else bool(GIVEAWAY.search(text)),
                         "Gives something away / asks people to comment for it",
                         "still a little above posts without one in the last 90 days, but much weaker than before "
                         "(the audience has seen many giveaways): it only works with a NEW asset"))
    out.append(Check(None if "meme" in shapes else bool(re.search(r"[\$€£]\s?\d", body)),
                     "Money proof in the body ($ figure)",
                     "posts with a $ figure still beat the same kind of post without one in the last 90 days"))
    out.append(Check(not (HYPE.search(body) or ANGER.search(first)), "No hype or angry words",
                     "posts with hype or angry words got far fewer views, before and in the last 90 days"))
    lim = 150 if f in ("Tweet", "QRT", "Video") else 400 if f == "Thread" else None
    if lim:
        out.append(Check(words <= lim, f"Fewer words (this has {words}; aim for {lim} or fewer)",
                         "shorter posts won in same-topic pairs; each extra block of text cost views"))
    out.append(Check(post_no <= 2, f"Post #{post_no} of the day, UTC (keep it to 2)",
                     "a 3rd post the same day got about half the views of the 2nd, before and in the last 90 days"))
    return out


def forecast(client: str, text: str, fmt: str, has_media: bool, title: str | None) -> dict:
    """Step 3 forecaster (pre-post expected views with an 80% range). Opens the database read-only and retries
    if another process holds it, so several writers can check drafts at once."""
    import duckdb
    import pandas as pd
    from .. import store
    from ..forecast import serve
    err = ""
    for _ in range(8):
        try:
            con = duckdb.connect(str(store.DB_PATH), read_only=True)
            try:
                c = CLIENT[client.lower()]
                when = pd.Timestamp.now(tz="UTC")
                hist = serve.client_history(con, c, when)
                f = {"Article": "article", "QRT": "quote post", "Thread": "thread"}.get(FORMATS[fmt.lower()])
                return serve.predict(hist, c, text, when, f, has_media, title)["actions"]["views"]
            finally:
                con.close()
        except Exception as e:  # noqa: BLE001 - the checklist still works without the forecaster
            err = str(e).splitlines()[0][:160]
            if "lock" not in err.lower() and "conflicting" not in err.lower():
                break
            time.sleep(1.5)
    return {"error": err}


def report(text: str, client: str, fmt: str, video=False, image=False, post_no=1, title=None,
           with_forecast=True) -> str:
    cs = [c for c in checks(text, client, fmt, video, image, post_no, title) if c.ok is not None]
    passed = sum(c.ok for c in cs)
    lines = [f"Rules followed: {passed} of {len(cs)}"]
    vs = viral_shapes(text, fmt, video, title)
    if vs:
        lines.append("Viral shape: " + "; ".join(f"{VIRAL[v][0]} ({VIRAL[v][1]})" for v in vs))
    else:
        lines.append("Viral shape: none. Almost every 100k post used one of the shapes in x-winners-playbook "
                     "viral.md; without one, about 1 in 60 gets there.")
    for c in cs:
        lines.append(f"  {'OK ' if c.ok else 'FIX'}  {c.rule}" + ("" if c.ok else f"\n        why: {c.why}"))
    normal = TYPICAL[CLIENT[client.lower()]]["normal"]
    if with_forecast:
        fc = forecast(client, text, fmt, video or image, title)
        if fc and "expected" in fc:
            lines.append(f"Forecast: about {fc['expected']:,.0f} views (8 in 10 posts like this land between "
                         f"{fc['low']:,.0f} and {fc['high']:,.0f}). Their normal post in the last 90 days: ~{normal:,}.")
            if "meme" in vs:
                lines.append("  note: the forecast reads the words, not the video, so it under-rates this shape. "
                             "Lately their real posts like this got ~4,900 views typical.")
        else:
            lines.append(f"Forecast: not available ({(fc or {}).get('error') or 'no data'}). The rules above still "
                         f"apply. Their normal post in the last 90 days: ~{normal:,}.")
    lines.append("Proof (their real posts, last 90 days): the third of posts that followed the most rules got "
                 "Alex ~8,200 vs ~3,100 views, Michel ~5,200 vs ~2,200, Kenny ~3,100 vs ~300. Between two of their "
                 "posts it picked the one that did better about 7 times in 10, so write 2-3 versions.")
    return "\n".join(lines)
