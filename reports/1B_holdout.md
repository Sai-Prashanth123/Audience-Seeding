# 1B hold-out test: are clients' real engagers in the seed map?

Seed map built **without any client-touching edge**. Engagers: last 60 days of replies + quotes from xplatform `x_engagements` (likes/retweets are not collectable).
Baseline: 3,000 random accounts from the 38,204-account corpus.

| client | segments | engagers | in seed map | random baseline | lift |
|---|---|---:|---:|---:|---:|
| itsalexvacca | b2b | 267 | 17.6% | 5.5% | 3.2x |
| Kenny_GTM | ai+b2b | 13 | 23.1% | 10.0% | 2.3x |
| nikolak47 | tech+b2b | 182 | 24.7% | 9.2% | 2.7x |

In seed map = share of the client's distinct engagers who appear in the seed map of the client's segment(s). This is also the client's **baseline niche share** for later phases.
