# 1D · Backtest

Trained on **23,791 posts** from 326 accounts posted before 2026-10-15; tested on **13,652 later posts** (each ≥48h old). Target: X-weighted score (replies ×5, quotes ×5, reposts ×1, likes ×0.66).

**Within-author Spearman** is the headline: for each account, does the predictor rank that account's posts in the right order? (0 = no better than random, 1 = perfect.) Baseline A is the account's rolling recent level; a negative score means posts right after a hot streak tend to do worse than the streak (regression to the mean). **Top-20% hit rate**: of the posts a predictor puts in an account's top fifth, the share that really were (random = 20%).

| predictor | within-author Spearman | top-20% hit rate | pooled Spearman | mean abs error (log) |
|---|---:|---:|---:|---:|
| A · account's usual level | -0.143 | 15% | 0.778 | 0.841 |
| B · usual level × X's published rules | 0.009 | 18% | 0.752 | 0.982 |
| Model | 0.189 | 26% | 0.802 | 0.802 |

**Gate: PASS**: the model beats both baselines on within-author ranking and error.

## Pilot clients (test period only)

| client | test posts | predictor | within-author Spearman | top-20% hit rate | MAE (log) |
|---|---:|---|---:|---:|---:|
| itsalexvacca | 41 | A · account's usual level | 0.001 | 25% | 0.711 |
| itsalexvacca | 41 | B · usual level × X's published rules | 0.155 | 12% | 0.740 |
| itsalexvacca | 41 | Model | 0.281 | 38% | 0.665 |
| kenny_gtm | 13 | A · account's usual level | -0.765 | 0% | 0.926 |
| kenny_gtm | 13 | B · usual level × X's published rules | -0.311 | 0% | 0.836 |
| kenny_gtm | 13 | Model | -0.258 | 33% | 0.853 |
| mailankhong | 14 | A · account's usual level | 0.964 | 100% | 0.502 |
| mailankhong | 14 | B · usual level × X's published rules | 0.881 | 33% | 0.432 |
| mailankhong | 14 | Model | 0.845 | 67% | 0.386 |
| michlieben | 42 | A · account's usual level | -0.252 | 12% | 0.564 |
| michlieben | 42 | B · usual level × X's published rules | 0.243 | 25% | 0.589 |
| michlieben | 42 | Model | 0.291 | 50% | 0.493 |
| nateandorsky | 16 | A · account's usual level | 0.158 | 33% | 0.367 |
| nateandorsky | 16 | B · usual level × X's published rules | 0.158 | 33% | 0.367 |
| nateandorsky | 16 | Model | 0.115 | 33% | 0.491 |
| nifinet | 26 | A · account's usual level | 0.009 | 20% | 0.942 |
| nifinet | 26 | B · usual level × X's published rules | 0.087 | 40% | 0.955 |
| nifinet | 26 | Model | 0.396 | 60% | 0.795 |
| nikolak47 | 25 | A · account's usual level | -0.289 | 0% | 0.818 |
| nikolak47 | 25 | B · usual level × X's published rules | -0.029 | 0% | 0.836 |
| nikolak47 | 25 | Model | 0.116 | 20% | 0.805 |
| pierreherubel | 15 | A · account's usual level | -0.391 | 0% | 1.169 |
| pierreherubel | 15 | B · usual level × X's published rules | -0.231 | 0% | 1.168 |
| pierreherubel | 15 | Model | 0.416 | 33% | 1.074 |
| vick_mucunski | 12 | A · account's usual level | -0.502 | 0% | 0.650 |
| vick_mucunski | 12 | B · usual level × X's published rules | -0.502 | 0% | 0.650 |
| vick_mucunski | 12 | Model | 0.161 | 0% | 0.548 |
| vukconfidential | 11 | A · account's usual level | -0.377 | 0% | 0.799 |
| vukconfidential | 11 | B · usual level × X's published rules | -0.377 | 0% | 0.799 |
| vukconfidential | 11 | Model | -0.018 | 0% | 1.124 |

Per-client numbers rest on few test posts; read them as direction, not proof.

## What the model leans on (gain)

- log_base: 44%
- log_base_views: 8%
- format: 3%
- n_chars: 3%
- txt9: 3%
- txt2: 2%
- log_gap_h: 2%
- txt5: 2%
- txt1: 2%
- txt0: 2%
- txt13: 2%
- txt10: 2%
