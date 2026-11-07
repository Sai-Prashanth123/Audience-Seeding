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


class SaveError(RuntimeError):
    """A save that GitHub refused, with a plain-language reason (never contains the token)."""


def explain_http(code: int) -> str:
    return {
        401: "GitHub says the token is invalid, expired or revoked. Create a new one and update the "
             "app's GITHUB_TOKEN secret.",
        403: "The token can READ the repo but is not allowed to WRITE. On GitHub, edit the token: "
             "Repository permissions -> Contents -> 'Read and write' -> Update. No change needed in Streamlit.",
        404: "GitHub can't see the repo with this token. Give the token access to Sai-Prashanth123/Audience-Seeding.",
        409: "The file changed on GitHub at the same moment. Press Save again.",
        422: "The file changed on GitHub at the same moment. Press Save again.",
    }.get(code, f"GitHub refused the save (HTTP {code}). Try again in a minute.")


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
            raise SaveError(explain_http(e.code)) from None
    new_rows = new_rows.astype(str)
    merged = pd.concat([current[~current[key].isin(new_rows[key])], new_rows], ignore_index=True)
    body = {"message": message, "branch": "main",
            "content": base64.b64encode(merged.to_csv(index=False).encode("utf-8")).decode()}
    if sha:
        body["sha"] = sha
    try:
        _call("PUT", url, token, body)
    except urllib.error.HTTPError as e:
        raise SaveError(explain_http(e.code)) from None
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
        return False, explain_http(e.code)
    except Exception as e:
        return False, f"could not reach GitHub ({e.__class__.__name__})"
    # Write check that cannot change anything: an update with a deliberately wrong file fingerprint.
    # GitHub answers 409/422 when the token MAY write (the fingerprint is just wrong), 403 when it may not.
    probe = {"message": "write-permission probe (never applies)", "content": "cHJvYmU=", "branch": "main",
             "sha": "0" * 40}
    try:
        _call("PUT", f"https://api.github.com/repos/{repo}/contents/data/labels/1A_claude_grades.csv", tok, probe)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return False, explain_http(403)
        if e.code not in (409, 422):
            return False, explain_http(e.code)
    except Exception as e:
        return False, f"could not reach GitHub ({e.__class__.__name__})"
    return True, f"connected to {info.get('full_name', repo)} with write access: reviews save to the repo"
