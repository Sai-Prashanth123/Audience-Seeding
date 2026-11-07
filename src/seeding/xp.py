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

    def get(self, path: str, **params: Any) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        r = self.s.get(f"{self.base}{path}", params=params, timeout=120)
        r.raise_for_status()
        return r.json()

    # ---- stored data (free) -------------------------------------------------
    def export_tweets(self, **filters: Any) -> Iterator[dict]:
        """Stream /datasets/export as JSONL rows (no `raw`, includes reply_to/quoted ids)."""
        params = {"format": "jsonl", **{k: v for k, v in filters.items() if v is not None}}
        r = self.s.get(f"{self.base}/datasets/export", params=params, timeout=600, stream=True)
        r.raise_for_status()
        buf = b""
        for chunk in r.iter_content():
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for line in lines:
                if line.strip():
                    yield json.loads(line)
        if buf.strip():
            yield json.loads(buf)

    def get_csv(self, path: str, **params: Any) -> str:
        params = {k: v for k, v in params.items() if v is not None}
        r = self.s.get(f"{self.base}{path}", params=params, timeout=600)
        r.raise_for_status()
        return r.text

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
            job = self.get(f"/jobs/{job_id}")
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
