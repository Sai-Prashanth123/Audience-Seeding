"""Check a draft against the proven X-winner rules, in plain words, plus the forecaster's expected views.

    uv run seeding winners-check --client alex --format article --text "..." [--video] [--image] [--post-no 2]

Rules come from the Mar-Nov 2026 analysis (reports/winners/): each was found by the Bayesian model, agreed with
the same-topic post pairs, and held up on the last 90 days of posts the analysis never saw.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CLIENT = {"alex": "itsalexvacca", "michel": "michlieben", "mich": "michlieben", "kenny": "kenny_gtm",
          "itsalexvacca": "itsalexvacca", "michlieben": "michlieben", "kenny_gtm": "kenny_gtm"}
FORMATS = {"article": "Article", "qrt": "QRT", "quote": "QRT", "thread": "Thread", "video": "Video", "tweet": "Tweet"}

# typical views per format today (Mar-Nov 2026 medians scaled to each client's last-90-day reach)
TYPICAL = {
    "itsalexvacca": {"normal": 4300, "Article": 7000, "Video": 4600, "QRT": 3800, "Thread": 1500, "Tweet": 1500},
    "michlieben": {"normal": 3300, "Article": 4900, "QRT": 2900, "Thread": 2300, "Tweet": 2100, "Video": 1400},
    "kenny_gtm": {"normal": 2100, "Article": 11300, "Thread": 9400, "Tweet": 1500, "QRT": 1400},
}
URL = re.compile(r"https?://\S+")
GIVEAWAY = re.compile(r"giv(e|ing) (it all |them |this |the whole \w+ |all of (it|them) )?away|"
                      r"\b(comment|reply)\b[^.\n]{0,50}\b(get|send|dm|share)\b|\bfor free\b|"
                      r"free (template|playbook|guide|access)|(^|[.!]\s+)free\.?\s*$", re.I | re.M)
HYPE = re.compile(r"\b(insane|crazy|wild|mind[- ]?blowing|unreal|game[- ]?changer|absurd)\b", re.I)
ANGER = re.compile(r"\b(stop|wrong|dead|lie|lies|scam|broken|garbage|trash|nonsense|stupid|hate|worst)\b", re.I)


NAME = {"Article": "article", "QRT": "quote post", "Thread": "thread", "Video": "video", "Tweet": "plain tweet"}


# Viral shapes: measured on 4,358 posts from the 3 clients + 12 similar accounts (Mar-Nov 2026).
# Across all posts: typical ~2,900 views, 2 in 10 pass 10k, about 1 in 60 pass 100k.
VIRAL = {
    "meme": ("Short caption over a video, quoting your own article/post",
             "typical ~10,000 views, 5 in 10 pass 10k, about 1 in 13 pass 100k (Alex ~10,300 and 6 in 10; "
             "Michel ~9,200 and 5 in 10). Their best repeatable viral shape."),
    "teardown": ("Breakdown of a famous company's GTM ($B company)",
                 "typical ~6,900 views, 4 in 10 pass 10k, about 1 in 10 pass 100k. Barely used by the clients yet "
                 "(6 posts); peers got 401k and 447k with it."),
    "thennow": ("Then vs now (\"2023: ... / today: ...\")",
                "about 1 in 9 pass 100k (vs 1 in 60 overall), but the typical one gets ~3,500: a big swing"),
    "belief": ("Quoted common belief as the first line, then the proof",
               "about 1 in 20 pass 100k (Alex 292k, Michel 133k), but the typical one gets ~3,300: a big swing"),
    "giveaway": ("Giveaway of a real asset",
                 "typical ~4,800 views, 3 in 10 pass 10k, about 1 in 35 pass 100k"),
    "bootstrap": ("Bootstrapped vs VC money",
                  "typical ~3,800 views, 3 in 10 pass 10k, about 1 in 20 pass 100k"),
}


def viral_shapes(text: str, fmt: str, video: bool = False, title: str | None = None) -> list[str]:
    f = FORMATS[fmt.lower()]
    body = URL.sub("", text).strip()
    t = f"{title or ''}\n{body}"
    first = _first(body)
    out = []
    if f == "QRT" and video and len(body.split()) <= 12:
        out.append("meme")
    if re.search(r"(breakdown|teardown|inside) of .{0,40}\$\d+(\.\d)?\s?B\b|\$\d+(\.\d)?B\b", t, re.I):
        out.append("teardown")
    if re.search(r"(?im)^(me in )?(19|20)\d\d\s*:|back in the day|^back then:\s*$|\b(19|20)\d\d\):?\s*$", t):
        out.append("thennow")
    if re.match(r'^["“][^"”]{3,70}["”]\s*$', first):
        out.append("belief")
    if GIVEAWAY.search(text):
        out.append("giveaway")
    if re.search(r"bootstrap|\bno vc\b|vc money|without (vc|funding)", t, re.I):
        out.append("bootstrap")
    return out


@dataclass
class Check:
    ok: bool | None          # None = does not apply
    rule: str
    why: str


def _first(t: str) -> str:
    return next((l.strip() for l in t.split("\n") if l.strip()), "")


def checks(text: str, client: str, fmt: str, video: bool = False, image: bool = False, post_no: int = 1,
           title: str | None = None) -> list[Check]:
    c = CLIENT[client.lower()]
    f = FORMATS[fmt.lower()]
    body = URL.sub("", text).strip()
    first = _first(body)
    words = len(body.split())
    out = []
    t = TYPICAL[c]
    if f in ("Tweet", "Thread", "Video") and c != "kenny_gtm" or f in ("Tweet", "QRT") and c == "kenny_gtm":
        best = max((k for k in t if k != "normal"), key=t.get)
        out.append(Check(False, f"Format: {NAME[f]} is one of this client's weaker formats",
                         f"a typical {NAME[f]} gets ~{t.get(f, t['normal']):,} views; a typical {NAME[best]} gets "
                         f"~{t[best]:,}. Consider turning this into an article (or a quote post of one, with a video)."))
    else:
        out.append(Check(True, f"Format: {NAME[f]}", f"a typical {NAME[f]} gets ~{t.get(f, t['normal']):,} views "
                                               f"(a normal post: ~{t['normal']:,})"))
    if f == "QRT":
        out.append(Check(video or image, "Quote post has a video or image attached",
                         "quote posts with a video get more views than text-only ones (Alex ~4,700 vs ~3,000; "
                         "Michel ~3,600 vs ~2,500)"))
    if f == "Article":
        tt = title or first
        out.append(Check(bool(re.search(r"\d", tt)), "Article title has a number",
                         "most of the biggest articles had a number in the title (\"5-Step...\", \"$7M ARR\")"))
        out.append(Check(bool(re.search(r"\b(how to|guide|playbook|system|full course|complete|step)\b", tt, re.I)),
                         "Article title promises a complete system or guide",
                         "the biggest articles all promise the whole system: \"How to Build Services-as-Software "
                         "Business\" (867k), \"How to Become a GTM Engineer: The Complete Guide\" (98k)"))
    if f != "Article":
        belief = "belief" in viral_shapes(text, fmt, video)  # a quoted belief may say "you" (Michel, 133k)
        out.append(Check(None if belief else not re.search(r"\byou(r)?\b", first, re.I),
                         "First line does not start with \"you\"",
                         "in same-topic pairs, 7 in 10 losing posts had \"you\" in the first line"))
        out.append(Check(not first.endswith("?"), "First line is not a question",
                         "16 of 18 same-topic pairs with a question opener lost"))
        out.append(Check(not re.search(r"\d", first) or bool(GIVEAWAY.search(text)),
                         "No number in the first line (put it in the body)",
                         "number-first openings got ~2,100 views for Alex and ~2,700 for Michel vs ~5,000 / ~3,500 "
                         "for a plain statement"))
        out.append(Check(len(first.split()) <= 14, "First line is short (14 words or fewer)",
                         "winners in same-topic pairs had shorter first lines"))
        gw = bool(GIVEAWAY.search(text))
        meme = "meme" in viral_shapes(text, fmt, video)
        out.append(Check(None if meme else gw, "Gives something away / asks people to comment for it",
                         "giveaway openings got ~7,500 views for Alex and ~6,900 for Michel, about double a normal post"))
        out.append(Check(None if meme else bool(re.search(r"[\$€£]\s?\d", body)), "Money proof in the body ($ figure)",
                         "for Michel and Kenny, posts with a $ figure got more views than the same kind of post without one"))
    out.append(Check(not (HYPE.search(body) or ANGER.search(first)), "No hype or angry words",
                     "angry or hype wording lost in same-topic pairs; contrarian openers got ~1,400 views for Michel"))
    lim = 150 if f in ("Tweet", "QRT", "Video") else 400 if f == "Thread" else None
    if lim:
        out.append(Check(words <= lim, f"Fewer words (this has {words}; aim for {lim} or fewer)",
                         "shorter posts won in same-topic pairs; each extra block of text cost views"))
    out.append(Check(post_no <= 2, f"Post #{post_no} of the day (keep it to 2)",
                     "the 3rd post of the day got ~2,900 views for Alex and ~1,800 for Michel, about half the 2nd"))
    return out


def forecast(client: str, text: str, fmt: str, has_media: bool, title: str | None) -> dict | None:
    """Step 3 forecaster (pre-post expected views with an 80% range), if the local data is there."""
    try:
        from .. import store
        from ..forecast import serve
        import pandas as pd
        c = CLIENT[client.lower()]
        con = store.connect()
        when = pd.Timestamp.now(tz="UTC")
        hist = serve.client_history(con, c, when)
        f = {"Article": "article", "QRT": "quote post", "Thread": "thread"}.get(FORMATS[fmt.lower()])
        return serve.predict(hist, c, text, when, f, has_media, title)["actions"]["views"]
    except Exception as e:  # noqa: BLE001 - the checklist still works without the forecaster
        return {"error": str(e)}


def report(text: str, client: str, fmt: str, video=False, image=False, post_no=1, title=None,
           with_forecast=True) -> str:
    cs = [c for c in checks(text, client, fmt, video, image, post_no, title) if c.ok is not None]
    passed = sum(c.ok for c in cs)
    lines = [f"Rules followed: {passed} of {len(cs)}"]
    vs = viral_shapes(text, fmt, video, title)
    if vs:
        lines.append("Viral shape: " + "; ".join(f"{VIRAL[v][0]} ({VIRAL[v][1]})" for v in vs))
    else:
        lines.append("Viral shape: none. Posts in one of the viral shapes (see x-winners-playbook viral.md) are "
                     "the ones that reach 100k; a post without one rarely does (about 1 in 60 overall).")
    if "meme" in vs:
        lines.append("  note: the forecast below under-rates this shape (it reads the words, not the video). Their "
                     "real posts like this got ~10,000 views typical.")
    for c in cs:
        lines.append(f"  {'OK ' if c.ok else 'FIX'}  {c.rule}" + ("" if c.ok else f"\n        why: {c.why}"))
    if with_forecast:
        fc = forecast(client, text, fmt, video or image, title)
        if fc and "expected" in fc:
            lines.append(f"Forecast: about {fc['expected']:,.0f} views (8 in 10 posts like this land between "
                         f"{fc['low']:,.0f} and {fc['high']:,.0f}); a normal post now gets about {fc['usual']:,.0f}.")
    lines.append("In tests on the last 90 days, posts that followed most rules got 2-3x the views of posts that broke "
                 "them. It picks the stronger of two drafts about 2 times out of 3, so write 2-3 versions.")
    return "\n".join(lines)
