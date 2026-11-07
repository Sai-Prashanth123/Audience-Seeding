# Audience Seeding

Finds the real niche audience (Tech / B2B / AI) around Thought Pilot's X clients, so engagement before posting reaches the people X will then show the client's posts to. Data comes from the xplatform scraper API.

Phase 1 is four steps. Each one is run on real data and reviewed before the next starts.

| Step | What it does | Status |
|---|---|---|
| 1A Segmentation | Labels accounts Tech / B2B / AI from bio and posts (model trained on hand labels) | Built: 90.5% in-niche accuracy, 81% main-or-second segment |
| 1B Seed map | 150 core accounts per niche, then the accounts they reply to, quote and retweet, then a scored seed map of 2,000 accounts per niche. Includes a hold-out test against clients' real engagers. | Built: clients' real engagers found 2.3-3.2× more often than random |
| 1C Content performance | Per-post X-weighted score vs the account's own baseline, by format, hook, topic, timing; niche share of repliers | Built: totals match xplatform within 0-3.4% |
| 1D Model | LightGBM on post features + X's published rules; time-split backtest vs two baselines; live forward test | Built: within-author Spearman 0.19 vs -0.02 for the best baseline; live test running |

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync --extra embed --extra model   # embed: 1A/1C/1D text features; model: 1D
echo XPLATFORM_API_KEY=... > .env
```

## Pipeline

```bash
uv run seeding pull-corpus       # export stored tweets (free read)
uv run seeding pull-profiles     # export stored profiles with bios (free read)
uv run seeding edges             # who replies to, quotes and retweets whom
uv run seeding segments          # 1A: train, measure, label accounts, write review sample
uv run seeding core              # 1B: pick core accounts per niche
uv run seeding collect-core      # 1B: scrape core timelines (SPENDS X QUOTA)
uv run seeding seeds             # 1B: seed maps + hold-out test
uv run seeding content           # 1C: what worked per pilot client
uv run seeding backtest          # 1D: backtest vs baselines, then train the final model
uv run seeding predict --client itsalexvacca --text "..." [--when 2026-11-08T14:00]
uv run seeding live              # 1D: score new pilot posts early (run every few hours), check after 48h
uv run seeding export-dashboard  # small results snapshot for the deployed app
uv run pytest
```

## Dashboard

```bash
uv run streamlit run app/dashboard.py
```

The dashboard reads `data/seeding.duckdb`, which is not in git. Set `SEEDING_DB` to point it at another file.

## Layout

- `config/segments.yaml`: segments, exclusions, client to segment map, seed weights
- `src/seeding/`: pipeline code. `xp.py` is the API client; `segments.py` is 1A; `seedmap.py` and `holdout.py` are 1B
- `data/labels/`: hand labels used to train and measure 1A
- `reports/`: outputs reviewed at each gate
