"""
Send follow-up emails at Day 3 and Day 7 after first contact.
Only for leads where contacted=1, replied=0, and contacted_at is set.
"""
from dotenv import load_dotenv
load_dotenv()

import os
import time
import smtplib
import pandas as pd
from email.mime.text import MIMEText
from datetime import datetime, date

LEADS_FILE = "leads.csv"

FOLLOW_UP_1 = """Just checking if you saw the quick redesign I made for your site.

Happy to send the link again if helpful."""

FOLLOW_UP_2 = """Last note — the demo I put together is still available if you'd like to take a look.

No pressure; happy to help if timing's right."""

EMAIL = os.getenv("OUTREACH_EMAIL")
PASSWORD = os.getenv("OUTREACH_PASSWORD")

if not EMAIL or not PASSWORD:
    print("Set OUTREACH_EMAIL and OUTREACH_PASSWORD in .env")
    exit(1)

leads = pd.read_csv(LEADS_FILE)
for col in ("contacted", "replied", "contacted_at", "follow_up_1_sent", "follow_up_2_sent"):
    if col not in leads.columns:
        leads[col] = 0 if col in ("contacted", "replied", "follow_up_1_sent", "follow_up_2_sent") else ""

today = date.today()
sent_1 = sent_2 = 0

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login(EMAIL, PASSWORD)

for index, row in leads.iterrows():
    if row.get("contacted") != 1 or row.get("replied") == 1:
        continue
    to_email = row.get("email")
    if pd.isna(to_email) or not str(to_email).strip():
        continue
    contacted_at = row.get("contacted_at")
    if pd.isna(contacted_at) or not str(contacted_at).strip():
        continue
    try:
        first_contact = datetime.strptime(str(contacted_at).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        continue
    days = (today - first_contact).days
    business = row.get("business_name", "there")

    # Day 3: first follow-up
    if days >= 3 and row.get("follow_up_1_sent") != 1:
        msg = MIMEText(FOLLOW_UP_1)
        msg["Subject"] = "Re: Quick website idea"
        msg["From"] = EMAIL
        msg["To"] = to_email
        try:
            server.sendmail(EMAIL, to_email, msg.as_string())
            leads.at[index, "follow_up_1_sent"] = 1
            sent_1 += 1
            print(f"  Follow-up 1 → {business}")
        except Exception as e:
            print(f"  Failed {business}: {e}")
        time.sleep(45)

    # Day 7: second follow-up (after first was sent)
    elif days >= 7 and row.get("follow_up_1_sent") == 1 and row.get("follow_up_2_sent") != 1:
        msg = MIMEText(FOLLOW_UP_2)
        msg["Subject"] = "Re: Quick website idea"
        msg["From"] = EMAIL
        msg["To"] = to_email
        try:
            server.sendmail(EMAIL, to_email, msg.as_string())
            leads.at[index, "follow_up_2_sent"] = 1
            sent_2 += 1
            print(f"  Follow-up 2 → {business}")
        except Exception as e:
            print(f"  Failed {business}: {e}")
        time.sleep(45)

leads.to_csv(LEADS_FILE, index=False)
server.quit()
print(f"Follow-ups sent: {sent_1} (Day 3), {sent_2} (Day 7).")
