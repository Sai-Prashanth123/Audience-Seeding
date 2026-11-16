# Audience Seeding

Finds the real niche audience (Tech / B2B / AI) around Thought Pilot's X clients, so engagement before posting reaches the people X will then show the client's posts to. Data comes from the xplatform scraper API.

Phase 1 is four steps. Each one is run on real data and reviewed before the next starts.

| Step | What it does | Status |
|---|---|---|
| 1A Segmentation | Labels accounts Tech / B2B / AI from bio and posts (model trained on hand labels) | Built: 91.6% in-niche accuracy, 84% main-or-second segment (cross-validated) |
| 1B Seed map | 150 core accounts per niche, then the accounts they reply to, quote and retweet, then a scored seed map of 2,000 accounts per niche. Includes a hold-out test against clients' real engagers. | Built: clients' real engagers found 2.3-3.2× more often than random |
| 1C Content performance | Per-post X-weighted score vs the account's own baseline, by format, hook, topic, timing; niche share of repliers | Built: totals match xplatform within 0-3.4% |
| 1D Model | LightGBM on post features + X's published rules; time-split backtest vs two baselines; live forward test | Built: within-author Spearman 0.19 vs -0.02 for the best baseline; live test running |

## Proof & trust

Every Phase 1 claim is published with its evidence (`seeding proof` → `reports/proof.md`, dashboard tab "Proof & trust"):
value, **95% range**, sample size, method, evidence file. A claim is **proven** only when its whole range clears
the bar; weak or unproven patterns are shown as such and never used in recommendations.

Automatic trust checks (every GitHub run; a failure turns the run red and emails the owner):
1. our totals match xplatform's own client summary (within 5%)
2. no client data leaks into what we measure (1C and tracking use the hold-out seed map)
3. data is fresh (posts < 36h, daily steps < 36h, weekly < 8 days)
4. every claim rests on enough data (weak ones flagged)
5. the 1D backtest only tests on posts after the split date

