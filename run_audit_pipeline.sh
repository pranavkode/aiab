#!/usr/bin/env bash
# Audit + before/after pipeline: screenshot current site → LLM audit → redesign → screenshot redesign → email with images + Calendly.
# Run after lead_finder + email_extractor. Then run email_sender (attaches before/after PNGs).
set -e
cd "$(dirname "$0")"

# Optional: deploy demos so the live link still works
python3 audit_and_redesign.py

git add demos/ screenshots/ audits/ 2>/dev/null || true
if ! git diff --cached --quiet 2>/dev/null; then
  git commit -m "Add audit demos and screenshots" || true
  git push origin main 2>/dev/null || true
  git push origin main:gh-pages 2>/dev/null || true
fi

python3 email_sender.py
python3 follow_up_sender.py
