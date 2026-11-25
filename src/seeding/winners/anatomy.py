"""Writing anatomy: deterministic tags for what a post *is* (no paid API, same result every run).

Groups: hook · structure · proof · CTA · voice · emotion/arousal (Berger & Milkman 2012: high-arousal emotions,
awe/anger/anxiety, spread more than low-arousal ones) · readability · delivery (time, day position, media).
"""

from __future__ import annotations

import re
import warnings

warnings.filterwarnings("ignore", message="This pattern is interpreted as a regular expression")

import numpy as np
import pandas as pd

from .. import xalgo

URL = re.compile(r"https?://\S+")
TOOLS = re.compile(r"\b(claude(?: code)?|chatgpt|gpt-?\d|openai|gemini|codex|cursor|n8n|make\.com|zapier|clay|apollo|"
                   r"instantly|smartlead|lemlist|heyreach|hubspot|salesforce|linkedin|sales navigator|perplexity|"
                   r"notion|airtable|lovable|replit|grok|anthropic|mcp|apify|phantombuster|trigify|common room)\b", re.I)
OWN_BRANDS = re.compile(r"\b(coldiq|frontal|@frontal_ai|heyreach)\b", re.I)
EMO = {
    "awe": r"\b(insane|crazy|wild|mind[- ]?blowing|incredible|unreal|game[- ]?changer|absurd|magic|holy)\b",
    "anger": r"\b(stop|wrong|dead|lie|lies|scam|broken|garbage|trash|nonsense|stupid|hate|worst)\b",
    "anxiety": r"\b(losing|lose|risk|mistake|fail(?:ing|ed|s)?|wasting|behind|too late|miss(?:ing)? out|afraid|killing)\b",
    "money": r"[\$€£]\s?\d|\b(revenue|arr|mrr|pipeline|profit|deals?|closed|booked)\b",
    "curiosity": r"\b(secret|nobody|hidden|exact|steal|copy|most people|no one|here'?s why|the truth)\b",
}
CTA_KIND = [
    ("comment-to-get", r"\b(comment|reply)\b[^.\n]{0,50}\b(get|send|dm|share)\b|\bcomment \"?[A-Z]{2,}\"?"),
    ("dm gate", r"\bdm me\b|\bsend (me )?a dm\b"),
    ("bookmark/save", r"\b(bookmark|save this|save it)\b"),
    ("follow", r"\bfollow (me|@)"),
    ("repost", r"\b(repost|retweet|rt)\b ?(this|if)"),
    ("question to reader", r"\?\s*$"),
]


def _first_line(t: str) -> str:
    for line in (t or "").split("\n"):
        if line.strip():
            return line.strip()
    return ""


