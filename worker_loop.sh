#!/usr/bin/env bash
# Continuous worker loop for 24/7 mode (e.g. Mac Mini).
# Runs: find leads → extract emails → generate demos → send outreach, then sleeps 2 minutes.
set -e
cd "$(dirname "$0")"

while true; do
  echo "=== Worker cycle $(date) ==="
  python3 lead_worker.py
  python3 email_worker.py
  python3 demo_worker.py
  git add demos/
  if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "Add new demos" && git push origin main && git push origin main:gh-pages
  fi
  python3 outreach_worker.py
  echo "=== Sleep 120s ==="
  sleep 120
done
