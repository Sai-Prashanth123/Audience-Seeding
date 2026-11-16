# 1B hold-out test: are clients' real engagers in the seed map?

Seed map built **without any client-touching edge**. Engagers: last 60 days of replies + quotes from xplatform `x_engagements` (likes/retweets are not collectable).
Baseline: 3,000 random accounts from the 52,552-account corpus.

| client | segments | engagers | in seed map | random baseline | lift |
|---|---|---:|---:|---:|---:|
| itsalexvacca | b2b | 318 | 22.3% | 3.8% | 5.9x |
| MichLieben | b2b | 242 | 28.5% | 3.8% | 7.5x |
| nifinet | b2b | 203 | 7.9% | 3.8% | 2.1x |
| VukConfidential | b2b+ai | 50 | 32.0% | 7.3% | 4.4x |
| nikolak47 | tech+b2b | 394 | 26.4% | 6.6% | 4.0x |
| Vick_Mucunski | tech | 16 | 25.0% | 3.2% | 7.8x |
| itsivanfalco | b2b | 1 | 0.0% | 3.8% | 0.0x |
| Kenny_GTM | ai+b2b | 35 | 37.1% | 7.3% | 5.1x |
| mailankhong | ai | 9 | 22.2% | 3.6% | 6.2x |
| Tycho_luijten | b2b | 2 | 50.0% | 3.8% | 13.2x |
| thejcron | tech | 1 | 100.0% | 3.2% | 31.2x |
| kennyrueter | tech | 0 | 0.0% | 3.2% | 0.0x |
| pierreherubel | b2b | 96 | 13.5% | 3.8% | 3.6x |
| nateandorsky | ai+b2b | 5 | 0.0% | 7.3% | 0.0x |
| imrenat | tech | 2 | 50.0% | 3.2% | 15.6x |

In seed map = share of the client's distinct engagers who appear in the seed map of the client's segment(s). This is also the client's **baseline niche share** for later phases.