Bias fixes made on 7 Nov 2026: 1C niche share switched to the hold-out seed map; 1D follower features dropped
(they used today's follower count). Team labels saved from the dashboard (GitHub token in Streamlit secrets)
are trained on weekly, and 1A accuracy is reported separately against them.

## Memory: how Phase 1 learns over time (`seeding memory`, weekly)

Phase 1 learns the way a person does:

- **Learns from others first.** A pattern's effect for a client blends their own posts with all clients'
  (weight n/(n+20); every client counts equally in "all clients"). A quiet client follows the group;
  a busy client follows their own evidence.
- **Remembers.** Each Sunday the 99% range of every pattern is stored in `data/memory/history.csv`.
  Stored weeks are never rewritten.
- **Habits and forgetting.** The lifecycle is new → emerging → **habit** (3 weeks in a row), then
  fading → forgotten. Only habits, plus labelled emerging patterns, reach a plan. Reach-only patterns
  (giveaways) are remembered but never recommended.
- **Surprises.** Posts that do 3× better or worse than predicted are logged. After 10 judged posts,
  a client's draft scores show a corrected estimate. The live test still judges the raw model.
- **Adapting.** If a client's last 4 weeks break from the 12 before on 2+ signals, the client switches
  to fast learning (habits in 2 weeks, quicker forgetting).
- **Keeps only what helps.** The backtest tries weighting recent posts more; it is used only if it
  ranks better. It currently doesn't (0.171 vs 0.174), so it is off.

## Step 3: Predict a post (reach and reactions before it goes out)

Paste a draft and get views, likes, replies, reposts, quotes and bookmarks, each with an **80% range**, compared with the
client's usual post. Use it in the dashboard (**🔮 Predict a post**), in Slack (`@client <draft>` in #predict), or with
`uv run seeding forecast --client itsalexvacca --text "..."`.

| layer | what | status |
|---|---|---|
| Data | hourly live snapshots of client posts and who replied (`seeding snapshot`, `nowcast.yml`) into the git ledger | on |
| L1 forecaster | per-action LightGBM / CatBoost / NGBoost + per-account shrinkage + stacker; usual levels only from posts matured 48h+ | on (members chosen by the backtest) |
| X algorithm | weights and rules read from `xai-org/x-algorithm` @ `30647a8` (`xalgo.py`) | on |
| Honest ranges | conformalized quantile regression on posts the models never trained on; adaptive conformal for drift | on |
| Nowcast | after posting: growth offsets (Szabo & Huberman 2010) + Bayesian fusion with the pre-post forecast | collecting until 200 posts have early + final snapshots |
| Colab | fine-tuned text model on a free GPU (`notebooks/colab_train.ipynb`, `seeding export-training`) | optional; judged like any member |
| Claude layers | content grader, in-context forecaster, real-person audience panel (`forecast/llm.py`) | **off** (`forecast.llm_enabled: false`): API cost |

**Proof.** The evaluation rules were fixed before any model was trained (`reports/3_protocol.md`): rolling time folds,
typical miss, ranking, range coverage, CRPS, Diebold–Mariano and account-cluster bootstrap. A member is kept only if it
beats the account's usual level significantly (`reports/3_backtest.md`). Every live forecast is frozen in
`data/ledger/predictions.csv` before the post's result exists, and judged at 48h (`reports/3_live.md`). The ledger lives
in git because the pipeline database's Actions cache can roll back.

```bash
uv run seeding forecast-backtest     # every member, keep/drop, report, choose what to serve (slow: hours)
uv run seeding forecast-train        # fit + calibrate the served members on the newest posts (weekly job)
uv run seeding forecast-live         # freeze forecasts for new client posts, judge 48h-old ones (live job)
uv run seeding nowcast-report        # after-posting accuracy by post age, once snapshots accumulate
```

## Phase 2 (started 7 Nov 2026)

Turns the seed maps into daily work, and measures it against a comparison group.

| Feature | What it does | Status |
|---|---|---|
| 2A Engage today | Each morning: about 20 fresh, on-topic posts per pilot client from people in their seed map, ranked by who × freshness × openness × topic fit. Each post goes to one client only (no pod pattern). The team writes every reply by hand. | Running |
| 2B Tracking | Treatment (Alex, Kenny, Nikola) vs control (Michel, Mai-Lan, Vick): niche share of engagers (hold-out seed map), reply-back within 14 days, replies by target type. Difference-in-differences. | Running; judged after about 4 weeks |
| 2C-2E | Content recommendations, growth dashboard, lead identification | Planned after 2A/2B checks |

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync --extra embed --extra model   # embed: 1A/1C/1D text features; model: 1D
echo XPLATFORM_API_KEY=... > .env
```

## Pipeline

```bash
uv run seeding pull-corpus       # export stored tweets (free read)
uv run seeding pull-profiles     # export stored profiles with bios (free read)
uv run seeding edges             # who replies to, quotes and retweets whom
uv run seeding segments          # 1A: train, measure, label accounts, write review sample
uv run seeding core              # 1B: pick core accounts per niche
uv run seeding collect-core      # 1B: scrape core timelines (SPENDS X QUOTA)
uv run seeding seeds             # 1B: seed maps + hold-out test
uv run seeding content           # 1C: what worked per pilot client
uv run seeding memory            # weekly: store patterns, update habits / fading / forgotten
uv run seeding backtest          # 1D: backtest vs baselines, then train the final model
uv run seeding predict --client itsalexvacca --text "..." [--when 2026-11-08T14:00]
uv run seeding live              # 1D: score new pilot posts early (run every few hours), check after 48h
uv run seeding engage            # 2A: scrape watched seeds + clients (SPENDS X QUOTA), build today's lists
uv run seeding engage --no-scrape  # 2A: rebuild lists from stored posts only
uv run seeding track             # 2B: treatment vs control tracking (free reads)
uv run seeding proof             # 95% ranges + trust checks (--gate: exit 1 on a failed check)
uv run seeding export-dashboard  # small results snapshot for the deployed app
uv run pytest
```

## Dashboard

```bash
uv run streamlit run app/dashboard.py
```

The dashboard reads `data/seeding.duckdb`, which is not in git. Set `SEEDING_DB` to point it at another file.

## Layout

- `config/segments.yaml`: segments, exclusions, client to segment map, seed weights
- `src/seeding/`: pipeline code. `xp.py` is the API client; `segments.py` is 1A; `seedmap.py` and `holdout.py` are 1B
- `data/labels/`: hand labels used to train and measure 1A
- `reports/`: outputs reviewed at each gate

## Scheduled jobs (GitHub Actions)

The pipeline runs on GitHub, not on a PC. Each run restores the database from the Actions cache
(or rebuilds it with `seeding bootstrap`), does its work, saves the cache and publishes
`data/dashboard.duckdb` + `reports/` + `data/model/`, so the deployed Streamlit app updates by itself.

| Workflow | Schedule | X quota |
|---|---|---|
| `daily.yml`: Engage lists (2A) + tracking (2B) | 06:00 IST | ~270 timeline reads (falls back to stored posts if the pool is cooling down) |
| `live.yml`: 1D live forward test | every 4 hours | none |
| `weekly.yml`: segments, seed maps, content, model retrain | Sunday 03:00 IST | none |

- Secret: `XPLATFORM_API_KEY` (repository secret).
- Re-run Daily without spending quota: Actions → Daily → Run workflow → untick "scrape".
- Expected usage is about 1,500 Actions minutes a month (free private-repo allowance: 2,000).
- The old Windows tasks (`AudienceSeeding-Live`, `AudienceSeeding-Engage`, `scripts/*.cmd`) are disabled, not deleted.
  Re-enable with `schtasks /Change /TN <name> /ENABLE` if needed.
