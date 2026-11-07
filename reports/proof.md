# Phase 1 proof · 07 Nov 2026 16:26 UTC

## Trust checks

- ✅ **Our data matches xplatform post by post (same posts; likes/views within 5%)**: 2026-10, UTC days: itsalexvacca 101 posts, MichLieben 93 posts, nifinet 123 posts, VukConfidential 58 posts, nikolak47 165 posts, Vick_Mucunski 48 posts, itsivanfalco 18 posts, Kenny_GTM 21 posts, mailankhong 150 posts, Tycho_luijten 11 posts, thejcron 3 posts, pierreherubel 22 posts, nateandorsky 35 posts, imrenat 1 posts
- ✅ **No client data leaks into what we measure**: hold-out map has no clients; 1C and tracking read the hold-out map
- ⚠️ **Data is fresh (posts < 36h, daily steps < 36h, weekly < 8 days)**: newest post 0h old; engage 5h ago; content 4h ago; segments 4h ago; seeds 4h ago; backtest 3h ago; live 0h ago; memory: no run recorded yet
- ✅ **Every claim rests on enough data (weak ones are flagged, not hidden)**: every published claim has enough data
- ✅ **1D test uses only posts after the split date**: earliest test post 15 Oct 2026 (split 2026-10-15)
- ⚠️ **AI reviewer stays in line with the team (>= 80% agreement)**: only 0 accounts reviewed by both so far; need 30 to judge
- ✅ **Long-term memory is built and stable**: 13 weeks in memory (24 habit, 4 fading, 6 forgotten, 10 emerging, 3 new); no client's situation changed

## Claims with 95% ranges

| step | client | claim | value | 95% range | n | status |
|---|---|---|---:|---|---:|---|
| 1A |  | In-niche vs off-topic accuracy, vs Claude's hand labels | 91% | 88% – 94% | 353 | proven |
| 1A |  | Right niche (main or 2nd), vs Claude's hand labels | 85% | 79% – 90% | 155 | not yet proven above 80% |
| 1A |  | Accuracy vs the team's labels | — | — – — | 0 | waiting for labels |
| 1A |  | Accuracy vs the AI reviewer's labels | — | — – — | 0 | waiting for labels |
| 1A |  | AI reviewer agrees with the team (random audits + disagreements) | — | — – — | 0 | waiting for team reviews |
| 2A |  | Engage-list posts the AI reviewer judges worth replying to | 40% | 12% – 77% | 5 | measured |
| 1B | Kenny_GTM | Seed map finds real engagers vs random accounts (lift) | 2.23x | 0.72x – 3.99x | 31 | not proven |
| 1B | Kenny_GTM | Share of real engagers in the seed map (baseline niche share) | 19% | 9% – 36% | 31 | measured |
| 1B | itsalexvacca | Seed map finds real engagers vs random accounts (lift) | 4.04x | 2.97x – 5.45x | 284 | proven |
| 1B | itsalexvacca | Share of real engagers in the seed map (baseline niche share) | 18% | 14% – 23% | 284 | measured |
| 1B | nikolak47 | Seed map finds real engagers vs random accounts (lift) | 3.24x | 2.62x – 3.92x | 395 | proven |
| 1B | nikolak47 | Share of real engagers in the seed map (baseline niche share) | 24% | 20% – 29% | 395 | measured |
| 1C | Kenny_GTM | format = quote post: vs own usual level | 0.48x | 0.15x – 0.85x | 19 | proven worse |
| 1C | itsalexvacca | hook = giveaway / comment-to-get: vs own usual level | 11.58x | 2.08x – 20.78x | 33 | proven better |
| 1C | itsalexvacca | hook = number / result: vs own usual level | 0.63x | 0.52x – 0.91x | 73 | proven worse |
| 1C | itsalexvacca | topic = ai / services / software: vs own usual level | 1.53x | 1.18x – 2.41x | 50 | proven better |
| 1C | itsalexvacca | topic = gtm / build gtm / gtm playbook: vs own usual level | 1.56x | 1.03x – 2.40x | 48 | proven better |
| 1C | itsalexvacca | length = 100-280: vs own usual level | 0.62x | 0.44x – 0.82x | 64 | proven worse |
| 1C | itsalexvacca | hour_block = 12-17 UTC: vs own usual level | 1.23x | 1.02x – 1.49x | 232 | proven better |
| 1C | itsalexvacca | day_slot = 3rd+: vs own usual level | 0.57x | 0.44x – 0.80x | 88 | proven worse |
| 1C | nikolak47 | format = long-form post: vs own usual level | 1.26x | 1.02x – 1.49x | 98 | proven better |
| 1C | nikolak47 | format = quote post: vs own usual level | 0.54x | 0.41x – 0.98x | 45 | proven worse |
| 1C | nikolak47 | hook = number / result: vs own usual level | 1.19x | 1.00x – 1.78x | 60 | proven better |
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
| 1D |  | Model ranks an account's posts (within-author Spearman) | 0.19 | 0.16 – 0.22 | 510 | measured |
| 1D |  | Model beats the best simple baseline (difference in ranking) | 0.21 | 0.17 – 0.24 | 510 | proven |
| data | itsalexvacca | Share of replies + quotes X lets us collect | 49% | 46% – 52% | 1012 | measured |
| data | MichLieben | Share of replies + quotes X lets us collect | 50% | 46% – 53% | 716 | measured |
| data | nifinet | Share of replies + quotes X lets us collect | 26% | 23% – 29% | 1052 | measured |
| data | VukConfidential | Share of replies + quotes X lets us collect | 32% | 26% – 40% | 173 | measured |
| data | nikolak47 | Share of replies + quotes X lets us collect | 53% | 50% – 56% | 1096 | measured |
| data | Vick_Mucunski | Share of replies + quotes X lets us collect | 30% | 20% – 42% | 61 | measured |
| data | itsivanfalco | Share of replies + quotes X lets us collect | 9% | 2% – 27% | 23 | measured |
| data | Kenny_GTM | Share of replies + quotes X lets us collect | 40% | 30% – 51% | 80 | measured |
| data | mailankhong | Share of replies + quotes X lets us collect | 13% | 7% – 23% | 63 | measured |
| data | Tycho_luijten | Share of replies + quotes X lets us collect | 50% | 24% – 76% | 10 | measured |
| data | thejcron | Share of replies + quotes X lets us collect | 0% | 0% – 28% | 10 | measured |
| data | pierreherubel | Share of replies + quotes X lets us collect | 47% | 39% – 55% | 149 | measured |
| data | nateandorsky | Share of replies + quotes X lets us collect | 44% | 19% – 73% | 9 | measured |
| data | imrenat | Share of replies + quotes X lets us collect | 20% | 4% – 62% | 5 | measured |
