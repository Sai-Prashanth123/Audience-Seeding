# Phase 1 proof · 27 Nov 2026 10:50 UTC

## Trust checks

- ✅ **Our data matches xplatform post by post (same posts; likes/views within 5%)**: 2026-10, UTC days: itsalexvacca 101 posts, MichLieben 93 posts, nifinet 123 posts, VukConfidential 58 posts, nikolak47 165 posts, Vick_Mucunski 48 posts, itsivanfalco 18 posts, Kenny_GTM 21 posts, mailankhong 150 posts, Tycho_luijten 11 posts, thejcron 3 posts, pierreherubel 22 posts, nateandorsky 35 posts, imrenat 1 posts
- ✅ **No client data leaks into what we measure**: hold-out map has no clients; 1C and tracking read the hold-out map
- ❌ **Data is fresh (posts < 36h, daily steps < 36h, weekly < 8 days)**: segments 261h ago; seeds 260h ago; backtest 260h ago; memory 260h ago; forecast-train 260h ago; newest post 2h old; engage 2h ago; content 2h ago; live 0h ago; live-check 0h ago
- ⚠️ **Every claim rests on enough data (weak ones are flagged, not hidden)**: 1A  In-niche vs off-topic accuracy, vs the team's labels (n=1); 1A  Right niche (main or 2nd), vs the team's labels (n=1); 1A  AI reviewer agrees with the team (random audits + disagreements) (n=1); 1B Tycho_luijten Seed map finds real engagers vs random accounts (lift) (n=2); 1B Vick_Mucunski Seed map finds real engagers vs random accounts (lift) (n=16); 1B imrenat Seed map finds real engagers vs random accounts (lift) (n=2); 1B itsivanfalco Seed map finds real engagers vs random accounts (lift) (n=1); 1B mailankhong Seed map finds real engagers vs random accounts (lift) (n=9); 1B nateandorsky Seed map finds real engagers vs random accounts (lift) (n=5); 1B thejcron Seed map finds real engagers vs random accounts (lift) (n=1)
- ✅ **1D test uses only posts after the split date**: earliest test post 15 Oct 2026 (split 2026-10-15)
- ⚠️ **AI reviewer stays in line with the team (>= 80% agreement)**: only 1 accounts reviewed by both so far; need 30 to judge
- ✅ **Long-term memory is built and stable**: 15 weeks in memory (5 fading, 12 emerging, 4 new, 6 forgotten, 27 habit); no client's situation changed
- ✅ **Forecasts are honest (80% ranges hold; frozen before results)**: 97 live posts forecast before their results; live 78% inside (95% range 74%-81%, n=532)

## Claims with 95% ranges

