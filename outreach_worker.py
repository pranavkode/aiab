"""
Queue worker: process jobs with status=DEMO_GENERATED, generate outreach, send email, set EMAIL_SENT.
"""
from dotenv import load_dotenv
load_dotenv()

import os
import time
import smtplib
import pandas as pd
from email.mime.text import MIMEText
from datetime import datetime, timezone

from outreach_generator import generate_outreach_for_row

JOBS_FILE = "jobs.csv"
EMAIL = os.getenv("OUTREACH_EMAIL")
PASSWORD = os.getenv("OUTREACH_PASSWORD")
_max = os.getenv("MAX_EMAILS_PER_RUN", "10").strip()
MAX_EMAILS_PER_RUN = int(_max) if _max and _max != "0" else None

if not EMAIL or not PASSWORD:
    print("Set OUTREACH_EMAIL and OUTREACH_PASSWORD in .env")
    exit(1)

jobs = pd.read_csv(JOBS_FILE)
if jobs.empty:
    print("Outreach worker: no jobs.")
    exit(0)

todo = jobs[jobs["status"] == "DEMO_GENERATED"]
if todo.empty:
    print("Outreach worker: no DEMO_GENERATED jobs.")
    exit(0)

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login(EMAIL, PASSWORD)

sent = 0
for index, row in jobs.iterrows():
    if MAX_EMAILS_PER_RUN is not None and sent >= MAX_EMAILS_PER_RUN:
        print(f"(Stopping at {MAX_EMAILS_PER_RUN} emails this run.)")
        break
    if row["status"] != "DEMO_GENERATED":
        continue
    to_email = row.get("email")
    if pd.isna(to_email) or not str(to_email).strip():
        continue
    business = row["business_name"]
    try:
        message = generate_outreach_for_row(row, save_to_file=True)
        msg = MIMEText(message)
        msg["Subject"] = f"Quick idea for {row['business_name']}'s site"
        msg["From"] = EMAIL
        msg["To"] = to_email
        server.sendmail(EMAIL, to_email, msg.as_string())
        jobs.at[index, "status"] = "EMAIL_SENT"
        jobs.at[index, "contacted"] = 1
        jobs.at[index, "contacted_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sent += 1
        print(f"  Sent → {business}")
    except Exception as e:
        print(f"  Failed {business}: {e}")
    time.sleep(45)

jobs.to_csv(JOBS_FILE, index=False)
server.quit()
print(f"Outreach worker: sent {sent} emails.")
