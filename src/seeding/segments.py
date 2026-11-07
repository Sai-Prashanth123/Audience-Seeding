"""Step 1A: label accounts Tech / B2B / AI from what they post.

Bios come back null from xplatform today, so the signal is the account's own posts.
Each post is embedded once (cached in DuckDB); an account's vector is the mean of its
posts. Segment prototypes are the mean of (a) the segment description and keyword
phrases and (b) the posts of client accounts assigned to that segment in
config/segments.yaml. Scores are cosine similarities, centred against the corpus
average so 'generic founder chatter' does not score high everywhere.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MAX_POSTS_PER_ACCOUNT = 40
MIN_CHARS = 25


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config" / "segments.yaml").read_text(encoding="utf-8"))


def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL, device="cpu")


def _clean_sql() -> str:
    # strip leading @mentions, RT prefix and links so the text is the account's own words
    return r"""trim(regexp_replace(regexp_replace(regexp_replace(text,
              '^(RT @[A-Za-z0-9_]+: )', ''), '^(\s*@[A-Za-z0-9_]+)+', ''), 'https?://\S+', '', 'g'))"""


def embed_posts(con: duckdb.DuckDBPyConnection, batch: int = 256) -> int:
    """Embed up to MAX_POSTS_PER_ACCOUNT recent own-words posts per account (retweets excluded)."""
    con.execute("CREATE TABLE IF NOT EXISTS post_vecs (tweet_id VARCHAR PRIMARY KEY, username VARCHAR, vec FLOAT[384])")
    todo = con.execute(f"""
        WITH c AS (
          SELECT tweet_id, lower(username) AS username, {_clean_sql()} AS clean,
                 row_number() OVER (PARTITION BY lower(username) ORDER BY created_at DESC) AS rn
          FROM tweets WHERE NOT coalesce(is_retweet, false))
        SELECT tweet_id, username, clean FROM c
        WHERE rn <= {MAX_POSTS_PER_ACCOUNT} AND length(clean) >= {MIN_CHARS}
          AND tweet_id NOT IN (SELECT tweet_id FROM post_vecs)
    """).df()
    if todo.empty:
        return 0
    model = _model()
    for i in range(0, len(todo), batch * 20):
        part = todo.iloc[i:i + batch * 20]
        vecs = model.encode(part["clean"].str.slice(0, 1000).tolist(), batch_size=batch,
                            normalize_embeddings=True, show_progress_bar=False)
        df = pd.DataFrame({"tweet_id": part["tweet_id"], "username": part["username"],
                           "vec": list(vecs.astype(np.float32))})
        con.execute("INSERT OR IGNORE INTO post_vecs SELECT * FROM df")
        print(f"embedded {min(i + batch * 20, len(todo))}/{len(todo)}")
    return len(todo)


def embed_bios(con: duckdb.DuckDBPyConnection, batch: int = 256) -> int:
    """Embed every stored bio not yet embedded (bios arrived 2026-11-07)."""
    con.execute("CREATE TABLE IF NOT EXISTS bio_vecs (handle VARCHAR PRIMARY KEY, vec FLOAT[384])")
    todo = con.execute("""
        SELECT handle, regexp_replace(description, 'https?://\\S+', '', 'g') AS bio FROM profiles
        WHERE description IS NOT NULL AND length(trim(description)) >= 3
          AND handle NOT IN (SELECT handle FROM bio_vecs)""").df()
    if todo.empty:
        return 0
    model = _model()
    vecs = model.encode(todo["bio"].str.slice(0, 500).tolist(), batch_size=batch,
                        normalize_embeddings=True, show_progress_bar=False)
    df = pd.DataFrame({"handle": todo["handle"], "vec": list(vecs.astype(np.float32))})
    con.execute("INSERT OR IGNORE INTO bio_vecs SELECT * FROM df")
    return len(todo)


def account_features(con: duckdb.DuckDBPyConnection):
    """[post-mean vector | bio vector | has_posts | has_bio] for every account with either.

    Missing halves are zeros plus a flag, so one model handles bio-only accounts (one-off
    repliers we never had enough posts for) and post-only accounts (bio missing).
    """
    names_p, Xp, counts = account_vectors(con)
    bios = con.execute("SELECT handle, vec FROM bio_vecs").df()
    bio_map = dict(zip(bios.handle, bios.vec))
    post_map = {n: (Xp[i], counts[i]) for i, n in enumerate(names_p)}
    names = sorted(set(post_map) | set(bio_map))
    dim = Xp.shape[1]
    F = np.zeros((len(names), 2 * dim + 2), dtype=np.float32)
    n_posts = np.zeros(len(names), dtype=int)
    for i, n in enumerate(names):
        if n in post_map:
            F[i, :dim] = post_map[n][0]
            F[i, 2 * dim] = 1.0
            n_posts[i] = post_map[n][1]
        if n in bio_map:
            F[i, dim:2 * dim] = bio_map[n]
            F[i, 2 * dim + 1] = 1.0
    return names, F, n_posts


def account_vectors(con: duckdb.DuckDBPyConnection) -> tuple[list[str], np.ndarray, np.ndarray]:
    df = con.execute("SELECT username, vec FROM post_vecs").df()
    g = df.groupby("username")["vec"]
    names = list(g.groups.keys())
    mats = [np.vstack(v.values).mean(axis=0) for _, v in g]
    counts = g.size().reindex(names).to_numpy()
    X = np.vstack(mats)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    return names, X, counts


def prototypes(cfg: dict, names: list[str], X: np.ndarray) -> dict[str, np.ndarray]:
    model = _model()
    idx = {n: i for i, n in enumerate(names)}
    protos = {}
    for key, seg in cfg["segments"].items():
        phrases = [seg["description"]] + [f"Posts about {k}" for k in seg["search_keywords"]]
        text_vec = model.encode(phrases, normalize_embeddings=True).mean(axis=0)
        anchors = [idx[h.lower()] for h, segs in cfg["client_segments"].items()
                   if segs and segs[0] == key and h.lower() in idx]
        parts = [text_vec] + ([X[anchors].mean(axis=0)] if anchors else [])
        v = np.mean(parts, axis=0)
        protos[key] = v / np.linalg.norm(v)
    return protos


def _exclusion_vectors(cfg: dict):
    ex = cfg.get("exclude") or {}
    if not ex:
        return None
    model = _model()
    keys = list(ex)
    V = model.encode([ex[k] for k in keys], normalize_embeddings=True)
    return keys, V


def classify(con: duckdb.DuckDBPyConnection, min_margin: float = 0.03) -> pd.DataFrame:
    cfg = load_config()
    names, X, counts = account_vectors(con)
    protos = prototypes(cfg, names, X)
    keys = list(protos)
    P = np.vstack([protos[k] for k in keys])
    centred = X - X.mean(axis=0)
    S = centred @ P.T
    out = pd.DataFrame(S, columns=[f"score_{k}" for k in keys])
    out.insert(0, "username", names)
    out["n_posts"] = counts
    order = np.argsort(-S, axis=1)
    best, second = S[np.arange(len(S)), order[:, 0]], S[np.arange(len(S)), order[:, 1]]
    out["segment"] = [keys[i] for i in order[:, 0]]
    out["margin"] = best - second
    floor = float(np.median(best))
    out["confidence"] = np.clip((best - floor) / (best.max() - floor), 0, 1)

    # Off-topic check: closer to an exclusion prototype than to the best segment -> none.
    excl = _exclusion_vectors(cfg)
    if excl is not None:
        E = centred @ excl[1].T
        ex_best = E.max(axis=1)
        margin = cfg.get("offtopic_margin", 0.0)
        out["offtopic"] = np.where(ex_best > best + margin,
                                   [excl[0][i] for i in E.argmax(axis=1)], "")
    else:
        out["offtopic"] = ""

    none = ((out["confidence"] < cfg.get("min_confidence", 0.3))
            | (out["n_posts"] < cfg.get("min_posts", 3))
            | (out["offtopic"] != ""))
    out.loc[none, "segment"] = "none"
    out.loc[none, "confidence"] = 0.0
    out["ambiguous"] = (out["segment"] != "none") & (out["margin"] < min_margin)
    con.execute("CREATE OR REPLACE TABLE account_segments AS SELECT * FROM out")
    return out


LABELS = ROOT / "data" / "labels" / "1A_claude_grades.csv"


def _training_set(cfg: dict, names: list[str], X: np.ndarray):
    """Hand labels plus the configured clients (primary segment) as extra examples."""
    idx = {n: i for i, n in enumerate(names)}
    lab = pd.read_csv(LABELS)[["username", "expected"]]
    clients = pd.DataFrame([(h.lower(), s[0]) for h, s in cfg["client_segments"].items() if s],
                           columns=["username", "expected"])
    lab = pd.concat([lab, clients]).drop_duplicates("username", keep="first")
    lab = lab[lab.username.isin(idx)]
    return lab, X[[idx[u] for u in lab.username]], lab.expected.to_numpy()


def _assign(proba: np.ndarray, classes: list[str], second_ratio: float = 0.5,
            second_min: float = 0.15) -> tuple[list[str], list[str]]:
    """Main segment = argmax (may be 'none'); second = next-best segment when it is at
    least `second_ratio` of the main one's probability and above `second_min`."""
    seg_idx = [i for i, c in enumerate(classes) if c != "none"]
    main, also = [], []
    for row in proba:
        top = int(row.argmax())
        if classes[top] == "none":
            main.append("none"); also.append(""); continue
        main.append(classes[top])
        rest = sorted((i for i in seg_idx if i != top), key=lambda i: -row[i])
        j = rest[0] if rest else None
        ok = j is not None and row[j] >= second_min and row[j] >= second_ratio * row[top]
        also.append(classes[j] if ok else "")
    return main, also