| step | client | claim | value | 95% range | n | status |
|---|---|---|---:|---|---:|---|
| 1A |  | In-niche vs off-topic accuracy, vs Claude's hand labels | 90% | 87% – 93% | 353 | proven |
| 1A |  | Right niche (main or 2nd), vs Claude's hand labels | 84% | 77% – 89% | 154 | not yet proven above 80% |
| 1A |  | In-niche vs off-topic accuracy, vs the team's labels | 100% | 21% – 100% | 1 | weak (few labels) |
| 1A |  | Right niche (main or 2nd), vs the team's labels | 100% | 21% – 100% | 1 | weak (few labels) |
| 1A |  | In-niche vs off-topic accuracy, vs the AI reviewer's labels | 94% | 92% – 96% | 520 | proven |
| 1A |  | Right niche (main or 2nd), vs the AI reviewer's labels | 95% | 90% – 97% | 168 | proven |
| 1A |  | AI reviewer agrees with the team (random audits + disagreements) | 100% | 21% – 100% | 1 | weak (few audits) |
| 2A |  | Engage-list posts the AI reviewer judges worth replying to | 56% | 54% – 59% | 2195 | measured |
| 1B | Kenny_GTM | Seed map finds real engagers vs random accounts (lift) | 5.11x | 2.94x – 7.55x | 35 | proven |
| 1B | Kenny_GTM | Share of real engagers in the seed map (baseline niche share) | 37% | 23% – 54% | 35 | measured |
| 1B | MichLieben | Seed map finds real engagers vs random accounts (lift) | 7.50x | 5.74x – 9.80x | 242 | proven |
| 1B | MichLieben | Share of real engagers in the seed map (baseline niche share) | 29% | 23% – 35% | 242 | measured |
| 1B | Tycho_luijten | Seed map finds real engagers vs random accounts (lift) | 13.16x | 0.00x – 29.70x | 2 | weak (few engagers) |
| 1B | Tycho_luijten | Share of real engagers in the seed map (baseline niche share) | 50% | 9% – 91% | 2 | measured |
| 1B | Vick_Mucunski | Seed map finds real engagers vs random accounts (lift) | 7.81x | 1.82x – 16.49x | 16 | weak (few engagers) |
| 1B | Vick_Mucunski | Share of real engagers in the seed map (baseline niche share) | 25% | 10% – 49% | 16 | measured |
| 1B | VukConfidential | Seed map finds real engagers vs random accounts (lift) | 4.40x | 2.64x – 6.30x | 50 | proven |
| 1B | VukConfidential | Share of real engagers in the seed map (baseline niche share) | 32% | 21% – 46% | 50 | measured |
| 1B | imrenat | Seed map finds real engagers vs random accounts (lift) | 15.62x | 0.00x – 35.30x | 2 | weak (few engagers) |
| 1B | imrenat | Share of real engagers in the seed map (baseline niche share) | 50% | 9% – 91% | 2 | measured |
| 1B | itsalexvacca | Seed map finds real engagers vs random accounts (lift) | 5.88x | 4.47x – 7.72x | 318 | proven |
| 1B | itsalexvacca | Share of real engagers in the seed map (baseline niche share) | 22% | 18% – 27% | 318 | measured |
| 1B | itsivanfalco | Seed map finds real engagers vs random accounts (lift) | 0.00x | 0.00x – 0.00x | 1 | weak (few engagers) |
| 1B | itsivanfalco | Share of real engagers in the seed map (baseline niche share) | 0% | 0% – 79% | 1 | measured |
| 1B | mailankhong | Seed map finds real engagers vs random accounts (lift) | 6.17x | 0.00x – 14.88x | 9 | weak (few engagers) |
| 1B | mailankhong | Share of real engagers in the seed map (baseline niche share) | 22% | 6% – 55% | 9 | measured |
| 1B | nateandorsky | Seed map finds real engagers vs random accounts (lift) | 0.00x | 0.00x – 0.00x | 5 | weak (few engagers) |
| 1B | nateandorsky | Share of real engagers in the seed map (baseline niche share) | 0% | 0% – 43% | 5 | measured |
| 1B | nifinet | Seed map finds real engagers vs random accounts (lift) | 2.07x | 1.13x – 3.30x | 203 | proven |
| 1B | nifinet | Share of real engagers in the seed map (baseline niche share) | 8% | 5% – 12% | 203 | measured |
| 1B | nikolak47 | Seed map finds real engagers vs random accounts (lift) | 4.02x | 3.24x – 4.92x | 394 | proven |
| 1B | nikolak47 | Share of real engagers in the seed map (baseline niche share) | 26% | 22% – 31% | 394 | measured |
| 1B | pierreherubel | Seed map finds real engagers vs random accounts (lift) | 3.56x | 1.82x – 5.66x | 96 | proven |
| 1B | pierreherubel | Share of real engagers in the seed map (baseline niche share) | 14% | 8% – 22% | 96 | measured |
| 1B | thejcron | Seed map finds real engagers vs random accounts (lift) | 31.25x | 25.86x – 38.96x | 1 | weak (few engagers) |
| 1B | thejcron | Share of real engagers in the seed map (baseline niche share) | 100% | 21% – 100% | 1 | measured |
| 1C | Kenny_GTM | format = quote post: vs own usual level | 0.61x | 0.32x – 0.90x | 37 | proven worse |
| 1C | MichLieben | format = thread: vs own usual level | 1.84x | 1.52x – 3.05x | 35 | proven better |
| 1C | MichLieben | hook = giveaway / comment-to-get: vs own usual level | 7.82x | 1.38x – 39.20x | 36 | proven better |
| 1C | MichLieben | length = 1,000+: vs own usual level | 1.55x | 1.18x – 1.86x | 125 | proven better |
| 1C | MichLieben | length = 100-280: vs own usual level | 0.71x | 0.45x – 0.88x | 79 | proven worse |
| 1C | MichLieben | weekday = Sun: vs own usual level | 1.44x | 1.05x – 1.96x | 28 | proven better |
| 1C | MichLieben | day_slot = 1st post of day: vs own usual level | 1.35x | 1.08x – 1.55x | 214 | proven better |
| 1C | MichLieben | day_slot = 3rd+: vs own usual level | 0.67x | 0.46x – 0.88x | 94 | proven worse |
| 1C | Tycho_luijten | hook = statement: vs own usual level | 0.86x | 0.60x – 1.00x | 48 | proven worse |
| 1C | Tycho_luijten | hour_block = 18-23 UTC: vs own usual level | 0.81x | 0.64x – 1.00x | 28 | proven worse |
| 1C | itsalexvacca | hook = giveaway / comment-to-get: vs own usual level | 8.58x | 2.29x – 19.69x | 37 | proven better |
| 1C | itsalexvacca | hook = number / result: vs own usual level | 0.70x | 0.52x – 0.91x | 77 | proven worse |
| 1C | itsalexvacca | topic = pov / finding / free: vs own usual level | 0.73x | 0.53x – 0.99x | 96 | proven worse |
| 1C | itsalexvacca | topic = software / services / services software: vs own usual level | 1.42x | 1.11x – 2.25x | 70 | proven better |
| 1C | itsalexvacca | length = 100-280: vs own usual level | 0.67x | 0.47x – 0.86x | 73 | proven worse |
| 1C | itsalexvacca | hour_block = 12-17 UTC: vs own usual level | 1.24x | 1.03x – 1.43x | 248 | proven better |
| 1C | itsalexvacca | weekday = Sun: vs own usual level | 1.33x | 1.02x – 2.33x | 30 | proven better |
| 1C | itsalexvacca | day_slot = 1st post of day: vs own usual level | 1.30x | 1.04x – 1.50x | 213 | proven better |
| 1C | itsalexvacca | day_slot = 3rd+: vs own usual level | 0.58x | 0.43x – 0.80x | 95 | proven worse |
| 1C | mailankhong | format = quote post: vs own usual level | 0.21x | 0.00x – 0.66x | 32 | proven worse |
| 1C | mailankhong | topic = product / growth / company: vs own usual level | 0.31x | 0.16x – 0.77x | 17 | proven worse |
| 1C | mailankhong | length = 100-280: vs own usual level | 0.26x | 0.00x – 0.50x | 27 | proven worse |
| 1C | mailankhong | hour_block = 06-11 UTC: vs own usual level | 0.21x | 0.09x – 0.88x | 19 | proven worse |
| 1C | nateandorsky | hour_block = 12-17 UTC: vs own usual level | 0.18x | 0.00x – 0.89x | 51 | proven worse |
| 1C | nateandorsky | day_slot = 1st post of day: vs own usual level | 0.18x | 0.00x – 0.89x | 51 | proven worse |
| 1C | nifinet | format = article: vs own usual level | 4.84x | 2.31x – 8.54x | 33 | proven better |
| 1C | nifinet | format = quote post: vs own usual level | 0.49x | 0.29x – 0.84x | 98 | proven worse |
| 1C | nifinet | topic = laptop / great / gift: vs own usual level | 0.38x | 0.12x – 0.90x | 32 | proven worse |
| 1C | nifinet | topic = outbound / signal based / based: vs own usual level | 3.96x | 1.74x – 8.57x | 21 | proven better |
| 1C | nikolak47 | format = long-form post: vs own usual level | 1.23x | 1.02x – 1.48x | 109 | proven better |
| 1C | nikolak47 | format = quote post: vs own usual level | 0.58x | 0.43x – 0.97x | 46 | proven worse |
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
| 1D |  | Model ranks an account's posts (within-author Spearman) | 0.21 | 0.19 – 0.22 | 861 | measured |
| 1D |  | Model beats the best simple baseline (difference in ranking) | 0.17 | 0.15 – 0.19 | 861 | proven |
| 3 |  | Live forecasts of bookmarks inside their 80% range | 68% | 57% – 78% | 76 | measured |
| 3 |  | Live forecasts of likes inside their 80% range | 76% | 66% – 84% | 76 | measured |
| 3 |  | Live forecasts of quotes inside their 80% range | 84% | 74% – 91% | 76 | measured |
| 3 |  | Live forecasts of replies inside their 80% range | 82% | 71% – 89% | 76 | measured |
| 3 |  | Live forecasts of reposts inside their 80% range | 79% | 69% – 87% | 76 | measured |
| 3 |  | Live forecasts of views inside their 80% range | 76% | 66% – 84% | 76 | measured |
| 3 |  | Live forecasts of xscore inside their 80% range | 80% | 70% – 88% | 76 | measured |
| data | itsalexvacca | Share of replies + quotes X lets us collect | 55% | 52% – 58% | 1277 | measured |
| data | MichLieben | Share of replies + quotes X lets us collect | 51% | 48% – 54% | 1097 | measured |
| data | nifinet | Share of replies + quotes X lets us collect | 24% | 22% – 27% | 966 | measured |
| data | VukConfidential | Share of replies + quotes X lets us collect | 64% | 57% – 70% | 203 | measured |
| data | nikolak47 | Share of replies + quotes X lets us collect | 59% | 56% – 62% | 910 | measured |
| data | Vick_Mucunski | Share of replies + quotes X lets us collect | 42% | 28% – 57% | 43 | measured |
| data | Kenny_GTM | Share of replies + quotes X lets us collect | 44% | 38% – 51% | 237 | measured |
| data | mailankhong | Share of replies + quotes X lets us collect | 18% | 10% – 30% | 51 | measured |
| data | pierreherubel | Share of replies + quotes X lets us collect | 56% | 49% – 62% | 217 | measured |
| data | nateandorsky | Share of replies + quotes X lets us collect | 80% | 38% – 96% | 5 | measured |
| data | imrenat | Share of replies + quotes X lets us collect | 100% | 21% – 100% | 1 | measured |
