# Audience Seeding

Finds the real niche audience (Tech / B2B / AI) around Thought Pilot's X clients, so engagement before posting reaches the people X will then show the client's posts to. Data comes from the xplatform scraper API.

Phase 1 is four steps. Each one is run on real data and reviewed before the next starts.

| Step | What it does | Status |
|---|---|---|
| 1A Segmentation | Labels accounts Tech / B2B / AI from bio and posts (model trained on hand labels) | Built: 90.5% in-niche accuracy, 81% main-or-second segment |
| 1B Seed map | 150 core accounts per niche, then the accounts they reply to, quote and retweet, then a scored seed map of up to 2,000 accounts. Includes a hold-out test against clients' real engagers. | In progress |
| 1C Content performance | Per-post rates, X-weighted score, niche share of repliers | Not started |
| 1D Model | Performance model with X's published ranking weights, backtested | Not started |

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync --extra embed            # the embed extra is only needed to (re)train 1A
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
