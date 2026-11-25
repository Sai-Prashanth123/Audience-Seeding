"""Media type per post from X's public embed endpoint (cdn.syndication.twimg.com, the one embedded tweets use).

Free, no login, no xplatform quota. xplatform stores only a media count, so this is how Videos are told
apart from images. Cached in data/winners/media_types.csv; only uncached posts are fetched.
"""

from __future__ import annotations

import time

import pandas as pd

from .data import DIR, MEDIA_CACHE

URL = "https://cdn.syndication.twimg.com/tweet-result"
COLS = ["tweet_id", "media_kind", "n_media", "video_s", "quoted_media_kind", "quoted_user", "article_preview",
        "fetched"]


def _kind(media: list[dict]) -> str:
    types = [m.get("type") for m in media or []]
    if "video" in types:
        return "video"
    if "animated_gif" in types:
        return "gif"
    if "photo" in types:
        return "photo"
    return "none"


def parse(tid: str, d: dict) -> dict:
    media = d.get("mediaDetails") or []
    vid = next((m for m in media if m.get("type") == "video"), None)
    dur = ((vid or {}).get("video_info") or {}).get("duration_millis")
    q = d.get("quoted_tweet") or {}
    art = d.get("article") or {}
    return {"tweet_id": tid, "media_kind": _kind(media), "n_media": len(media),
            "video_s": round(dur / 1000, 1) if dur else None,
            "quoted_media_kind": _kind(q.get("mediaDetails")) if q else None,
            "quoted_user": (q.get("user") or {}).get("screen_name") if q else None,
            "article_preview": art.get("preview_text"), "fetched": True}


def _one(tid: str) -> dict | None:
    from curl_cffi import requests
    for attempt in range(3):
        try:
            r = requests.get(URL, params={"id": tid, "token": "a", "lang": "en"}, impersonate="chrome", timeout=20)
            if r.status_code == 200:
                return parse(tid, r.json())
            if r.status_code == 404:
                return {"tweet_id": tid, "media_kind": "unavailable", "fetched": True}
            if r.status_code == 429:
                time.sleep(30 * (attempt + 1))
                continue
            return None
        except Exception:  # noqa: BLE001  - network blip: retry, then skip (stays uncached)
            time.sleep(3)
    return None


def fetch(tweet_ids: list[str], workers: int = 4, log_every: int = 200) -> pd.DataFrame:
    """Fetch uncached posts with a small thread pool (polite: 4 at a time); cache saved as it goes."""
    from concurrent.futures import ThreadPoolExecutor
    DIR.mkdir(parents=True, exist_ok=True)
    cache = pd.read_csv(MEDIA_CACHE, dtype={"tweet_id": str}) if MEDIA_CACHE.exists() else pd.DataFrame(columns=COLS)
    done = set(cache.tweet_id)
    todo = [t for t in dict.fromkeys(map(str, tweet_ids)) if t not in done]
    rows = []
    with ThreadPoolExecutor(workers) as ex:
        for i, r in enumerate(ex.map(_one, todo), 1):
            if r:
                rows.append(r)
            if i % log_every == 0 or i == len(todo):
                pd.concat([cache, pd.DataFrame(rows, columns=COLS)], ignore_index=True).to_csv(MEDIA_CACHE, index=False)
                print(f"{i}/{len(todo)} fetched", flush=True)
    return pd.read_csv(MEDIA_CACHE, dtype={"tweet_id": str}) if MEDIA_CACHE.exists() else cache
