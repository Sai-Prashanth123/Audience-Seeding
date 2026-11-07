# 1D · Backtest

Trained on **23,777 posts** from 314 accounts posted before 2026-10-15; tested on **11,205 later posts** (each ≥48h old). Target: X-weighted score (replies ×5, quotes ×5, reposts ×1, likes ×0.66).

**Within-author Spearman** is the headline: for each account, does the predictor rank that account's posts in the right order? (0 = no better than random, 1 = perfect.) Baseline A is the account's rolling recent level; a negative score means posts right after a hot streak tend to do worse than the streak (regression to the mean). **Top-20% hit rate**: of the posts a predictor puts in an account's top fifth, the share that really were (random = 20%).

| predictor | within-author Spearman | top-20% hit rate | pooled Spearman | mean abs error (log) |
|---|---:|---:|---:|---:|
| A · account's usual level | -0.154 | 15% | 0.783 | 0.827 |
| B · usual level × X's published rules | -0.017 | 18% | 0.755 | 0.976 |
| Model | 0.189 | 27% | 0.800 | 0.805 |

**Gate: PASS**: the model beats both baselines on within-author ranking and error.

## Pilot clients (test period only)

| client | test posts | predictor | within-author Spearman | top-20% hit rate | MAE (log) |
|---|---:|---|---:|---:|---:|
| itsalexvacca | 39 | A · account's usual level | -0.037 | 25% | 0.743 |
| itsalexvacca | 39 | B · usual level × X's published rules | 0.130 | 12% | 0.765 |
| itsalexvacca | 39 | Model | 0.219 | 25% | 0.687 |
| kenny_gtm | 11 | A · account's usual level | -0.766 | 0% | 0.753 |
| kenny_gtm | 11 | B · usual level × X's published rules | 0.014 | 0% | 0.607 |
| kenny_gtm | 11 | Model | 0.055 | 50% | 0.606 |
| nikolak47 | 24 | A · account's usual level | -0.278 | 0% | 0.836 |
| nikolak47 | 24 | B · usual level × X's published rules | -0.037 | 0% | 0.856 |
| nikolak47 | 24 | Model | 0.303 | 40% | 0.765 |

Per-client numbers rest on few test posts; read them as direction, not proof.

## What the model leans on (gain)

- log_base: 40%
- log_base_views: 9%
- log_followers: 6%
- format: 3%
- n_chars: 3%
- txt9: 2%
- txt2: 2%
- txt0: 2%
- log_gap_h: 2%
- txt3: 2%
- txt5: 2%
- txt13: 2%
