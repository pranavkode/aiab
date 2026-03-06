"""
Extract email addresses from lead websites and update leads.csv.
Runs after lead_finder so new leads with empty email get filled before outreach.
"""
import re
import requests
import pandas as pd

LEADS_FILE = "leads.csv"
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Skip common false positives (images, placeholders, etc.)
SKIP_DOMAINS = {"example.com", "sentry.io", "wixpress.com", "schema.org", "example.org"}
SKIP_LOCALHOST = re.compile(r"@(localhost|0\.0\.0\.0|127\.0\.0\.1)", re.I)

def is_valid_email(addr: str) -> bool:
    addr = addr.lower().strip()
    if SKIP_LOCALHOST.search(addr):
        return False
    domain = addr.split("@")[-1] if "@" in addr else ""
    if domain in SKIP_DOMAINS:
        return False
    if "image" in addr or "png" in addr or "jpg" in addr or "2x" in addr:
        return False
    return True

def pick_best_email(emails: list[str]) -> str | None:
    if not emails:
        return None
    valid = [e for e in emails if is_valid_email(e)]
    if not valid:
        return None
    # Prefer common business addresses
    for prefix in ("info@", "contact@", "sales@", "hello@", "support@"):
        for e in valid:
            if e.lower().startswith(prefix):
                return e
    return valid[0]

leads = pd.read_csv(LEADS_FILE)
extracted = 0

for index, row in leads.iterrows():
    if pd.notna(row.get("email")) and str(row["email"]).strip():
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
        leads.at[index, "email"] = best
        extracted += 1
        print(f"  {row.get('business_name', '?')}: {best}")

leads.to_csv(LEADS_FILE, index=False)
print(f"Email extraction complete. Filled {extracted} leads.")
