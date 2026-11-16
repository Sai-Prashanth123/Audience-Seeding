# 1B hold-out test: are clients' real engagers in the seed map?

Seed map built **without any client-touching edge**. Engagers: last 60 days of replies + quotes from xplatform `x_engagements` (likes/retweets are not collectable).
Baseline: 3,000 random accounts from the 51,353-account corpus.

| client | segments | engagers | in seed map | random baseline | lift |
|---|---|---:|---:|---:|---:|
| itsalexvacca | b2b | 318 | 23.0% | 3.8% | 6.0x |
| MichLieben | b2b | 242 | 27.7% | 3.8% | 7.2x |
| nifinet | b2b | 203 | 7.9% | 3.8% | 2.1x |
| VukConfidential | b2b+ai | 50 | 30.0% | 7.1% | 4.2x |
| nikolak47 | tech+b2b | 394 | 25.9% | 6.9% | 3.8x |
| Vick_Mucunski | tech | 16 | 25.0% | 3.6% | 6.9x |
| itsivanfalco | b2b | 1 | 0.0% | 3.8% | 0.0x |
| Kenny_GTM | ai+b2b | 35 | 37.1% | 7.1% | 5.3x |
| mailankhong | ai | 9 | 33.3% | 3.6% | 9.3x |
| Tycho_luijten | b2b | 2 | 50.0% | 3.8% | 13.0x |
| thejcron | tech | 1 | 100.0% | 3.6% | 27.8x |
| kennyrueter | tech | 0 | 0.0% | 3.6% | 0.0x |
| pierreherubel | b2b | 96 | 15.6% | 3.8% | 4.1x |
| nateandorsky | ai+b2b | 5 | 0.0% | 7.1% | 0.0x |
| imrenat | tech | 2 | 50.0% | 3.6% | 13.9x |

In seed map = share of the client's distinct engagers who appear in the seed map of the client's segment(s). This is also the client's **baseline niche share** for later phases.
