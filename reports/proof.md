# Phase 1 proof · 16 Nov 2026 13:30 UTC

## Trust checks

- ✅ **Our data matches xplatform post by post (same posts; likes/views within 5%)**: 2026-10, UTC days: itsalexvacca 101 posts, MichLieben 93 posts, nifinet 123 posts, VukConfidential 58 posts, nikolak47 165 posts, Vick_Mucunski 48 posts, itsivanfalco 18 posts, Kenny_GTM 21 posts, mailankhong 150 posts, Tycho_luijten 11 posts, thejcron 3 posts, pierreherubel 22 posts, nateandorsky 35 posts, imrenat 1 posts
- ✅ **No client data leaks into what we measure**: hold-out map has no clients; 1C and tracking read the hold-out map
- ⚠️ **Data is fresh (posts < 36h, daily steps < 36h, weekly < 8 days)**: newest post 0h old; engage 6h ago; content 1h ago; segments 2h ago; seeds 2h ago; backtest 1h ago; live 0h ago; memory 1h ago; forecast-train: no run recorded yet
- ⚠️ **Every claim rests on enough data (weak ones are flagged, not hidden)**: 1A  In-niche vs off-topic accuracy, vs the team's labels (n=1); 1A  Right niche (main or 2nd), vs the team's labels (n=1); 1A  AI reviewer agrees with the team (random audits + disagreements) (n=1); 1B Tycho_luijten Seed map finds real engagers vs random accounts (lift) (n=2); 1B Vick_Mucunski Seed map finds real engagers vs random accounts (lift) (n=16); 1B imrenat Seed map finds real engagers vs random accounts (lift) (n=2); 1B itsivanfalco Seed map finds real engagers vs random accounts (lift) (n=1); 1B mailankhong Seed map finds real engagers vs random accounts (lift) (n=9); 1B nateandorsky Seed map finds real engagers vs random accounts (lift) (n=5); 1B thejcron Seed map finds real engagers vs random accounts (lift) (n=1)
- ✅ **1D test uses only posts after the split date**: earliest test post 15 Oct 2026 (split 2026-10-15)
- ⚠️ **AI reviewer stays in line with the team (>= 80% agreement)**: only 1 accounts reviewed by both so far; need 30 to judge
- ✅ **Long-term memory is built and stable**: 15 weeks in memory (27 habit, 5 fading, 4 new, 6 forgotten, 12 emerging); no client's situation changed
- ✅ **Forecasts are honest (80% ranges hold; frozen before results)**: backtest views 77% inside the 80% range; backtest xscore 78% inside the 80% range; 6 live posts forecast before their results

## Claims with 95% ranges

