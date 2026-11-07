# 1D · Backtest

Trained on **23,776 posts** from 314 accounts posted before 2026-10-15; tested on **11,345 later posts** (each ≥48h old). Target: X-weighted score (replies ×5, quotes ×5, reposts ×1, likes ×0.66).

**Within-author Spearman** is the headline: for each account, does the predictor rank that account's posts in the right order? (0 = no better than random, 1 = perfect.) Baseline A is the account's rolling recent level; a negative score means posts right after a hot streak tend to do worse than the streak (regression to the mean). **Top-20% hit rate**: of the posts a predictor puts in an account's top fifth, the share that really were (random = 20%).

| predictor | within-author Spearman | top-20% hit rate | pooled Spearman | mean abs error (log) |
|---|---:|---:|---:|---:|
| A · account's usual level | -0.157 | 15% | 0.784 | 0.828 |
| B · usual level × X's published rules | -0.018 | 18% | 0.756 | 0.975 |
| Model | 0.175 | 27% | 0.805 | 0.796 |

**Gate: PASS**: the model beats both baselines on within-author ranking and error.

## Pilot clients (test period only)

| client | test posts | predictor | within-author Spearman | top-20% hit rate | MAE (log) |
|---|---:|---|---:|---:|---:|
| itsalexvacca | 39 | A · account's usual level | -0.037 | 25% | 0.743 |
| itsalexvacca | 39 | B · usual level × X's published rules | 0.130 | 12% | 0.765 |
| itsalexvacca | 39 | Model | 0.221 | 25% | 0.674 |
| kenny_gtm | 11 | A · account's usual level | -0.766 | 0% | 0.753 |
| kenny_gtm | 11 | B · usual level × X's published rules | 0.014 | 0% | 0.607 |
| kenny_gtm | 11 | Model | -0.282 | 50% | 0.636 |
| nikolak47 | 24 | A · account's usual level | -0.278 | 0% | 0.836 |
| nikolak47 | 24 | B · usual level × X's published rules | -0.037 | 0% | 0.856 |
| nikolak47 | 24 | Model | 0.205 | 20% | 0.809 |

Per-client numbers rest on few test posts; read them as direction, not proof.

## What the model leans on (gain)

- log_base: 45%
- log_base_views: 8%
- format: 3%
- n_chars: 3%
- txt9: 2%
- txt2: 2%
- txt10: 2%
- txt1: 2%
- txt5: 2%
- log_gap_h: 2%
- txt4: 2%
- txt6: 2%
