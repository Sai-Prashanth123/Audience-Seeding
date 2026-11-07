"""1B gate: do the seed maps contain the people who actually engage with our clients?

The seed map is rebuilt with every client-touching edge removed (seed_map_holdout), then
compared with each pilot client's real repliers/quoters from xplatform's x_engagements.
Baseline: the same share for a random sample of corpus accounts. The ratio is the lift.
"""

from __future__ import annotations

import io
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from .seedmap import ROOT, build_seed_map, load_config
from .xp import XPlatform


def fetch_engagements(xp: XPlatform, client: str, days: int = 60) -> pd.DataFrame:
    since = (date.today() - timedelta(days=days)).isoformat()
    text = xp.get_csv("/datasets/engagements", client=client, since=since, limit=100_000)
    df = pd.read_csv(io.StringIO(text), dtype=str)
    df["engager"] = df.engager_username.str.lower()
    return df


def run(con: duckdb.DuckDBPyConnection, days: int = 60, seed: int = 0, sample: int = 3000) -> Path:
    cfg = load_config()
    seeds = build_seed_map(con, exclude_clients=True)
    clients_lc = {h.lower() for h in cfg["client_segments"]}
    authors = con.execute("SELECT DISTINCT lower(username) u FROM tweets").df().u
    rand = authors[~authors.isin(clients_lc)].sample(min(sample, len(authors)), random_state=seed)
    xp = XPlatform()
    lines = ["# 1B hold-out test: are clients' real engagers in the seed map?", "",
             f"Seed map built **without any client-touching edge**. Engagers: last {days} days of "
             "replies + quotes from xplatform `x_engagements` (likes/retweets are not collectable).",
             f"Baseline: {len(rand):,} random accounts from the {len(authors):,}-account corpus.", "",
             "| client | segments | engagers | in seed map | random baseline | lift |",
             "|---|---|---:|---:|---:|---:|"]
    rows = []
    for client in cfg["pilot_clients"]:
        segs = cfg["client_segments"][client]
        smap = set(seeds[seeds.seg.isin(segs)].username)
        eng = fetch_engagements(xp, client, days)
        people = set(eng.engager) - clients_lc
        hit = len(people & smap) / max(len(people), 1)
        base = rand.isin(smap).mean()
        lift = hit / base if base else float("nan")
        rows.append(dict(client=client, segments="+".join(segs), engagers=len(people),
                         in_seed_map=hit, baseline=base, lift=lift))
        lines.append(f"| {client} | {'+'.join(segs)} | {len(people):,} | {hit:.1%} | {base:.1%} | {lift:.1f}x |")
    pd.DataFrame(rows).to_csv(ROOT / "reports" / "1B_holdout.csv", index=False)
    lines += ["", "In seed map = share of the client's distinct engagers who appear in the seed map of the "
              "client's segment(s). This is also the client's **baseline niche share** for later phases."]
    path = ROOT / "reports" / "1B_holdout.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
