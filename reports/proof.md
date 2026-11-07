# Phase 1 proof · 07 Nov 2026 10:57 UTC

## Trust checks

- ✅ **Totals match xplatform's own client summary (within 5%)**: 2026-10, own posts + quotes: itsalexvacca likes +0.7%, itsalexvacca views +0.2%, Kenny_GTM likes +0.0%, Kenny_GTM views +0.2%, nikolak47 likes +0.4%, nikolak47 views +1.2%
- ✅ **No client data leaks into what we measure**: hold-out map has no clients; 1C and tracking read the hold-out map
- ⚠️ **Data is fresh (posts < 36h, daily steps < 36h, weekly < 8 days)**: newest post 3h old; engage: no run recorded yet; content 0h ago; segments 0h ago; seeds 0h ago; backtest 0h ago; live: no run recorded yet
- ✅ **Every claim rests on enough data (weak ones are flagged, not hidden)**: every published claim has enough data
- ✅ **1D test uses only posts after the split date**: earliest test post 15 Oct 2026 (split 2026-10-15)

## Claims with 95% ranges

| step | client | claim | value | 95% range | n | status |
|---|---|---|---:|---|---:|---|
| 1A |  | In-niche vs off-topic accuracy, vs Claude's hand labels | 92% | 88% – 94% | 368 | proven |
| 1A |  | Right niche (main or 2nd), vs Claude's hand labels | 85% | 79% – 89% | 170 | not yet proven above 80% |
| 1A |  | Accuracy vs the team's labels | — | — – — | 0 | waiting for labels |
| 1B | Kenny_GTM | Seed map finds real engagers vs random accounts (lift) | 2.42x | 0.75x – 4.13x | 31 | not proven |
| 1B | Kenny_GTM | Share of real engagers in the seed map (baseline niche share) | 23% | 11% – 40% | 31 | measured |
| 1B | itsalexvacca | Seed map finds real engagers vs random accounts (lift) | 3.30x | 2.36x – 4.43x | 284 | proven |
| 1B | itsalexvacca | Share of real engagers in the seed map (baseline niche share) | 17% | 13% – 22% | 284 | measured |
| 1B | nikolak47 | Seed map finds real engagers vs random accounts (lift) | 2.64x | 2.12x – 3.20x | 395 | proven |
| 1B | nikolak47 | Share of real engagers in the seed map (baseline niche share) | 23% | 19% – 28% | 395 | measured |
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
| 1D |  | Model ranks an account's posts (within-author Spearman) | 0.17 | 0.15 – 0.20 | 475 | measured |
| 1D |  | Model beats the best simple baseline (difference in ranking) | 0.19 | 0.16 – 0.23 | 475 | proven |
| data | itsalexvacca | Share of replies + quotes X lets us collect | 49% | 46% – 52% | 1012 | measured |
| data | Kenny_GTM | Share of replies + quotes X lets us collect | 42% | 31% – 53% | 77 | measured |
| data | nikolak47 | Share of replies + quotes X lets us collect | 53% | 50% – 56% | 1092 | measured |