| step | client | claim | value | 95% range | n | status |
|---|---|---|---:|---|---:|---|
| 1A |  | In-niche vs off-topic accuracy, vs Claude's hand labels | 90% | 87% – 93% | 353 | proven |
| 1A |  | Right niche (main or 2nd), vs Claude's hand labels | 84% | 77% – 89% | 154 | not yet proven above 80% |
| 1A |  | In-niche vs off-topic accuracy, vs the team's labels | 100% | 21% – 100% | 1 | weak (few labels) |
| 1A |  | Right niche (main or 2nd), vs the team's labels | 100% | 21% – 100% | 1 | weak (few labels) |
| 1A |  | In-niche vs off-topic accuracy, vs the AI reviewer's labels | 95% | 93% – 97% | 396 | proven |
| 1A |  | Right niche (main or 2nd), vs the AI reviewer's labels | 95% | 90% – 98% | 137 | proven |
| 1A |  | AI reviewer agrees with the team (random audits + disagreements) | 100% | 21% – 100% | 1 | weak (few audits) |
| 2A |  | Engage-list posts the AI reviewer judges worth replying to | 55% | 52% – 59% | 965 | measured |
| 1B | Kenny_GTM | Seed map finds real engagers vs random accounts (lift) | 5.26x | 3.05x – 7.75x | 35 | proven |
| 1B | Kenny_GTM | Share of real engagers in the seed map (baseline niche share) | 37% | 23% – 54% | 35 | measured |
| 1B | MichLieben | Seed map finds real engagers vs random accounts (lift) | 7.22x | 5.64x – 9.33x | 242 | proven |
| 1B | MichLieben | Share of real engagers in the seed map (baseline niche share) | 28% | 22% – 34% | 242 | measured |
| 1B | Tycho_luijten | Seed map finds real engagers vs random accounts (lift) | 13.04x | 0.00x – 29.42x | 2 | weak (few engagers) |
| 1B | Tycho_luijten | Share of real engagers in the seed map (baseline niche share) | 50% | 9% – 91% | 2 | measured |
| 1B | Vick_Mucunski | Seed map finds real engagers vs random accounts (lift) | 6.94x | 1.59x – 14.29x | 16 | weak (few engagers) |
| 1B | Vick_Mucunski | Share of real engagers in the seed map (baseline niche share) | 25% | 10% – 49% | 16 | measured |
| 1B | VukConfidential | Seed map finds real engagers vs random accounts (lift) | 4.25x | 2.43x – 6.15x | 50 | proven |
| 1B | VukConfidential | Share of real engagers in the seed map (baseline niche share) | 30% | 19% – 44% | 50 | measured |
| 1B | imrenat | Seed map finds real engagers vs random accounts (lift) | 13.89x | 0.00x – 31.59x | 2 | weak (few engagers) |
| 1B | imrenat | Share of real engagers in the seed map (baseline niche share) | 50% | 9% – 91% | 2 | measured |
| 1B | itsalexvacca | Seed map finds real engagers vs random accounts (lift) | 5.99x | 4.52x – 7.79x | 318 | proven |
| 1B | itsalexvacca | Share of real engagers in the seed map (baseline niche share) | 23% | 19% – 28% | 318 | measured |
| 1B | itsivanfalco | Seed map finds real engagers vs random accounts (lift) | 0.00x | 0.00x – 0.00x | 1 | weak (few engagers) |
| 1B | itsivanfalco | Share of real engagers in the seed map (baseline niche share) | 0% | 0% – 79% | 1 | measured |
| 1B | mailankhong | Seed map finds real engagers vs random accounts (lift) | 9.35x | 0.00x – 18.87x | 9 | weak (few engagers) |
| 1B | mailankhong | Share of real engagers in the seed map (baseline niche share) | 33% | 12% – 65% | 9 | measured |
| 1B | nateandorsky | Seed map finds real engagers vs random accounts (lift) | 0.00x | 0.00x – 0.00x | 5 | weak (few engagers) |
| 1B | nateandorsky | Share of real engagers in the seed map (baseline niche share) | 0% | 0% – 43% | 5 | measured |
| 1B | nifinet | Seed map finds real engagers vs random accounts (lift) | 2.06x | 1.13x – 3.14x | 203 | proven |
| 1B | nifinet | Share of real engagers in the seed map (baseline niche share) | 8% | 5% – 12% | 203 | measured |
| 1B | nikolak47 | Seed map finds real engagers vs random accounts (lift) | 3.75x | 3.02x – 4.63x | 394 | proven |
| 1B | nikolak47 | Share of real engagers in the seed map (baseline niche share) | 26% | 22% – 30% | 394 | measured |
| 1B | pierreherubel | Seed map finds real engagers vs random accounts (lift) | 4.08x | 2.25x – 6.37x | 96 | proven |
| 1B | pierreherubel | Share of real engagers in the seed map (baseline niche share) | 16% | 10% – 24% | 96 | measured |
| 1B | thejcron | Seed map finds real engagers vs random accounts (lift) | 27.78x | 23.44x – 34.09x | 1 | weak (few engagers) |
| 1B | thejcron | Share of real engagers in the seed map (baseline niche share) | 100% | 21% – 100% | 1 | measured |
| 1C | Kenny_GTM | format = article: vs own usual level | 1.59x | 1.09x – 2.43x | 20 | proven better |
| 1C | Kenny_GTM | format = quote post: vs own usual level | 0.51x | 0.30x – 0.88x | 24 | proven worse |
| 1C | MichLieben | format = thread: vs own usual level | 1.93x | 1.57x – 2.55x | 31 | proven better |
| 1C | MichLieben | hook = giveaway / comment-to-get: vs own usual level | 5.55x | 1.42x – 50.93x | 35 | proven better |
| 1C | MichLieben | length = 1,000+: vs own usual level | 1.55x | 1.16x – 1.84x | 117 | proven better |
| 1C | MichLieben | length = 100-280: vs own usual level | 0.71x | 0.44x – 0.89x | 76 | proven worse |
| 1C | MichLieben | day_slot = 1st post of day: vs own usual level | 1.34x | 1.06x – 1.55x | 204 | proven better |
| 1C | MichLieben | day_slot = 3rd+: vs own usual level | 0.66x | 0.46x – 0.90x | 90 | proven worse |
| 1C | VukConfidential | weekday = Mon: vs own usual level | 1.90x | 1.02x – 2.43x | 18 | proven better |
| 1C | itsalexvacca | hook = giveaway / comment-to-get: vs own usual level | 11.58x | 2.08x – 20.78x | 33 | proven better |
| 1C | itsalexvacca | hook = number / result: vs own usual level | 0.70x | 0.52x – 0.91x | 76 | proven worse |
| 1C | itsalexvacca | topic = services / software / ai: vs own usual level | 1.45x | 1.10x – 2.32x | 57 | proven better |
| 1C | itsalexvacca | length = 100-280: vs own usual level | 0.63x | 0.44x – 0.87x | 68 | proven worse |
| 1C | itsalexvacca | hour_block = 12-17 UTC: vs own usual level | 1.23x | 1.02x – 1.46x | 240 | proven better |
| 1C | itsalexvacca | day_slot = 1st post of day: vs own usual level | 1.25x | 1.02x – 1.48x | 202 | proven better |
| 1C | itsalexvacca | day_slot = 3rd+: vs own usual level | 0.57x | 0.44x – 0.77x | 91 | proven worse |
| 1C | mailankhong | format = quote post: vs own usual level | 0.23x | 0.05x – 0.67x | 32 | proven worse |
| 1C | mailankhong | topic = product / growth / company: vs own usual level | 0.30x | 0.16x – 0.77x | 17 | proven worse |
| 1C | mailankhong | length = 100-280: vs own usual level | 0.25x | 0.00x – 0.50x | 27 | proven worse |
| 1C | mailankhong | hour_block = 06-11 UTC: vs own usual level | 0.24x | 0.09x – 0.91x | 19 | proven worse |
| 1C | nateandorsky | hour_block = 12-17 UTC: vs own usual level | 0.17x | 0.00x – 0.90x | 51 | proven worse |
| 1C | nateandorsky | day_slot = 1st post of day: vs own usual level | 0.17x | 0.00x – 0.90x | 51 | proven worse |
| 1C | nifinet | format = article: vs own usual level | 4.91x | 2.34x – 8.43x | 33 | proven better |
| 1C | nifinet | format = quote post: vs own usual level | 0.50x | 0.29x – 0.83x | 96 | proven worse |
| 1C | nifinet | topic = outbound / signal based / based: vs own usual level | 3.40x | 1.75x – 8.43x | 21 | proven better |
| 1C | nifinet | weekday = Sat: vs own usual level | 0.30x | 0.00x – 0.83x | 20 | proven worse |
| 1C | nikolak47 | format = long-form post: vs own usual level | 1.22x | 1.01x – 1.45x | 107 | proven better |
| 1C | nikolak47 | format = quote post: vs own usual level | 0.57x | 0.42x – 0.97x | 46 | proven worse |
| 1C | nikolak47 | topic = arr / saas / saas arr: vs own usual level | 1.47x | 1.07x – 2.12x | 39 | proven better |
| 1C | nikolak47 | topic = claude / choose / death: vs own usual level | 0.52x | 0.17x – 0.84x | 23 | proven worse |
| memory | Kenny_GTM | habit: format = quote post (worse, own evidence) | 0.56x | 0.39x – 0.96x | 24 | habit since 2026-09-27 |
| memory | MichLieben | habit: day_slot = 1st post of day (better, own evidence) | 1.31x | 1.05x – 1.48x | 204 | habit since 2026-08-23 |
| memory | MichLieben | habit: day_slot = 3rd+ (worse, own evidence) | 0.63x | 0.44x – 0.87x | 90 | habit since 2026-08-30 |
| memory | MichLieben | habit: format = thread (better, own evidence) | 1.87x | 1.18x – 3.30x | 31 | habit since 2026-09-13 |
| memory | MichLieben | habit: hook = giveaway / comment-to-get (better, own evidence) (reach only - never recommended) | 3.96x | 1.53x – 18.61x | 35 | habit since 2026-10-04 |
| memory | MichLieben | habit: length = 1,000+ (better, own evidence) | 1.45x | 1.12x – 1.66x | 117 | habit since 2026-09-06 |
| memory | MichLieben | habit: length = 100-280 (worse, own evidence) | 0.70x | 0.45x – 0.96x | 76 | habit since 2026-10-25 |
| memory | Tycho_luijten | habit: hook = statement (worse, own evidence) | 0.90x | 0.71x – 1.02x | 48 | habit since 2026-11-08 |
| memory | VukConfidential | habit: format = article (better, learned from all clients) | 1.63x | 1.10x – 2.17x | 19 | habit since 2026-10-25 |
| memory | imrenat | habit: hook = statement (worse, learned from all clients) | 0.76x | 0.52x – 0.96x | 2 | habit since 2026-08-23 |
| memory | itsalexvacca | emerging: day_slot = 1st post of day (better, own evidence) | 1.24x | 1.04x – 1.43x | 202 | emerging since 2026-11-15 |
| memory | itsalexvacca | habit: day_slot = 3rd+ (worse, own evidence) | 0.56x | 0.41x – 0.77x | 91 | habit since 2026-08-23 |
| memory | itsalexvacca | habit: hook = giveaway / comment-to-get (better, own evidence) (reach only - never recommended) | 6.19x | 1.77x – 13.06x | 33 | habit since 2026-08-23 |
| memory | itsalexvacca | habit: hook = number / result (worse, own evidence) | 0.75x | 0.59x – 0.96x | 76 | habit since 2026-08-23 |
| memory | itsalexvacca | habit: hour_block = 12-17 UTC (better, own evidence) | 1.22x | 1.03x – 1.42x | 240 | habit since 2026-09-06 |
| memory | itsalexvacca | habit: length = 100-280 (worse, own evidence) | 0.64x | 0.46x – 0.83x | 68 | habit since 2026-11-01 |
| memory | itsalexvacca | emerging: topic = pov / free / sauce (worse, own evidence) | 0.64x | 0.43x – 0.99x | 69 | emerging since 2026-11-01 |
| memory | itsalexvacca | emerging: topic = services / software / ai (better, own evidence) | 1.45x | 1.16x – 2.29x | 57 | emerging since 2026-11-15 |
| memory | itsalexvacca | habit: topic = services / software / services software (better, own evidence) | 1.44x | 1.14x – 2.39x | 51 | habit since 2026-08-23 |
| memory | itsivanfalco | emerging: format = quote post (worse, learned from all clients) | 0.57x | 0.32x – 1.00x | 11 | emerging since 2026-11-01 |
| memory | kennyrueter | habit: format = thread (better, learned from all clients) | 3.02x | 1.11x – 7.68x | 10 | habit since 2026-08-23 |
| memory | mailankhong | habit: format = quote post (worse, own evidence) | 0.33x | 0.18x – 0.68x | 32 | habit since 2026-11-08 |
| memory | mailankhong | emerging: hook = statement (worse, own evidence) | 0.62x | 0.32x – 0.93x | 45 | emerging since 2026-11-15 |
| memory | mailankhong | emerging: hour_block = 06-11 UTC (worse, learned from all clients) | 0.45x | 0.17x – 0.82x | 19 | emerging since 2026-11-15 |
| memory | mailankhong | habit: length = 100-280 (worse, own evidence) | 0.38x | 0.14x – 0.67x | 27 | habit since 2026-11-08 |
| memory | mailankhong | habit: topic = product / growth / company (worse, own evidence) | 0.30x | 0.18x – 0.77x | 17 | habit since 2026-11-08 |
| memory | nateandorsky | emerging: day_slot = 1st post of day (worse, own evidence) | 0.29x | 0.11x – 0.94x | 51 | emerging since 2026-10-18 |
| memory | nateandorsky | emerging: hour_block = 12-17 UTC (worse, own evidence) | 0.29x | 0.11x – 0.97x | 51 | emerging since 2026-11-01 |
| memory | nateandorsky | emerging: length = 281-1,000 (worse, learned from all clients) | 0.37x | 0.25x – 1.00x | 11 | emerging since 2026-11-08 |
| memory | nifinet | habit: format = article (better, own evidence) | 3.01x | 1.62x – 4.55x | 33 | habit since 2026-08-23 |
| memory | nifinet | habit: format = quote post (worse, own evidence) | 0.52x | 0.35x – 0.85x | 95 | habit since 2026-08-30 |
| memory | nifinet | habit: hour_block = 00-05 UTC (worse, learned from all clients) | 0.27x | 0.05x – 0.68x | 12 | habit since 2026-09-20 |
| memory | nifinet | emerging: topic = outbound / signal based / based (better, own evidence) | 3.40x | 1.75x – 8.43x | 21 | emerging since 2026-11-15 |
| memory | nifinet | habit: topic = outbound / signal based / based outbound (better, own evidence) | 3.40x | 1.90x – 7.37x | 19 | habit since 2026-10-11 |
| memory | nikolak47 | habit: format = long-form post (better, own evidence) | 1.20x | 1.01x – 1.39x | 107 | habit since 2026-10-25 |
| memory | nikolak47 | habit: format = quote post (worse, own evidence) | 0.59x | 0.44x – 0.94x | 46 | habit since 2026-10-11 |
| memory | nikolak47 | emerging: topic = claude / choose / death (worse, own evidence) | 0.52x | 0.16x – 0.84x | 23 | emerging since 2026-11-15 |
| memory | nikolak47 | emerging: topic = claude / saastanak / launch (worse, own evidence) | 0.46x | 0.13x – 1.12x | 17 | emerging since 2026-10-25 |
| memory | nikolak47 | habit: topic = saas / saas arr / arr (better, own evidence) | 1.93x | 0.91x – 4.22x | 23 | habit since 2026-10-18 |
| 1D |  | Model ranks an account's posts (within-author Spearman) | 0.20 | 0.18 – 0.22 | 848 | measured |
| 1D |  | Model beats the best simple baseline (difference in ranking) | 0.17 | 0.15 – 0.19 | 848 | proven |
| 3 |  | Forecast bookmarks: typical miss before posting (backtest) | 2.82x | — – — | 27609 | proven better than the usual level |
| 3 |  | Forecast bookmarks: share of posts inside the 80% range (backtest) | 79% | — – — | 27609 | measured |
| 3 |  | Forecast likes: typical miss before posting (backtest) | 2.32x | — – — | 27609 | proven better than the usual level |
| 3 |  | Forecast likes: share of posts inside the 80% range (backtest) | 78% | — – — | 27609 | measured |
| 3 |  | Forecast quotes: typical miss before posting (backtest) | 1.70x | — – — | 27609 | proven better than the usual level |
| 3 |  | Forecast quotes: share of posts inside the 80% range (backtest) | 81% | — – — | 27609 | measured |
| 3 |  | Forecast replies: typical miss before posting (backtest) | 2.00x | — – — | 27609 | proven better than the usual level |
| 3 |  | Forecast replies: share of posts inside the 80% range (backtest) | 79% | — – — | 27609 | measured |
| 3 |  | Forecast reposts: typical miss before posting (backtest) | 2.08x | — – — | 27609 | proven better than the usual level |
| 3 |  | Forecast reposts: share of posts inside the 80% range (backtest) | 81% | — – — | 27609 | measured |
| 3 |  | Forecast views: typical miss before posting (backtest) | 2.31x | — – — | 27609 | proven better than the usual level |
| 3 |  | Forecast views: share of posts inside the 80% range (backtest) | 77% | — – — | 27609 | measured |
| 3 |  | Forecast xscore: typical miss before posting (backtest) | 2.26x | — – — | 27609 | proven better than the usual level |
| 3 |  | Forecast xscore: share of posts inside the 80% range (backtest) | 78% | — – — | 27609 | measured |
| data | itsalexvacca | Share of replies + quotes X lets us collect | 57% | 54% – 60% | 997 | measured |
| data | MichLieben | Share of replies + quotes X lets us collect | 52% | 48% – 55% | 761 | measured |
| data | nifinet | Share of replies + quotes X lets us collect | 26% | 23% – 29% | 1040 | measured |
| data | VukConfidential | Share of replies + quotes X lets us collect | 59% | 52% – 66% | 174 | measured |
| data | nikolak47 | Share of replies + quotes X lets us collect | 56% | 53% – 59% | 1042 | measured |
| data | Vick_Mucunski | Share of replies + quotes X lets us collect | 35% | 24% – 49% | 54 | measured |
| data | itsivanfalco | Share of replies + quotes X lets us collect | 0% | 0% – 56% | 3 | measured |
| data | Kenny_GTM | Share of replies + quotes X lets us collect | 36% | 28% – 46% | 107 | measured |
| data | mailankhong | Share of replies + quotes X lets us collect | 17% | 9% – 29% | 53 | measured |
| data | Tycho_luijten | Share of replies + quotes X lets us collect | 33% | 10% – 70% | 6 | measured |
| data | thejcron | Share of replies + quotes X lets us collect | 25% | 5% – 70% | 4 | measured |
| data | pierreherubel | Share of replies + quotes X lets us collect | 56% | 49% – 63% | 195 | measured |
| data | nateandorsky | Share of replies + quotes X lets us collect | 75% | 41% – 93% | 8 | measured |
| data | imrenat | Share of replies + quotes X lets us collect | 100% | 21% – 100% | 1 | measured |
