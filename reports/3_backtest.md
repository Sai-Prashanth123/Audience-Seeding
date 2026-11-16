# Step 3 · Forecaster backtest

Rolling-origin test (protocol: `reports/3_protocol.md`): 4 back-to-back 14-day test windows, **27,609 test posts from 834 accounts**. Every model trained only on posts matured before its window and had its 80% ranges calibrated on the 14 days in between.

**How to read:** *typical miss* 2.0× = usually off by a factor of 2 (1.0× would be perfect). *Ranking* = within-account Spearman (does it order one account's posts correctly; 0 = random). *In range* = share of posts inside the 80% range (should be ~80%).

## views

| predictor | typical miss | ranking | in 80% range | range width | CRPS | vs usual level |
|---|---:|---:|---:|---:|---:|---|
| L1 + 1D's baselines (diagnostic, not deployable) | 2.20× | 0.123 | 78% | 11.8× | 0.525 | better (p=0, gain +0.057…+0.087) |
| CatBoost per action | 2.31× | 0.109 | 76% | 12.4× | 0.555 | better (p=0, gain +0.014…+0.037) |
| LightGBM per action | 2.31× | 0.105 | 77% | 12.4× | 0.554 | better (p=0, gain +0.015…+0.036) |
| Stack of the members | 2.31× | 0.109 | 76% | 11.8× | 0.554 | better (p=0, gain +0.013…+0.033) |
| LightGBM + per-account shrinkage | 2.32× | 0.096 | 77% | 13.2× | 0.558 | better (p=1.58e-13, gain +0.007…+0.030) |
| A · the account's usual level | 2.37× | -0.012 | 78% | 17.0× | 0.592 |  |
| NGBoost (distribution) | 2.41× | 0.108 | 77% | 11.7× | 0.569 | worse (p=7.12e-12, gain -0.032…-0.003) |
| B · usual × X's same-day rule | 2.55× | 0.042 | 80% | 19.9× | 0.622 | worse (p=0, gain -0.092…-0.060) |

## likes

| predictor | typical miss | ranking | in 80% range | range width | CRPS | vs usual level |
|---|---:|---:|---:|---:|---:|---|
| LightGBM per action | 2.32× | 0.148 | 78% | 13.1× | 0.551 | better (p=0, gain +0.044…+0.064) |
| LightGBM + per-account shrinkage | 2.32× | 0.139 | 78% | 13.3× | 0.552 | better (p=0, gain +0.039…+0.061) |
| A · the account's usual level | 2.44× | -0.038 | 78% | 17.0× | 0.595 |  |
| B · usual × X's same-day rule | 2.56× | 0.041 | 79% | 20.1× | 0.614 | worse (p=0, gain -0.058…-0.033) |

## replies

| predictor | typical miss | ranking | in 80% range | range width | CRPS | vs usual level |
|---|---:|---:|---:|---:|---:|---|
| LightGBM + per-account shrinkage | 2.00× | 0.220 | 79% | 8.6× | 0.447 | better (p=0, gain +0.051…+0.072) |
| LightGBM per action | 2.00× | 0.228 | 79% | 8.7× | 0.447 | better (p=0, gain +0.050…+0.070) |
| A · the account's usual level | 2.12× | -0.047 | 78% | 11.0× | 0.497 |  |
| B · usual × X's same-day rule | 2.26× | 0.042 | 79% | 13.2× | 0.526 | worse (p=0, gain -0.075…-0.051) |

## reposts

| predictor | typical miss | ranking | in 80% range | range width | CRPS | vs usual level |
|---|---:|---:|---:|---:|---:|---|
| LightGBM per action | 2.08× | 0.134 | 81% | 9.1× | 0.475 | better (p=0, gain +0.032…+0.051) |
| LightGBM + per-account shrinkage | 2.10× | 0.128 | 81% | 10.3× | 0.479 | better (p=0, gain +0.026…+0.045) |
| A · the account's usual level | 2.17× | -0.038 | 80% | 17.4× | 0.535 |  |
| B · usual × X's same-day rule | 2.42× | 0.016 | 81% | 21.1× | 0.581 | worse (p=0, gain -0.121…-0.091) |

## quotes

| predictor | typical miss | ranking | in 80% range | range width | CRPS | vs usual level |
|---|---:|---:|---:|---:|---:|---|
| LightGBM per action | 1.70× | 0.132 | 81% | 3.7× | 0.344 | better (p=0, gain +0.033…+0.050) |
| LightGBM + per-account shrinkage | 1.72× | 0.126 | 84% | 5.4× | 0.355 | better (p=0, gain +0.020…+0.039) |
| A · the account's usual level | 1.78× | -0.049 | 80% | 9.4× | 0.419 |  |
| B · usual × X's same-day rule | 2.11× | 0.011 | 80% | 14.6× | 0.491 | worse (p=0, gain -0.193…-0.151) |

## bookmarks

| predictor | typical miss | ranking | in 80% range | range width | CRPS | vs usual level |
|---|---:|---:|---:|---:|---:|---|
| LightGBM per action | 2.82× | 0.246 | 79% | 26.1× | 0.665 | better (p=0, gain +0.107…+0.144) |
| LightGBM + per-account shrinkage | 2.83× | 0.238 | 79% | 26.8× | 0.667 | better (p=0, gain +0.102…+0.138) |
| A · the account's usual level | 3.19× | -0.048 | 79% | 40.8× | 0.771 |  |
| B · usual × X's same-day rule | 3.34× | 0.012 | 80% | 50.1× | 0.787 | worse (p=0, gain -0.058…-0.030) |

## xscore

| predictor | typical miss | ranking | in 80% range | range width | CRPS | vs usual level |
|---|---:|---:|---:|---:|---:|---|
| C · 1D (current model) | 2.20× | 0.206 | 80% | 12.7× | 0.518 | better (p=0, gain +0.082…+0.112) |
| L1 + 1D's baselines (diagnostic, not deployable) | 2.20× | 0.191 | 79% | 11.9× | 0.518 | better (p=0, gain +0.083…+0.111) |
| LightGBM per action | 2.26× | 0.193 | 78% | 12.1× | 0.535 | better (p=0, gain +0.061…+0.083) |
| Stack of the members | 2.26× | 0.191 | 78% | 11.9× | 0.533 | better (p=0, gain +0.061…+0.082) |
| LightGBM + per-account shrinkage | 2.27× | 0.187 | 78% | 12.6× | 0.537 | better (p=0, gain +0.058…+0.081) |
| CatBoost per action | 2.28× | 0.190 | 78% | 12.7× | 0.537 | better (p=0, gain +0.054…+0.078) |
| 1D with strict 48h baselines (diagnostic) | 2.30× | 0.192 | 78% | 13.5× | 0.549 | better (p=0, gain +0.046…+0.066) |
| NGBoost (distribution) | 2.30× | 0.185 | 78% | 11.3× | 0.543 | better (p=0, gain +0.044…+0.065) |
| A · the account's usual level | 2.43× | -0.048 | 78% | 15.5× | 0.590 |  |
| B · usual × X's same-day rule | 2.53× | 0.042 | 79% | 17.7× | 0.606 | worse (p=0, gain -0.054…-0.029) |

## Against 1D (the current model)

| candidate | target | typical miss | 1D | significant? |
|---|---|---:|---:|---|
| A · the account's usual level | xscore | 2.43× | 2.20× | worse (p=0) |
| B · usual × X's same-day rule | xscore | 2.53× | 2.20× | worse (p=0) |
| 1D with strict 48h baselines (diagnostic) | xscore | 2.30× | 2.20× | worse (p=0) |
| CatBoost per action | xscore | 2.28× | 2.20× | worse (p=0) |
| LightGBM per action | xscore | 2.26× | 2.20× | worse (p=0) |
| LightGBM + per-account shrinkage | xscore | 2.27× | 2.20× | worse (p=0) |
| NGBoost (distribution) | xscore | 2.30× | 2.20× | worse (p=0) |
| L1 + 1D's baselines (diagnostic, not deployable) | xscore | 2.20× | 2.20× | no clear difference (p=0.66) |
| Stack of the members | xscore | 2.26× | 2.20× | worse (p=0) |

## Keep / drop (pre-registered rule)

| candidate | beats usual level (views, X score) | beats 1D (X score) |
|---|---|---|
| LightGBM per action | True, True | False |
| CatBoost per action | True, True | False |
| NGBoost (distribution) | False, True | False |
| LightGBM + per-account shrinkage | True, True | False |
| Stack of the members | True, True | False |

**Served now:** LightGBM per action.

## How close to the ceiling

- **views:** 800 same-author near-duplicate post pairs differ by a typical 2.22×, so even a perfect content model would miss by about **1.76×**. Best model here: 2.31×.
- **xscore:** 800 same-author near-duplicate post pairs differ by a typical 2.57×, so even a perfect content model would miss by about **1.95×**. Best model here: 2.26×.

*A post's reach also depends on things no model sees before posting (who is online, whether a big account reposts it). That is why the after-posting nowcast exists.*

## Finding: 1D's backtest score used information not available at posting time

1D's usual level is the median of the author's previous 20 posts **at their final counts**, including posts only hours
old whose numbers were still growing when the next post went out. Tested directly (same folds, same posts):

| model (X score) | typical miss | ranking |
|---|---:|---:|
| 1D as built | 2.20x | 0.206 |
| 1D with the strict rule (only posts matured 48h+) | 2.30x | 0.192 |
| Step 3 LightGBM, strict rule | **2.26x** | **0.193** |
| Step 3 LightGBM + 1D's non-strict usual level (diagnostic) | 2.20x | 0.191 |

- Most of 1D's edge comes from that look-ahead: given the same information, the Step 3 model ties 1D (p = 0.66).
- Under the honest rule, Step 3 is **significantly better than 1D** (Diebold-Mariano p < 0.001; typical-miss gain
  +0.009 to +0.021 in log units, 95% account-cluster range), and it forecasts every action with calibrated ranges.
- So 1D's published backtest was somewhat optimistic. Its live test (judged ~21 Nov) is the fair measure. Under the
  pre-registered rule Step 3 does not *replace* 1D's live test; it runs beside it, frozen in the same ledger.
- Next improvement: use recent posts' counts **so far** at forecast time (the new hourly snapshots make this
  possible for training from now on), which is the honest version of the signal 1D was using.
