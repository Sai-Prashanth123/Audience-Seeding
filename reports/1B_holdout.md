# 1B hold-out test: are clients' real engagers in the seed map?

Seed map built **without any client-touching edge**. Engagers: last 60 days of replies + quotes from xplatform `x_engagements` (likes/retweets are not collectable).
Baseline: 3,000 random accounts from the 38,204-account corpus.

| client | segments | engagers | in seed map | random baseline | lift |
|---|---|---:|---:|---:|---:|
| itsalexvacca | b2b | 284 | 17.3% | 5.2% | 3.3x |
| Kenny_GTM | ai+b2b | 31 | 22.6% | 9.3% | 2.4x |
| nikolak47 | tech+b2b | 395 | 23.3% | 8.8% | 2.6x |

In seed map = share of the client's distinct engagers who appear in the seed map of the client's segment(s). This is also the client's **baseline niche share** for later phases.
