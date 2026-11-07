#!/usr/bin/env bash
# Commit the refreshed dashboard snapshot, reports and model (never code) and push, so the deployed
# Streamlit app updates. Used by the GitHub workflows; safe to run when nothing changed.
set -euo pipefail
label="${1:-pipeline}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -- data/dashboard.duckdb reports data/model
if git diff --cached --quiet; then
  echo "nothing to publish"
  exit 0
fi
git commit -q -m "${label} snapshot $(date -u +%Y-%m-%dT%H:%MZ)"
for i in 1 2 3; do
  git pull -q --rebase origin main && git push -q origin HEAD:main && { echo "published"; exit 0; }
  sleep $((i * 10))
done
echo "push failed after 3 attempts" >&2
exit 1
