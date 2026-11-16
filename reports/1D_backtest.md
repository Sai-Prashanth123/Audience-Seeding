# 1D · Backtest

Trained on **23,740 posts** from 341 accounts posted before 2026-10-15; tested on **27,470 later posts** (each ≥48h old). Target: X-weighted score (replies ×5, quotes ×5, reposts ×1, likes ×0.66).

**Within-author Spearman** is the headline: for each account, does the predictor rank that account's posts in the right order? (0 = no better than random, 1 = perfect.) Baseline A is the account's rolling recent level; a negative score means posts right after a hot streak tend to do worse than the streak (regression to the mean). **Top-20% hit rate**: of the posts a predictor puts in an account's top fifth, the share that really were (random = 20%).

| predictor | within-author Spearman | top-20% hit rate | pooled Spearman | mean abs error (log) |
|---|---:|---:|---:|---:|
| A · account's usual level | -0.096 | 17% | 0.789 | 0.841 |
| B · usual level × X's published rules | 0.029 | 22% | 0.760 | 0.999 |
| Model | 0.202 | 28% | 0.812 | 0.804 |

**Gate: PASS**: the model beats both baselines on within-author ranking and error.

## Pilot clients (test period only)

| client | test posts | predictor | within-author Spearman | top-20% hit rate | MAE (log) |
|---|---:|---|---:|---:|---:|
| itsalexvacca | 56 | A · account's usual level | 0.119 | 18% | 0.687 |
| itsalexvacca | 56 | B · usual level × X's published rules | 0.320 | 18% | 0.702 |
| itsalexvacca | 56 | Model | 0.407 | 27% | 0.626 |
| kenny_gtm | 24 | A · account's usual level | -0.490 | 20% | 0.850 |
| kenny_gtm | 24 | B · usual level × X's published rules | -0.036 | 0% | 0.839 |
| kenny_gtm | 24 | Model | 0.143 | 20% | 0.745 |
| mailankhong | 14 | A · account's usual level | 0.964 | 100% | 0.502 |
| mailankhong | 14 | B · usual level × X's published rules | 0.881 | 33% | 0.432 |
| mailankhong | 14 | Model | 0.783 | 33% | 0.383 |
| michlieben | 58 | A · account's usual level | -0.211 | 17% | 0.578 |
| michlieben | 58 | B · usual level × X's published rules | 0.225 | 25% | 0.603 |
| michlieben | 58 | Model | 0.213 | 42% | 0.573 |
| nateandorsky | 17 | A · account's usual level | 0.190 | 33% | 0.345 |
| nateandorsky | 17 | B · usual level × X's published rules | 0.190 | 33% | 0.345 |
| nateandorsky | 17 | Model | -0.012 | 33% | 0.485 |
| nifinet | 28 | A · account's usual level | -0.057 | 17% | 0.960 |
| nifinet | 28 | B · usual level × X's published rules | -0.017 | 33% | 0.971 |
| nifinet | 28 | Model | 0.382 | 50% | 0.780 |
| nikolak47 | 38 | A · account's usual level | -0.348 | 12% | 0.666 |
| nikolak47 | 38 | B · usual level × X's published rules | 0.004 | 25% | 0.765 |
| nikolak47 | 38 | Model | 0.081 | 25% | 0.659 |
| pierreherubel | 25 | A · account's usual level | 0.068 | 20% | 0.987 |
| pierreherubel | 25 | B · usual level × X's published rules | 0.095 | 20% | 1.004 |
| pierreherubel | 25 | Model | 0.313 | 40% | 0.889 |
| vick_mucunski | 12 | A · account's usual level | -0.502 | 0% | 0.650 |
| vick_mucunski | 12 | B · usual level × X's published rules | -0.502 | 0% | 0.650 |
| vick_mucunski | 12 | Model | -0.102 | 0% | 0.641 |
| vukconfidential | 13 | A · account's usual level | -0.354 | 0% | 0.667 |
| vukconfidential | 13 | B · usual level × X's published rules | -0.354 | 0% | 0.667 |
| vukconfidential | 13 | Model | -0.286 | 33% | 1.038 |

Per-client numbers rest on few test posts; read them as direction, not proof.

## What the model leans on (gain)

- log_base: 45%
- log_base_views: 8%
- format: 3%
- n_chars: 3%
- txt9: 3%
- txt2: 2%
- txt0: 2%
- txt11: 2%
- log_gap_h: 2%
- txt5: 2%
- txt1: 2%
- txt6: 2%
