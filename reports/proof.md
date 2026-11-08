# Phase 1 proof · 08 Nov 2026 08:59 UTC

## Trust checks

- ✅ **Our data matches xplatform post by post (same posts; likes/views within 5%)**: 2026-10, UTC days: itsalexvacca 101 posts, MichLieben 93 posts, nifinet 123 posts, VukConfidential 58 posts, nikolak47 165 posts, Vick_Mucunski 48 posts, itsivanfalco 18 posts, Kenny_GTM 21 posts, mailankhong 150 posts, Tycho_luijten 11 posts, thejcron 3 posts, pierreherubel 22 posts, nateandorsky 35 posts, imrenat 1 posts
- ✅ **No client data leaks into what we measure**: hold-out map has no clients; 1C and tracking read the hold-out map
- ✅ **Data is fresh (posts < 36h, daily steps < 36h, weekly < 8 days)**: newest post 1h old; engage 2h ago; content 1h ago; segments 1h ago; seeds 1h ago; backtest 1h ago; live 0h ago; memory 1h ago
- ⚠️ **Every claim rests on enough data (weak ones are flagged, not hidden)**: 1A  In-niche vs off-topic accuracy, vs the team's labels (n=1); 1A  Right niche (main or 2nd), vs the team's labels (n=1); 1A  AI reviewer agrees with the team (random audits + disagreements) (n=1); 1B Tycho_luijten Seed map finds real engagers vs random accounts (lift) (n=5); 1B Vick_Mucunski Seed map finds real engagers vs random accounts (lift) (n=21); 1B imrenat Seed map finds real engagers vs random accounts (lift) (n=2); 1B itsivanfalco Seed map finds real engagers vs random accounts (lift) (n=5); 1B mailankhong Seed map finds real engagers vs random accounts (lift) (n=11); 1B nateandorsky Seed map finds real engagers vs random accounts (lift) (n=5); 1B thejcron Seed map finds real engagers vs random accounts (lift) (n=4)
- ✅ **1D test uses only posts after the split date**: earliest test post 15 Oct 2026 (split 2026-10-15)
- ⚠️ **AI reviewer stays in line with the team (>= 80% agreement)**: only 1 accounts reviewed by both so far; need 30 to judge
- ✅ **Long-term memory is built and stable**: 13 weeks in memory (6 forgotten, 10 emerging, 3 new, 24 habit, 4 fading); no client's situation changed

## Claims with 95% ranges

