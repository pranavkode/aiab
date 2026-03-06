"""
Send generated outreach emails to leads. Marks leads as contacted and sets contacted_at.
Uses a delay between emails (~80/hour) to reduce spam risk.
"""
from dotenv import load_dotenv
load_dotenv()

import os
import time
import smtplib
import pandas as pd
from email.mime.text import MIMEText
from datetime import datetime, timezone

EMAIL = os.getenv("OUTREACH_EMAIL")
PASSWORD = os.getenv("OUTREACH_PASSWORD")
# Cap emails per run (default 10). Set MAX_EMAILS_PER_RUN in .env to change; 0 = no limit.
_max = os.getenv("MAX_EMAILS_PER_RUN", "10").strip()
MAX_EMAILS_PER_RUN = int(_max) if _max and _max != "0" else None

if not EMAIL or not PASSWORD:
    print("Set OUTREACH_EMAIL and OUTREACH_PASSWORD in .env (use Gmail App Password if 2FA is on).")
    exit(1)

leads_file = "leads.csv"
leads = pd.read_csv(leads_file)

for col in ("contacted", "replied", "converted"):
    if col not in leads.columns:
        leads[col] = 0
if "contacted_at" not in leads.columns:
    leads["contacted_at"] = ""

leads["contacted"] = leads["contacted"].fillna(0).astype(int)

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login(EMAIL, PASSWORD)

sent = 0
for index, row in leads.iterrows():
    if MAX_EMAILS_PER_RUN is not None and sent >= MAX_EMAILS_PER_RUN:
        print(f"(Stopping at {MAX_EMAILS_PER_RUN} emails this run. Set MAX_EMAILS_PER_RUN in .env to change.)")
        break
    business = row["business_name"]
    to_email = row["email"]

    if pd.isna(to_email) or str(to_email).strip() == "":
        continue
    if row["contacted"]:
        continue

    filename = f"email_{business.replace(' ', '_')}.txt"
    if not os.path.exists(filename):
        continue

    with open(filename) as f:
        message = f.read()

    msg = MIMEText(message)
    msg["Subject"] = f"Quick idea for {business}'s site"
    msg["From"] = EMAIL
    msg["To"] = to_email

    try:
        server.sendmail(EMAIL, to_email, msg.as_string())
        leads.at[index, "contacted"] = 1
        leads.at[index, "contacted_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sent += 1
        print(f"Sent to {business} ({to_email})")
    except Exception as e:
        print(f"Failed {business}: {e}")

    # Safer rate: ~80 emails per hour to avoid blocks
    time.sleep(45)

leads.to_csv(leads_file, index=False)
server.quit()

print(f"Done. Sent {sent} emails. Contacted leads marked in {leads_file}.")
