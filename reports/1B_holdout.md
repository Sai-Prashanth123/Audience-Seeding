# 1B hold-out test: are clients' real engagers in the seed map?

Seed map built **without any client-touching edge**. Engagers: last 60 days of replies + quotes from xplatform `x_engagements` (likes/retweets are not collectable).
Baseline: 3,000 random accounts from the 43,028-account corpus.

| client | segments | engagers | in seed map | random baseline | lift |
|---|---|---:|---:|---:|---:|
| itsalexvacca | b2b | 281 | 19.2% | 4.6% | 4.1x |
| MichLieben | b2b | 219 | 24.2% | 4.6% | 5.2x |
| nifinet | b2b | 208 | 7.2% | 4.6% | 1.6x |
| VukConfidential | b2b+ai | 27 | 40.7% | 9.0% | 4.5x |
| nikolak47 | tech+b2b | 343 | 22.2% | 7.8% | 2.9x |
| Vick_Mucunski | tech | 17 | 11.8% | 3.9% | 3.0x |
| itsivanfalco | b2b | 2 | 50.0% | 4.6% | 10.8x |
| Kenny_GTM | ai+b2b | 24 | 29.2% | 9.0% | 3.2x |
| mailankhong | ai | 6 | 33.3% | 4.7% | 7.0x |
| Tycho_luijten | b2b | 5 | 20.0% | 4.6% | 4.3x |
| thejcron | tech | 0 | 0.0% | 3.9% | 0.0x |
| kennyrueter | tech | 0 | 0.0% | 3.9% | 0.0x |
| pierreherubel | b2b | 65 | 4.6% | 4.6% | 1.0x |
| nateandorsky | ai+b2b | 3 | 0.0% | 9.0% | 0.0x |
| imrenat | tech | 1 | 100.0% | 3.9% | 25.4x |

In seed map = share of the client's distinct engagers who appear in the seed map of the client's segment(s). This is also the client's **baseline niche share** for later phases.
