"""Minimal xplatform API client.

Base URL and quirks come from xplatform's CLAUDE.md: production sits behind Cloudflare,
which 403s non-browser TLS fingerprints, so requests go through curl_cffi impersonating
Chrome. Auth is the `X-API-Key` header. Reads from stored data are free; jobs spend the
shared X-account pool, so callers should keep them small and deliberate.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterator

from curl_cffi import requests

BASE_URL = os.environ.get("XPLATFORM_BASE_URL", "https://scraping.thought-pilot.co/api")
ROOT = Path(__file__).resolve().parents[2]
RETRY_STATUS = {429, 500, 502, 503, 504}


def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


class XPlatform:
    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL):
        _load_env()
        self.key = api_key or os.environ.get("XPLATFORM_API_KEY")
        if not self.key:
            raise RuntimeError("XPLATFORM_API_KEY missing (put it in .env)")
        self.base = base_url.rstrip("/")
        self.s = requests.Session(impersonate="chrome")
        self.s.headers.update({"X-API-Key": self.key})

    def get(self, path: str, tries: int = 6, **params: Any) -> Any:
        """GET with retries: xplatform sits behind Cloudflare and returns 502/503/504 during short outages
        (seen 15 Nov 2026: one 502 killed a whole weekly run). Other errors (4xx) fail at once."""
        params = {k: v for k, v in params.items() if v is not None}
        for attempt in range(1, tries + 1):
            try:
                r = self.s.get(f"{self.base}{path}", params=params, timeout=120)
                if r.status_code in RETRY_STATUS and attempt < tries:
                    raise requests.exceptions.HTTPError(f"HTTP {r.status_code}")
                r.raise_for_status()
                return r.json()
            except requests.exceptions.RequestException as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if attempt == tries or (status is not None and status not in RETRY_STATUS):
                    raise
                print(f"GET {path} attempt {attempt} failed ({e.__class__.__name__}); retrying")
                time.sleep(min(20 * attempt, 120))

    # ---- stored data (free) -------------------------------------------------
    def export_tweets(self, **filters: Any) -> list[dict]:
        """Download /datasets/export as JSONL rows (no `raw`, includes reply_to/quoted ids).

        Fully read before returning, and retried: long streams through Cloudflare occasionally get
        reset mid-download ("HTTP/2 stream reset", seen from GitHub runners). HTTP/1.1 is used
        because it has proven steadier for these long responses.
        """
        from curl_cffi import CurlHttpVersion

        params = {"format": "jsonl", **{k: v for k, v in filters.items() if v is not None}}
        last: Exception | None = None
        for attempt in range(1, 7):
            try:
                r = self.s.get(f"{self.base}/datasets/export", params=params, timeout=600,
                               http_version=CurlHttpVersion.V1_1)
                r.raise_for_status()
                return [json.loads(line) for line in r.content.splitlines() if line.strip()]
            except requests.exceptions.RequestException as e:
                last = e
                print(f"export attempt {attempt} failed ({e.__class__.__name__}); retrying")
                time.sleep(min(30 * attempt, 180))
        raise RuntimeError(f"/datasets/export failed 6 times: {last}")

    def get_csv(self, path: str, **params: Any) -> str:
        params = {k: v for k, v in params.items() if v is not None}
        for attempt in range(1, 7):
            try:
                r = self.s.get(f"{self.base}{path}", params=params, timeout=600)
                r.raise_for_status()
                return r.text
            except requests.exceptions.RequestException as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if attempt == 6 or (status is not None and status not in RETRY_STATUS):
                    raise
                print(f"GET {path} attempt {attempt} failed ({e.__class__.__name__}); retrying")
                time.sleep(min(30 * attempt, 180))

    # ---- jobs (spend quota) -------------------------------------------------
    def submit(self, actor: str, input: dict) -> int:
        r = self.s.post(f"{self.base}/jobs", json={"actor": actor, "input": input}, timeout=60)
        if r.status_code == 503:  # job exists, queue was down: never resubmit (API.md §8)
            return int(r.json()["detail"].split()[1])
        r.raise_for_status()
        return int(r.json()["id"])

    def wait(self, job_id: int, poll: float = 10, timeout: float = 1800) -> dict:
        end = time.time() + timeout
        while True:
            try:
                job = self.get(f"/jobs/{job_id}")
            except requests.exceptions.RequestException as e:  # transient network drop while polling
                print(f"poll error ({e.__class__.__name__}); retrying")
                time.sleep(poll)
                continue
            if job["status"] in ("succeeded", "failed", "cancelled"):
                return job
            if time.time() > end:
                raise TimeoutError(f"job {job_id} still {job['status']}")
            time.sleep(poll)

    def job_rows(self, job_id: int, kind: str = "items", page: int = 500) -> Iterator[dict]:
        offset = 0
        while True:
            data = self.get(f"/jobs/{job_id}/{kind}", limit=page, offset=offset)
            items = data["items"] if isinstance(data, dict) else data
            yield from items
            if len(items) < page:
                return
            offset += page