def tag(df: pd.DataFrame) -> pd.DataFrame:
    """Add anatomy columns to a winners.data frame (needs text, article_title, ts, author, media columns)."""
    d = df.copy()
    text = d.text.fillna("")
    clean = text.str.replace(URL, "", regex=True).str.strip()
    words = clean.str.split()
    d["n_words"] = words.str.len().fillna(0)
    d["n_chars"] = clean.str.len()
    lines = clean.str.split("\n")
    d["n_lines"] = lines.map(lambda ls: sum(1 for l in ls if l.strip()))
    d["blank_ratio"] = lines.map(lambda ls: sum(1 for l in ls if not l.strip()) / max(len(ls), 1))
    first = text.map(_first_line)
    d["first_line"] = first
    d["hook_words"] = first.str.split().str.len().fillna(0)
    d["hook_has_number"] = first.str.contains(r"\d").astype(int)
    d["hook_has_you"] = first.str.contains(r"\byou(r)?\b", case=False).astype(int)
    d["hook_is_question"] = first.str.strip().str.endswith("?").astype(int)
    d["numbered_steps"] = clean.str.count(r"(?m)^\s*\d{1,2}[/.)]\s")
    d["arrows"] = clean.str.count("→")
    d["bullets"] = clean.str.count(r"(?m)^\s*[•\-–✅❌✔️▪️]\s")
    d["is_list"] = ((d.numbered_steps >= 3) | (d.arrows >= 3) | (d.bullets >= 3)).astype(int)
    d["n_numbers"] = clean.str.count(r"\d+(?:[.,]\d+)?")
    d["has_dollar"] = clean.str.contains(r"[\$€£]\s?\d").astype(int)
    d["has_percent"] = clean.str.contains(r"\d\s?%").astype(int)
    d["big_number"] = clean.str.contains(r"\b\d{1,3}(?:,\d{3})+\b|\b\d+(?:\.\d+)?\s?[kKmM]\b|\b\d{4,}\b").astype(int)
    d["n_tools"] = clean.str.count(TOOLS)
    d["names_tool"] = (d.n_tools > 0).astype(int)
    d["mentions_claude"] = clean.str.contains(r"\bclaude\b", case=False).astype(int)
    d["mentions_own_brand"] = clean.str.contains(OWN_BRANDS).astype(int)
    d["n_mentions"] = clean.str.count(r"@\w+")
    d["has_link"] = (text.str.contains(URL) & d.media_kind.isin(["none", "media (unknown)"])
                     & d.article_title.isna() & ~d.is_quote).astype(int)
    cta = pd.Series("none", index=d.index)
    for name, pat in reversed(CTA_KIND):
        cta = cta.mask(text.str.contains(pat, case=False, regex=True), name)
    d["cta"] = cta
    d["has_cta"] = (cta != "none").astype(int)
    w = d.n_words.clip(lower=1)
    d["you_rate"] = clean.str.count(r"\byou(?:r|'re|'ll)?\b", flags=re.I) / w
    d["i_rate"] = clean.str.count(r"\b(?:i|i'm|i've|my|we|our)\b", flags=re.I) / w
    for k, pat in EMO.items():
        d[f"emo_{k}"] = clean.str.contains(pat, case=False, regex=True).astype(int)
    d["arousal"] = d[["emo_awe", "emo_anger", "emo_anxiety"]].max(axis=1)
    sents = clean.str.split(r"[.!?\n]+").map(lambda s: [x for x in s if x.strip()])
    d["words_per_sentence"] = [len(str(t).split()) / max(len(s), 1) for t, s in zip(clean, sents)]
    d["long_form"] = (d.n_chars > 280).astype(int)
    d["video_s"] = pd.to_numeric(d.get("video_s"), errors="coerce")
    d["quote_of_video"] = d.get("quoted_media_kind", pd.Series(index=d.index)).eq("video").astype(int)
    d["has_image"] = d.media_kind.eq("photo").astype(int)
    d["hour"] = d.ts.dt.hour
    d["weekday"] = d.ts.dt.day_of_week
    d["weekend"] = (d.weekday >= 5).astype(int)
    d = d.sort_values(["author", "ts"])
    day = d.ts.dt.floor("D")
    d["day_position"] = d.groupby(["author", day]).cumcount() + 1
    d["day_decay"] = d.day_position.map(xalgo.day_decay)
    d["gap_h"] = d.groupby("author").ts.diff().dt.total_seconds() / 3600
    d["log_gap_h"] = np.log1p(d.gap_h.fillna(48).clip(upper=24 * 14))
    return d.sort_index()


# binary/continuous features the models use (no outcome information in any of them)
FEATURES = ["n_words", "n_lines", "blank_ratio", "hook_words", "hook_has_number", "hook_has_you", "hook_is_question",
            "is_list", "numbered_steps", "arrows", "n_numbers", "has_dollar", "has_percent", "big_number", "names_tool",
            "mentions_claude", "mentions_own_brand", "n_mentions", "has_link", "has_cta", "you_rate", "i_rate",
            "emo_awe", "emo_anger", "emo_anxiety", "emo_money", "emo_curiosity", "words_per_sentence",
            "has_image", "has_video", "quote_of_video", "weekend", "day_position", "log_gap_h"]
BINARY = [f for f in FEATURES if f.startswith(("hook_has", "hook_is", "is_", "has_", "big_", "names_", "mentions_",
                                               "emo_", "quote_of", "weekend"))]
