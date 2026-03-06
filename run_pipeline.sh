#!/usr/bin/env bash
# Full pipeline: find leads → extract emails → generate demos → push live → outreach → send.
set -e
cd "$(dirname "$0")"

python3 lead_finder.py
python3 email_extractor.py
python3 website_copy_generator.py

# Deploy demos to GitHub Pages (commit on main, push main and gh-pages)
git add demos/
if ! git diff --cached --quiet; then
  git commit -m "Add new demos"
  git push origin main
  git push origin main:gh-pages
fi

python3 outreach_generator.py
python3 email_sender.py
python3 follow_up_sender.py
