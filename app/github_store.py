"""Save label reviews from the deployed app straight into the GitHub repo (contents API).

The deployed Streamlit app's disk is temporary, so reviews would be lost. With a fine-grained token
in Streamlit secrets (GITHUB_TOKEN; this repo only, Contents: read and write), a review is merged
into the CSV in the repo; the next weekly GitHub run trains on it and reports team-checked accuracy.
Standard library only (the deployed app has a minimal requirements file).
"""

from __future__ import annotations

import base64
import io
import json
import urllib.request

import pandas as pd

DEFAULT_REPO = "Sai-Prashanth123/Audience-Seeding"


def _token_and_repo():
    try:
        import streamlit as st
        tok = st.secrets.get("GITHUB_TOKEN")
        repo = st.secrets.get("GITHUB_REPO", DEFAULT_REPO)
    except Exception:
        return None, DEFAULT_REPO
    return tok, repo


def available() -> bool:
    return bool(_token_and_repo()[0])


def _call(method: str, url: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "audience-seeding-app"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def merge_csv(path: str, new_rows: pd.DataFrame, key: str, message: str) -> int:
    """Replace rows with the same `key` in the repo CSV at `path` (create it if missing). Returns rows saved."""
    token, repo = _token_and_repo()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set in Streamlit secrets")
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    sha, current = None, pd.DataFrame(columns=new_rows.columns)
    try:
        got = _call("GET", url + "?ref=main", token)
        sha = got["sha"]
        current = pd.read_csv(io.StringIO(base64.b64decode(got["content"]).decode("utf-8")), dtype=str)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    new_rows = new_rows.astype(str)
    merged = pd.concat([current[~current[key].isin(new_rows[key])], new_rows], ignore_index=True)
    body = {"message": message, "branch": "main",
            "content": base64.b64encode(merged.to_csv(index=False).encode("utf-8")).decode()}
    if sha:
        body["sha"] = sha
    _call("PUT", url, token, body)
    return len(new_rows)


def status() -> tuple[bool, str]:
    """Why saving to GitHub is on or off, in plain words. Never reveals the token."""
    try:
        import streamlit as st
        try:
            keys = list(st.secrets.keys())
        except Exception:
            return False, "this app has no secrets set (Streamlit → Settings → Secrets is empty or not loaded yet)"
        if "GITHUB_TOKEN" not in keys:
            found = ", ".join(keys) if keys else "none"
            return False, f"the secret GITHUB_TOKEN is not set (secrets found: {found}). Check the spelling."
        tok = str(st.secrets["GITHUB_TOKEN"]).strip()
    except Exception as e:  # pragma: no cover
        return False, f"could not read secrets: {e.__class__.__name__}"
    if not tok.startswith(("github_pat_", "ghp_")):
        return False, "GITHUB_TOKEN is set but doesn't look like a GitHub token (should start with github_pat_)"
    _, repo = _token_and_repo()
    try:
        info = _call("GET", f"https://api.github.com/repos/{repo}", tok)
    except urllib.error.HTTPError as e:
        return False, f"GitHub refused the token (HTTP {e.code}): it may be expired, revoked or not given this repo"
    except Exception as e:
        return False, f"could not reach GitHub ({e.__class__.__name__})"
    return True, f"connected to {info.get('full_name', repo)}: reviews save to the repo"
