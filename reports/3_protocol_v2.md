# Step 3 · Evaluation protocol v2 (pre-registered 16 Nov 2026, before any v2 result was seen)

v1 (`3_protocol.md`) stays in force. v2 adds client-focused metrics, because the tool is used for clients.

## Primary metrics (computed on the 15 clients' posts in the test windows)
| metric | meaning | bar |
|---|---|---|
| typical miss (×) on views and X score | exp(mean \|log error\|) | lower than the served v1 model |
| pairwise accuracy | for random pairs of one client's posts, how often the predictor orders them correctly | higher than the served v1 model |
| per-client 80% coverage | share of a client's posts inside the 80% range | **70–90% for every client with ≥20 test posts** |

All-account metrics (v1 tables) stay as secondary checks: a v2 item may not make them significantly worse.

## Keep / drop
An item (new range method, feature group, weighting, member) is kept only if, on client posts, for views **or**
X score:
1. its typical miss is lower with Diebold–Mariano p < 0.05 **and** an account-cluster bootstrap 95% range of the gain
   above 0, **or** its pairwise accuracy is higher with a bootstrap 95% range above 0; and
2. no primary metric gets significantly worse.

A range method is kept if it brings more clients inside 70–90% coverage without widening the median range of
clients that were already inside by more than 10%.

## Fixed
Same 4 frozen folds as the Colab export (`data/colab/folds.json`); same strict 48h rule for any final count used as a
feature. "Counts so far" features may only use counts that would have been visible when the post went out.
