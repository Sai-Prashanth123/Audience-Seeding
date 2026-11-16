# 1D · Backtest

Trained on **23,739 posts** from 341 accounts posted before 2026-10-15; tested on **27,956 later posts** (each ≥48h old). Target: X-weighted score (replies ×5, quotes ×5, reposts ×1, likes ×0.708).

**Within-author Spearman** is the headline: for each account, does the predictor rank that account's posts in the right order? (0 = no better than random, 1 = perfect.) Baseline A is the account's rolling recent level; a negative score means posts right after a hot streak tend to do worse than the streak (regression to the mean). **Top-20% hit rate**: of the posts a predictor puts in an account's top fifth, the share that really were (random = 20%).

| predictor | within-author Spearman | top-20% hit rate | pooled Spearman | mean abs error (log) |
|---|---:|---:|---:|---:|
| A · account's usual level | -0.093 | 17% | 0.791 | 0.842 |
| B · usual level × X's published rules | 0.035 | 21% | 0.769 | 0.973 |
| Model | 0.205 | 28% | 0.814 | 0.806 |

**Gate: PASS**: the model beats both baselines on within-author ranking and error.

## Pilot clients (test period only)

| client | test posts | predictor | within-author Spearman | top-20% hit rate | MAE (log) |
|---|---:|---|---:|---:|---:|
| itsalexvacca | 56 | A · account's usual level | 0.113 | 18% | 0.686 |
| itsalexvacca | 56 | B · usual level × X's published rules | 0.316 | 18% | 0.697 |
| itsalexvacca | 56 | Model | 0.438 | 27% | 0.634 |
| kenny_gtm | 24 | A · account's usual level | -0.475 | 20% | 0.848 |
| kenny_gtm | 24 | B · usual level × X's published rules | -0.033 | 0% | 0.839 |
| kenny_gtm | 24 | Model | 0.282 | 0% | 0.749 |
| mailankhong | 14 | A · account's usual level | 0.964 | 100% | 0.516 |
| mailankhong | 14 | B · usual level × X's published rules | 0.881 | 33% | 0.442 |
| mailankhong | 14 | Model | 0.812 | 67% | 0.413 |
| michlieben | 58 | A · account's usual level | -0.215 | 17% | 0.572 |
| michlieben | 58 | B · usual level × X's published rules | 0.227 | 25% | 0.595 |
| michlieben | 58 | Model | 0.208 | 50% | 0.578 |
| nateandorsky | 17 | A · account's usual level | 0.190 | 33% | 0.352 |
| nateandorsky | 17 | B · usual level × X's published rules | 0.190 | 33% | 0.352 |
| nateandorsky | 17 | Model | 0.015 | 33% | 0.511 |
| nifinet | 28 | A · account's usual level | -0.051 | 33% | 0.961 |
| nifinet | 28 | B · usual level × X's published rules | -0.012 | 33% | 0.973 |
| nifinet | 28 | Model | 0.376 | 50% | 0.764 |
| nikolak47 | 38 | A · account's usual level | -0.312 | 12% | 0.667 |
| nikolak47 | 38 | B · usual level × X's published rules | 0.006 | 25% | 0.758 |
| nikolak47 | 38 | Model | 0.273 | 38% | 0.625 |
| pierreherubel | 25 | A · account's usual level | 0.063 | 20% | 0.987 |
| pierreherubel | 25 | B · usual level × X's published rules | 0.093 | 20% | 1.005 |
| pierreherubel | 25 | Model | 0.245 | 20% | 0.904 |
| vick_mucunski | 12 | A · account's usual level | -0.502 | 0% | 0.639 |
| vick_mucunski | 12 | B · usual level × X's published rules | -0.502 | 0% | 0.639 |
| vick_mucunski | 12 | Model | -0.116 | 0% | 0.598 |
| vukconfidential | 13 | A · account's usual level | -0.354 | 0% | 0.660 |
| vukconfidential | 13 | B · usual level × X's published rules | -0.354 | 0% | 0.660 |
| vukconfidential | 13 | Model | -0.253 | 33% | 0.989 |

Per-client numbers rest on few test posts; read them as direction, not proof.

## What the model leans on (gain)

- log_base: 44%
- log_base_views: 8%
- format: 3%
- n_chars: 3%
- txt9: 3%
- txt2: 2%
- log_gap_h: 2%
- txt11: 2%
- txt0: 2%
- txt3: 2%
- txt5: 2%
- txt13: 2%