def classify_supervised(con: duckdb.DuckDBPyConnection, folds: int = 5) -> tuple[pd.DataFrame, dict]:
    """Logistic regression on [posts | bio] features, trained on hand labels.

    Every account gets a main segment and, for multi-niche accounts, a second one.
    The cross-validated metrics are the honest accuracy: each labelled account is scored
    by a model that never saw its label.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    cfg = load_config()
    names, F, n_posts = account_features(con)
    dim = (F.shape[1] - 2) // 2
    has_bio = F[:, 2 * dim + 1] > 0
    eligible = has_bio | (n_posts >= cfg.get("min_posts", 3))
    lab, Fl, y = _training_set(cfg, names, F)

    clf = LogisticRegression(C=2.0, max_iter=3000, class_weight="balanced")
    cv = StratifiedKFold(folds, shuffle=True, random_state=0)
    P_cv = cross_val_predict(clf, Fl, y, cv=cv, method="predict_proba")
    classes = sorted(set(y))
    main_cv, also_cv = _assign(P_cv, classes)
    main_cv, also_cv = np.array(main_cv), np.array(also_cv)
    inn, pin = (y != "none"), (main_cv != "none")
    both = inn & pin
    metrics = {
        "n_labels": int(len(y)),
        "in_niche_accuracy": float((inn == pin).mean()),
        "in_niche_precision": float(both.sum() / max(pin.sum(), 1)),
        "in_niche_recall": float(both.sum() / max(inn.sum(), 1)),
        "segment_exact": float((main_cv == y)[both].mean()),
        "segment_main_or_second": float(((main_cv == y) | (also_cv == y))[both].mean()),
        "share_with_second": float((also_cv != "")[pin].mean()),
    }

    clf.fit(Fl, y)
    P = clf.predict_proba(F)
    main, also = _assign(P, list(clf.classes_))
    out = pd.DataFrame(P, columns=[f"p_{c}" for c in clf.classes_])
    out.insert(0, "username", names)
    out["n_posts"] = n_posts
    out["has_bio"] = has_bio
    out["segment"] = main
    out["also"] = also
    out["confidence"] = P.max(axis=1)
    out.loc[~eligible, ["segment", "also"]] = ["none", ""]
    con.execute("CREATE OR REPLACE TABLE account_segments AS SELECT * FROM out")
    cv_table = lab.assign(predicted=main_cv, also=also_cv)
    return out, {"metrics": metrics, "cv": cv_table}


def review_sample(con: duckdb.DuckDBPyConnection, per_segment: int = 50, seed: int = 7) -> Path:
    """reports/1A_segment_sample.csv: random unseen accounts per segment, with bio and 3 top posts."""
    seg = con.execute("SELECT * FROM account_segments WHERE segment <> 'none'").df()
    done = set(pd.read_csv(LABELS).username) if LABELS.exists() else set()
    seg = seg[~seg.username.isin(done)]  # only accounts the model was not trained on
    picks = pd.concat([d.sample(min(per_segment, len(d)), random_state=seed)
                       for _, d in seg.groupby("segment")])
    ex = con.execute(f"""
        WITH c AS (SELECT lower(username) u, {_clean_sql()} clean,
                   row_number() OVER (PARTITION BY lower(username) ORDER BY like_count DESC NULLS LAST) rn
                   FROM tweets WHERE NOT coalesce(is_retweet,false))
        SELECT u, string_agg(left(replace(clean, chr(10), ' '), 160), '  ||  ') ex
        FROM c WHERE rn <= 3 AND length(clean) >= {MIN_CHARS} GROUP BY u""").df()
    bios = con.execute("SELECT handle u, replace(description, chr(10), ' ') bio, followers_count FROM profiles").df()
    picks = (picks.merge(bios, left_on="username", right_on="u", how="left").drop(columns="u")
                  .merge(ex, left_on="username", right_on="u", how="left").drop(columns="u"))
    picks["confidence"] = picks["confidence"].round(2)
    picks["url"] = "https://x.com/" + picks["username"]
    picks["correct (y/n)"] = ""
    path = ROOT / "reports" / "1A_segment_sample.csv"
    path.parent.mkdir(exist_ok=True)
    cols = ["segment", "also", "username", "url", "confidence", "followers_count", "bio", "ex", "correct (y/n)"]
    picks[cols].rename(columns={"ex": "example_posts"}).to_csv(path, index=False, encoding="utf-8-sig")
    return path
