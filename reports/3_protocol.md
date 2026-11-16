# Step 3 · Evaluation protocol (pre-registered 16 Nov 2026, before any Step 3 model was trained)

These rules are fixed **before** results are seen, so no model can be picked because it happened to look good.

## What is predicted
For each original client-style post (no replies, no retweets), the final count (≥48h old) of each X action:
**views, likes, replies, reposts, quotes, bookmarks**, as `log1p(count)`. The **X score** is derived from them using
the weights in `xai-org/x-algorithm` `home-mixer/params/param.rs` (cited in `src/seeding/xalgo.py`).

## Data and folds
- **Posts:** all original posts from accounts with ≥15 posts in the last 365 days (the 1D training set).
- **Rolling-origin folds:** the last 4 back-to-back 14-day test windows.
  - Each fold trains on posts made **more than 2 days before** its 14-day calibration window, so every training result had matured.
  - Ranges are calibrated on the calibration window, then the model is tested on the next 14 days.
- **Feature rule:** features may use only what was knowable when the post went out. An author's baseline uses only their posts **at least 48h older** than the post being predicted. (1D used the previous 20 posts, even ones still growing, which slightly favours it.)

## Metrics (per action, pooled over folds, and per client)
| metric | meaning |
|---|---|
| within-author Spearman | ranks one account's posts correctly (accounts with ≥5 test posts) |
| typical miss (×) | exp(mean \|log error\|); 1.0 = perfect |
| 80% coverage | share of posts inside the 80% range; **must be 75–85%** |
| range width (×) | median top ÷ bottom of the 80% range |
| CRPS | quality of the whole predicted spread (quantiles 0.1/0.5/0.9) |

## Baselines every model must beat
- **A:** the account's usual level for that action (median of its previous 20 matured posts).
- **B:** A × X's same-day author-diversity decay.
- **C (1D):** the current single LightGBM on the X score, retrained on the same folds.

## Keep / drop rule for every ensemble member and feature group
A member or feature group is **kept** only if, on **views and X score**:
1. its typical miss is lower, with **Diebold–Mariano p < 0.05** and an **author-cluster bootstrap 95% range of the gain above 0**, and
2. its within-author Spearman is not lower.

Ranges ship only if pooled 80% coverage is within **75–85%** on the test windows.

## Ceiling
The best possible typical miss is estimated from same-author near-duplicate posts (cosine ≥ 0.92, within 90 days),
following Martin et al. 2016. Results are reported as **"how close to the ceiling"**.

## Live
Every live prediction is appended to `data/ledger/predictions.csv` **before** the post's result exists, and is judged
at ≥48h. Live coverage and typical miss are reported per client, next to the backtest numbers.
