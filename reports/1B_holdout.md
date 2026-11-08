# 1B hold-out test: are clients' real engagers in the seed map?

Seed map built **without any client-touching edge**. Engagers: last 60 days of replies + quotes from xplatform `x_engagements` (likes/retweets are not collectable).
Baseline: 3,000 random accounts from the 44,152-account corpus.

| client | segments | engagers | in seed map | random baseline | lift |
|---|---|---:|---:|---:|---:|
| itsalexvacca | b2b | 281 | 18.5% | 4.2% | 4.4x |
| MichLieben | b2b | 232 | 24.1% | 4.2% | 5.7x |
| nifinet | b2b | 208 | 7.2% | 4.2% | 1.7x |
| VukConfidential | b2b+ai | 49 | 30.6% | 8.3% | 3.7x |
| nikolak47 | tech+b2b | 349 | 22.6% | 7.5% | 3.0x |
| Vick_Mucunski | tech | 21 | 14.3% | 4.4% | 3.2x |
| itsivanfalco | b2b | 5 | 20.0% | 4.2% | 4.8x |
| Kenny_GTM | ai+b2b | 31 | 29.0% | 8.3% | 3.5x |
| mailankhong | ai | 11 | 9.1% | 4.4% | 2.1x |
| Tycho_luijten | b2b | 5 | 20.0% | 4.2% | 4.8x |
| thejcron | tech | 4 | 25.0% | 4.4% | 5.7x |
| kennyrueter | tech | 0 | 0.0% | 4.4% | 0.0x |
| pierreherubel | b2b | 77 | 5.2% | 4.2% | 1.2x |
| nateandorsky | ai+b2b | 5 | 0.0% | 8.3% | 0.0x |
| imrenat | tech | 2 | 50.0% | 4.4% | 11.4x |

In seed map = share of the client's distinct engagers who appear in the seed map of the client's segment(s). This is also the client's **baseline niche share** for later phases.
