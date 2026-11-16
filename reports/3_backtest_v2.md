# Step 3 · Backtest v2 (protocol: reports/3_protocol_v2.md)

Same 4 frozen windows and the same 27,609 test posts as v1. Primary scope: the 509 test posts by our clients.

**What v2 adds:** each account's own track record by kind of post (format, opening line, length, link, media, quote), from posts matured 48h+ and shrunk toward 0 when there is little history; how many niche hubs and fellow clients usually reply; and training that counts client posts 5x and in-niche posts 2x.

## views

| model | scope | typical miss | picks the better of 2 | inside 80% range | vs v1: miss gain (95%) | vs v1: pairwise gain (95%) |
|---|---|---:|---:|---:|---|---|
| Usual level (baseline) | clients | 2.65× | 53% | 73% | -0.151..+0.048 | -0.154..-0.051 |
| v1 served model | clients | 2.51× | 64% | 71% |  |  |
| v1 + per-account bias correction | clients | 2.48× | 64% | 74% | -0.026..+0.065 | -0.014..+0.005 |
| v2: + own-history + hub support | clients | 2.45× | 64% | 72% | -0.007..+0.072 | -0.014..+0.008 |
| **v2w: v2 + clients weighted 5x (served)** | clients | 2.42× | 64% | 69% | +0.010..+0.086 | -0.013..+0.007 |
| Usual level (baseline) | all | 2.37× | 52% | 77% | -0.036..-0.015 | -0.052..-0.037 |
| v1 served model | all | 2.31× | 57% | 76% |  |  |
| v1 + per-account bias correction | all | 2.32× | 56% | 77% | -0.012..-0.002 | -0.006..-0.002 |
| v2: + own-history + hub support | all | 2.26× | 57% | 76% | +0.014..+0.023 | -0.001..+0.005 |
| **v2w: v2 + clients weighted 5x (served)** | all | 2.26× | 57% | 76% | +0.014..+0.024 | -0.001..+0.005 |

## xscore

| model | scope | typical miss | picks the better of 2 | inside 80% range | vs v1: miss gain (95%) | vs v1: pairwise gain (95%) |
|---|---|---:|---:|---:|---|---|
| Usual level (baseline) | clients | 2.09× | 50% | 83% | -0.102..-0.009 | -0.138..-0.085 |
| 1D (old model) | clients | 1.96× | 61% | 83% | -0.009..+0.035 | -0.012..+0.006 |
| v1 served model | clients | 1.99× | 62% | 84% |  |  |
| v1 + per-account bias correction | clients | 2.00× | 61% | 82% | -0.019..+0.008 | -0.020..-0.001 |
| v2: + own-history + hub support | clients | 1.98× | 61% | 83% | -0.011..+0.025 | -0.021..+0.006 |
| **v2w: v2 + clients weighted 5x (served)** | clients | 1.96× | 62% | 78% | -0.027..+0.043 | -0.021..+0.012 |
| Usual level (baseline) | all | 2.43× | 51% | 78% | -0.083..-0.061 | -0.090..-0.075 |
| 1D (old model) | all | 2.20× | 60% | 80% | +0.017..+0.035 | +0.004..+0.012 |
| v1 served model | all | 2.26× | 59% | 79% |  |  |
| v1 + per-account bias correction | all | 2.27× | 59% | 78% | -0.006..+0.001 | -0.006..-0.002 |
| v2: + own-history + hub support | all | 2.25× | 59% | 79% | -0.001..+0.007 | -0.006..+0.000 |
| **v2w: v2 + clients weighted 5x (served)** | all | 2.26× | 59% | 79% | -0.005..+0.004 | -0.004..+0.001 |

## likes

| model | scope | typical miss | picks the better of 2 | inside 80% range | vs v1: miss gain (95%) | vs v1: pairwise gain (95%) |
|---|---|---:|---:|---:|---|---|
| Usual level (baseline) | clients | 1.98× | 48% | 84% | -0.074..+0.017 | -0.160..-0.059 |
| v1 served model | clients | 1.92× | 59% | 84% |  |  |
| v1 + per-account bias correction | clients | 1.95× | 57% | 84% | -0.024..+0.005 | -0.033..+0.000 |
| v2: + own-history + hub support | clients | 1.94× | 57% | 84% | -0.025..+0.010 | -0.032..-0.003 |
| **v2w: v2 + clients weighted 5x (served)** | clients | 1.94× | 57% | 79% | -0.041..+0.012 | -0.042..+0.009 |
| Usual level (baseline) | all | 2.44× | 51% | 78% | -0.064..-0.044 | -0.073..-0.058 |
| v1 served model | all | 2.32× | 57% | 78% |  |  |
| v1 + per-account bias correction | all | 2.32× | 57% | 78% | -0.007..+0.000 | -0.006..-0.002 |
| v2: + own-history + hub support | all | 2.31× | 57% | 78% | -0.001..+0.007 | -0.002..+0.004 |
| **v2w: v2 + clients weighted 5x (served)** | all | 2.31× | 57% | 78% | -0.003..+0.005 | -0.006..-0.000 |

## replies

| model | scope | typical miss | picks the better of 2 | inside 80% range | vs v1: miss gain (95%) | vs v1: pairwise gain (95%) |
|---|---|---:|---:|---:|---|---|
| Usual level (baseline) | clients | 1.90× | 51% | 83% | -0.108..-0.008 | -0.158..-0.093 |
| v1 served model | clients | 1.78× | 65% | 81% |  |  |
| v1 + per-account bias correction | clients | 1.79× | 64% | 80% | -0.020..+0.009 | -0.008..+0.006 |
| v2: + own-history + hub support | clients | 1.78× | 64% | 81% | -0.011..+0.008 | -0.022..+0.013 |
| **v2w: v2 + clients weighted 5x (served)** | clients | 1.80× | 64% | 77% | -0.018..-0.003 | -0.022..+0.015 |
| Usual level (baseline) | all | 2.12× | 50% | 79% | -0.070..-0.050 | -0.113..-0.096 |
| v1 served model | all | 2.00× | 61% | 79% |  |  |
| v1 + per-account bias correction | all | 2.00× | 61% | 79% | -0.002..+0.004 | -0.006..-0.003 |
| v2: + own-history + hub support | all | 2.00× | 61% | 79% | -0.001..+0.005 | -0.006..+0.001 |
| **v2w: v2 + clients weighted 5x (served)** | all | 2.00× | 61% | 80% | -0.005..+0.003 | -0.007..-0.001 |

## Decision (pre-registered rule)

- **v2w is served.** On clients' views it is significantly better than v1 (typical miss 2.51× → 2.42×; Diebold-Mariano p = 0.002; account-cluster 95% gain +0.010…+0.086), its 80% ranges are narrower (views ~9× wide instead of ~13×), and no primary metric got significantly worse.
- X score, likes and replies: no significant change.
- Range methods (group / scaled conformal) did not bring clearly more clients inside 70–90% coverage (30/40 vs 29–30/40 client×action pairs), so the plain method stays; **volatile clients get wider ranges from their own live record instead** (adaptive conformal per client after 10 judged posts).
- Still open: views ranges for Nicolas, Mai, Vuk, Pierre and Vick hold only 55–70%. Their results swing more than the model can see before posting; the after-posting nowcast is the fix for them.

