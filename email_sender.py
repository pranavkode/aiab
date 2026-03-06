"""
Send generated outreach emails to leads. Embeds after screenshot as inline image (no attachments) for better deliverability.
Marks leads as contacted and sets contacted_at. Uses a delay between emails (~80/hour).
"""
from dotenv import load_dotenv
load_dotenv()

import os
import time
import smtplib
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime, timezone

EMAIL = os.getenv("OUTREACH_EMAIL")
PASSWORD = os.getenv("OUTREACH_PASSWORD")
_max = os.getenv("MAX_EMAILS_PER_RUN", "10").strip()
MAX_EMAILS_PER_RUN = int(_max) if _max and _max != "0" else None

SCREENSHOTS_DIR = "screenshots"

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
leads["contacted_at"] = leads["contacted_at"].fillna("").astype(str)

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

    slug = business.replace(" ", "_").replace("/", "-")
    filename_email = f"email_{slug}.txt"
    if not os.path.exists(filename_email):
        continue

    with open(filename_email) as f:
        message_body = f.read()

    path_after = os.path.join(SCREENSHOTS_DIR, f"{slug}_after.png")
    has_after = os.path.isfile(path_after)

    if has_after and "[AFTER_IMAGE]" in message_body:
        # Send HTML with inline after image (CID) — no attachments for better deliverability
        msg = MIMEMultipart("related")
        msg["Subject"] = f"Quick idea for {business}'s site"
        msg["From"] = EMAIL
        msg["To"] = to_email
        body_plain = message_body.replace("[AFTER_IMAGE]", "[See redesign screenshot in email.]")
        html_body = message_body.replace("\n", "<br>\n").replace("[AFTER_IMAGE]", '<br><img src="cid:afterimg" alt="Redesign mockup" style="max-width:100%; border-radius:8px;"><br>')
        msg.attach(MIMEText(html_body, "html"))
        with open(path_after, "rb") as fp:
            img = MIMEImage(fp.read(), _subtype="png")
            img.add_header("Content-Disposition", "inline", filename="after.png")
            img.add_header("Content-ID", "<afterimg>")
            msg.attach(img)
    else:
        msg = MIMEText(message_body)
        msg["Subject"] = f"Quick idea for {business}'s site"
        msg["From"] = EMAIL
        msg["To"] = to_email

    try:
        server.sendmail(EMAIL, to_email, msg.as_string())
        leads.at[index, "contacted"] = 1
        leads.at[index, "contacted_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sent += 1
        inline = " (inline after image)" if has_after else ""
        print(f"Sent to {business} ({to_email}){inline}")
    except Exception as e:
        print(f"Failed {business}: {e}")

    time.sleep(45)

leads.to_csv(leads_file, index=False)
server.quit()

print(f"Done. Sent {sent} emails. Contacted leads marked in {leads_file}.")