| step | client | claim | value | 95% range | n | status |
|---|---|---|---:|---|---:|---|
| 1A |  | In-niche vs off-topic accuracy, vs Claude's hand labels | 91% | 87% – 94% | 353 | proven |
| 1A |  | Right niche (main or 2nd), vs Claude's hand labels | 86% | 80% – 90% | 156 | not yet proven above 80% |
| 1A |  | In-niche vs off-topic accuracy, vs the team's labels | 100% | 21% – 100% | 1 | weak (few labels) |
| 1A |  | Right niche (main or 2nd), vs the team's labels | 100% | 21% – 100% | 1 | weak (few labels) |
| 1A |  | In-niche vs off-topic accuracy, vs the AI reviewer's labels | 96% | 93% – 98% | 288 | proven |
| 1A |  | Right niche (main or 2nd), vs the AI reviewer's labels | 95% | 88% – 98% | 96 | proven |
| 1A |  | AI reviewer agrees with the team (random audits + disagreements) | 100% | 21% – 100% | 1 | weak (few audits) |
| 2A |  | Engage-list posts the AI reviewer judges worth replying to | 66% | 58% – 74% | 125 | measured |
| 1B | Kenny_GTM | Seed map finds real engagers vs random accounts (lift) | 3.50x | 1.68x – 5.44x | 31 | proven |
| 1B | Kenny_GTM | Share of real engagers in the seed map (baseline niche share) | 29% | 16% – 47% | 31 | measured |
| 1B | MichLieben | Seed map finds real engagers vs random accounts (lift) | 5.75x | 4.25x – 7.69x | 232 | proven |
| 1B | MichLieben | Share of real engagers in the seed map (baseline niche share) | 24% | 19% – 30% | 232 | measured |
| 1B | Tycho_luijten | Seed map finds real engagers vs random accounts (lift) | 4.76x | 0.00x – 14.40x | 5 | weak (few engagers) |
| 1B | Tycho_luijten | Share of real engagers in the seed map (baseline niche share) | 20% | 4% – 62% | 5 | measured |
| 1B | Vick_Mucunski | Seed map finds real engagers vs random accounts (lift) | 3.25x | 0.00x – 7.08x | 21 | weak (few engagers) |
| 1B | Vick_Mucunski | Share of real engagers in the seed map (baseline niche share) | 14% | 5% – 35% | 21 | measured |
| 1B | VukConfidential | Seed map finds real engagers vs random accounts (lift) | 3.69x | 2.27x – 5.32x | 49 | proven |
| 1B | VukConfidential | Share of real engagers in the seed map (baseline niche share) | 31% | 20% – 45% | 49 | measured |
| 1B | imrenat | Seed map finds real engagers vs random accounts (lift) | 11.36x | 0.00x – 25.42x | 2 | weak (few engagers) |
| 1B | imrenat | Share of real engagers in the seed map (baseline niche share) | 50% | 9% – 91% | 2 | measured |
| 1B | itsalexvacca | Seed map finds real engagers vs random accounts (lift) | 4.41x | 3.23x – 5.77x | 281 | proven |
| 1B | itsalexvacca | Share of real engagers in the seed map (baseline niche share) | 19% | 14% – 23% | 281 | measured |
| 1B | itsivanfalco | Seed map finds real engagers vs random accounts (lift) | 4.76x | 0.00x – 15.39x | 5 | weak (few engagers) |
| 1B | itsivanfalco | Share of real engagers in the seed map (baseline niche share) | 20% | 4% – 62% | 5 | measured |
| 1B | mailankhong | Seed map finds real engagers vs random accounts (lift) | 2.07x | 0.00x – 6.44x | 11 | weak (few engagers) |
| 1B | mailankhong | Share of real engagers in the seed map (baseline niche share) | 9% | 2% – 38% | 11 | measured |
| 1B | nateandorsky | Seed map finds real engagers vs random accounts (lift) | 0.00x | 0.00x – 0.00x | 5 | weak (few engagers) |
| 1B | nateandorsky | Share of real engagers in the seed map (baseline niche share) | 0% | 0% – 43% | 5 | measured |
| 1B | nifinet | Seed map finds real engagers vs random accounts (lift) | 1.72x | 0.95x – 2.79x | 208 | not proven |
| 1B | nifinet | Share of real engagers in the seed map (baseline niche share) | 7% | 4% – 12% | 208 | measured |
| 1B | nikolak47 | Seed map finds real engagers vs random accounts (lift) | 3.03x | 2.39x – 3.74x | 349 | proven |
| 1B | nikolak47 | Share of real engagers in the seed map (baseline niche share) | 23% | 19% – 27% | 349 | measured |
| 1B | pierreherubel | Seed map finds real engagers vs random accounts (lift) | 1.24x | 0.28x – 2.68x | 77 | not proven |
| 1B | pierreherubel | Share of real engagers in the seed map (baseline niche share) | 5% | 2% – 13% | 77 | measured |
| 1B | thejcron | Seed map finds real engagers vs random accounts (lift) | 5.68x | 0.00x – 17.05x | 4 | weak (few engagers) |
| 1B | thejcron | Share of real engagers in the seed map (baseline niche share) | 25% | 5% – 70% | 4 | measured |
| 1C | Kenny_GTM | format = quote post: vs own usual level | 0.48x | 0.15x – 0.85x | 19 | proven worse |
| 1C | MichLieben | format = thread: vs own usual level | 1.91x | 1.57x – 2.55x | 31 | proven better |
| 1C | MichLieben | hook = giveaway / comment-to-get: vs own usual level | 10.36x | 1.92x – 61.89x | 33 | proven better |
| 1C | MichLieben | length = 1,000+: vs own usual level | 1.55x | 1.09x – 1.84x | 115 | proven better |
| 1C | MichLieben | length = 100-280: vs own usual level | 0.69x | 0.42x – 0.87x | 73 | proven worse |
| 1C | MichLieben | day_slot = 1st post of day: vs own usual level | 1.34x | 1.03x – 1.52x | 197 | proven better |
| 1C | MichLieben | day_slot = 3rd+: vs own usual level | 0.66x | 0.46x – 0.90x | 88 | proven worse |
| 1C | VukConfidential | weekday = Mon: vs own usual level | 1.88x | 1.02x – 2.48x | 18 | proven better |
| 1C | itsalexvacca | hook = giveaway / comment-to-get: vs own usual level | 11.58x | 2.08x – 20.78x | 33 | proven better |
| 1C | itsalexvacca | hook = number / result: vs own usual level | 0.63x | 0.52x – 0.91x | 73 | proven worse |
| 1C | itsalexvacca | topic = pov / free / sauce: vs own usual level | 0.62x | 0.43x – 0.99x | 65 | proven worse |
| 1C | itsalexvacca | length = 100-280: vs own usual level | 0.62x | 0.44x – 0.82x | 64 | proven worse |
| 1C | itsalexvacca | hour_block = 12-17 UTC: vs own usual level | 1.23x | 1.02x – 1.45x | 233 | proven better |
| 1C | itsalexvacca | day_slot = 1st post of day: vs own usual level | 1.24x | 1.01x – 1.49x | 195 | proven better |
| 1C | itsalexvacca | day_slot = 3rd+: vs own usual level | 0.57x | 0.44x – 0.80x | 88 | proven worse |
| 1C | mailankhong | format = quote post: vs own usual level | 0.23x | 0.05x – 0.67x | 32 | proven worse |
| 1C | mailankhong | topic = product / growth / company: vs own usual level | 0.30x | 0.16x – 0.77x | 17 | proven worse |
| 1C | mailankhong | length = 100-280: vs own usual level | 0.25x | 0.00x – 0.50x | 27 | proven worse |
| 1C | mailankhong | hour_block = 06-11 UTC: vs own usual level | 0.24x | 0.09x – 0.91x | 19 | proven worse |
| 1C | nateandorsky | hour_block = 12-17 UTC: vs own usual level | 0.17x | 0.00x – 0.90x | 51 | proven worse |
| 1C | nateandorsky | day_slot = 1st post of day: vs own usual level | 0.17x | 0.00x – 0.90x | 51 | proven worse |
| 1C | nifinet | format = article: vs own usual level | 4.91x | 2.34x – 8.43x | 33 | proven better |
| 1C | nifinet | format = quote post: vs own usual level | 0.52x | 0.28x – 0.86x | 94 | proven worse |
| 1C | nifinet | topic = outbound / signal based / based outbound: vs own usual level | 3.40x | 1.70x – 8.43x | 19 | proven better |
| 1C | nikolak47 | format = long-form post: vs own usual level | 1.26x | 1.02x – 1.49x | 98 | proven better |
| 1C | nikolak47 | format = quote post: vs own usual level | 0.54x | 0.41x – 0.98x | 45 | proven worse |
| memory | Kenny_GTM | habit: format = quote post (worse, learned from all clients) | 0.54x | 0.28x – 1.02x | 15 | habit since 2026-09-27 |
| memory | MichLieben | habit: day_slot = 1st post of day (better, own evidence) | 1.29x | 0.99x – 1.47x | 191 | habit since 2026-08-23 |
| memory | MichLieben | habit: day_slot = 3rd+ (worse, own evidence) | 0.61x | 0.40x – 0.88x | 87 | habit since 2026-08-30 |
| memory | MichLieben | habit: format = thread (better, own evidence) | 1.82x | 1.11x – 3.52x | 29 | habit since 2026-09-13 |
| memory | MichLieben | habit: hook = giveaway / comment-to-get (better, own evidence) (reach only - never recommended) | 5.85x | 1.71x – 30.33x | 32 | habit since 2026-10-04 |
| memory | MichLieben | habit: hour_block = 18-23 UTC (worse, own evidence) | 0.85x | 0.69x – 1.00x | 155 | habit since 2026-10-25 |
| memory | MichLieben | habit: length = 1,000+ (better, own evidence) | 1.35x | 1.05x – 1.67x | 111 | habit since 2026-09-06 |
| memory | MichLieben | habit: length = 100-280 (worse, own evidence) | 0.69x | 0.46x – 0.85x | 72 | habit since 2026-10-25 |
| memory | Tycho_luijten | emerging: hook = statement (worse, own evidence) | 0.89x | 0.68x – 0.99x | 48 | emerging since 2026-09-27 |
| memory | VukConfidential | habit: format = article (better, learned from all clients) | 1.59x | 0.94x – 2.16x | 19 | habit since 2026-10-25 |
| memory | imrenat | habit: hook = statement (worse, learned from all clients) | 0.76x | 0.54x – 0.89x | 2 | habit since 2026-08-23 |
| memory | itsalexvacca | habit: day_slot = 3rd+ (worse, own evidence) | 0.56x | 0.38x – 0.80x | 85 | habit since 2026-08-23 |
| memory | itsalexvacca | habit: hook = giveaway / comment-to-get (better, own evidence) (reach only - never recommended) | 6.23x | 2.65x – 13.89x | 31 | habit since 2026-08-23 |
| memory | itsalexvacca | habit: hook = number / result (worse, own evidence) | 0.70x | 0.61x – 0.94x | 71 | habit since 2026-08-23 |
| memory | itsalexvacca | habit: hour_block = 12-17 UTC (better, own evidence) | 1.22x | 1.01x – 1.40x | 230 | habit since 2026-09-06 |
| memory | itsalexvacca | habit: length = 100-280 (worse, own evidence) | 0.63x | 0.45x – 0.93x | 62 | habit since 2026-11-01 |
| memory | itsalexvacca | emerging: topic = pov / free / sauce (worse, own evidence) | 0.64x | 0.43x – 0.99x | 69 | emerging since 2026-11-01 |
| memory | itsalexvacca | habit: topic = services / software / services software (better, own evidence) | 1.44x | 1.14x – 2.39x | 51 | habit since 2026-08-23 |
| memory | itsivanfalco | emerging: format = quote post (worse, learned from all clients) | 0.52x | 0.33x – 0.98x | 11 | emerging since 2026-11-01 |
| memory | kennyrueter | habit: format = thread (better, learned from all clients) | 2.99x | 1.10x – 8.74x | 10 | habit since 2026-08-23 |
| memory | mailankhong | emerging: format = quote post (worse, own evidence) | 0.32x | 0.15x – 0.67x | 32 | emerging since 2026-11-01 |
| memory | mailankhong | emerging: length = 100-280 (worse, own evidence) | 0.38x | 0.14x – 0.72x | 27 | emerging since 2026-11-01 |
| memory | mailankhong | emerging: topic = product / growth / company (worse, own evidence) | 0.30x | 0.20x – 0.77x | 17 | emerging since 2026-11-01 |
| memory | nateandorsky | emerging: day_slot = 1st post of day (worse, own evidence) | 0.28x | 0.11x – 0.97x | 51 | emerging since 2026-10-18 |
| memory | nateandorsky | emerging: format = long-form post (worse, own evidence) | 0.14x | 0.13x – 0.82x | 39 | emerging since 2026-11-01 |
| memory | nateandorsky | emerging: hour_block = 12-17 UTC (worse, own evidence) | 0.29x | 0.12x – 0.97x | 51 | emerging since 2026-11-01 |
| memory | nifinet | habit: format = article (better, own evidence) | 2.89x | 1.69x – 4.28x | 31 | habit since 2026-08-23 |
| memory | nifinet | habit: format = quote post (worse, own evidence) | 0.51x | 0.33x – 0.84x | 90 | habit since 2026-08-30 |
| memory | nifinet | habit: hour_block = 00-05 UTC (worse, learned from all clients) | 0.27x | 0.05x – 0.68x | 12 | habit since 2026-09-20 |
| memory | nifinet | habit: topic = outbound / signal based / based outbound (better, own evidence) | 3.40x | 1.90x – 7.37x | 19 | habit since 2026-10-11 |
| memory | nikolak47 | habit: format = long-form post (better, own evidence) | 1.25x | 1.05x – 1.48x | 94 | habit since 2026-10-25 |
| memory | nikolak47 | habit: format = quote post (worse, own evidence) | 0.54x | 0.44x – 0.88x | 43 | habit since 2026-10-11 |
| memory | nikolak47 | emerging: topic = claude / saastanak / launch (worse, own evidence) | 0.46x | 0.13x – 1.12x | 17 | emerging since 2026-10-25 |
| memory | nikolak47 | habit: topic = saas / saas arr / arr (better, own evidence) | 1.93x | 0.91x – 4.22x | 23 | habit since 2026-10-18 |
| 1D |  | Model ranks an account's posts (within-author Spearman) | 0.18 | 0.16 – 0.21 | 579 | measured |
| 1D |  | Model beats the best simple baseline (difference in ranking) | 0.17 | 0.15 – 0.20 | 579 | proven |
| data | itsalexvacca | Share of replies + quotes X lets us collect | 50% | 46% – 53% | 987 | measured |
| data | MichLieben | Share of replies + quotes X lets us collect | 50% | 47% – 54% | 703 | measured |
| data | nifinet | Share of replies + quotes X lets us collect | 26% | 24% – 29% | 1051 | measured |
| data | VukConfidential | Share of replies + quotes X lets us collect | 58% | 51% – 66% | 171 | measured |
| data | nikolak47 | Share of replies + quotes X lets us collect | 54% | 51% – 58% | 916 | measured |
| data | Vick_Mucunski | Share of replies + quotes X lets us collect | 39% | 28% – 52% | 59 | measured |
| data | itsivanfalco | Share of replies + quotes X lets us collect | 25% | 11% – 47% | 20 | measured |
| data | Kenny_GTM | Share of replies + quotes X lets us collect | 46% | 35% – 57% | 72 | measured |
| data | mailankhong | Share of replies + quotes X lets us collect | 19% | 11% – 31% | 62 | measured |
| data | Tycho_luijten | Share of replies + quotes X lets us collect | 44% | 19% – 73% | 9 | measured |
| data | thejcron | Share of replies + quotes X lets us collect | 38% | 14% – 69% | 8 | measured |
| data | pierreherubel | Share of replies + quotes X lets us collect | 54% | 46% – 61% | 156 | measured |
| data | nateandorsky | Share of replies + quotes X lets us collect | 67% | 35% – 88% | 9 | measured |
| data | imrenat | Share of replies + quotes X lets us collect | 40% | 12% – 77% | 5 | measured |
