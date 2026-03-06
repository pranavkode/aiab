"""
Queue worker: find rows with status=NEW_LEAD, extract email from website, set status=EMAIL_FOUND.
"""
import re
import requests
import pandas as pd
from email_extractor import EMAIL_PATTERN, pick_best_email

JOBS_FILE = "jobs.csv"

# Reuse email extraction logic; LEADS_FILE not used in worker
jobs = pd.read_csv(JOBS_FILE)
if jobs.empty or "status" not in jobs.columns:
    print("Email worker: no jobs or no status column.")
    exit(0)

new_leads = jobs[jobs["status"] == "NEW_LEAD"]
if new_leads.empty:
    print("Email worker: no NEW_LEAD jobs.")
    exit(0)

filled = 0
for index, row in jobs.iterrows():
    if row["status"] != "NEW_LEAD":
        continue
    url = row.get("website")
    if pd.isna(url) or not str(url).strip().startswith("http"):
        continue
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
    except Exception:
        continue
    emails = EMAIL_PATTERN.findall(r.text)
    best = pick_best_email(emails)
    if best:
        jobs.at[index, "email"] = best
        jobs.at[index, "status"] = "EMAIL_FOUND"
        filled += 1
        print(f"  {row.get('business_name', '?')}: {best}")

jobs.to_csv(JOBS_FILE, index=False)
print(f"Email worker: {filled} jobs → EMAIL_FOUND.")
