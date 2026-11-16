"""Step 3: predict a post's reach and audience reaction on X, and measure how well it predicts.

Layers (see README "Predict a post"):
  ledger    frozen, append-only record of every prediction and every snapshot (git, not the cache)
  collect   live snapshots of client posts at 30m..48h, and who replied (xplatform tweet-detail)
  features  per-action features, only from data before each post
  model     L1 ensemble per X action, with conformal ranges
  evaluate  rolling-origin backtest, CRPS, coverage, Diebold-Mariano, ablations, ceiling
"""
