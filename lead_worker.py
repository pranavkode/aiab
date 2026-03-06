"""
Queue worker: find businesses with weak sites and add to jobs.csv as NEW_LEAD.
Uses same bad-site scoring as lead_finder (bad_score >= 2).
"""
from googlesearch import search
import requests
from bs4 import BeautifulSoup
import pandas as pd

JOBS_FILE = "jobs.csv"
# Broader queries = more leads (e.g. 10–20×). Add more niches as needed.
industries = [
    "roofing company Fairfax VA",
    "dentist Chantilly VA",
    "landscaping Herndon VA",
    "roofing company Virginia",
    "roofing contractor Virginia",
    "dentist Virginia",
    "landscaping Virginia",
]
OUTDATED_BUILDERS = ("wixsite", "weebly", "yolasite", "godaddy")
CTA_WORDS = ("contact", "quote", "call", "book", "schedule")

try:
    jobs = pd.read_csv(JOBS_FILE)
except FileNotFoundError:
    jobs = pd.DataFrame(columns=[
        "business_name", "website", "email", "industry", "city", "status",
        "contacted", "replied", "converted", "contacted_at", "follow_up_1_sent", "follow_up_2_sent",
    ])

for col in ("status", "contacted", "replied", "converted", "contacted_at", "follow_up_1_sent", "follow_up_2_sent"):
    if col not in jobs.columns:
        jobs[col] = "" if col in ("status", "contacted_at") else 0

existing_urls = set(jobs["website"].dropna().astype(str))
added = 0

for query in industries:
    for url in search(query, num_results=10):
        if url in existing_urls:
            continue
        try:
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            text_lower = soup.get_text().lower()
            url_lower = r.url.lower()
            html_lower = r.text.lower()

            no_ssl = not r.url.startswith("https://")
            no_mobile = soup.find("meta", attrs={"name": "viewport"}) is None
            no_cta = not any(w in text_lower for w in CTA_WORDS)
            outdated_builder = any(b in url_lower or b in html_lower for b in OUTDATED_BUILDERS)
            bad_score = sum([no_ssl, no_mobile, no_cta, outdated_builder])
            if bad_score < 2:
                continue

            title = soup.title.string if soup.title else "Unknown"
            new_job = {
                "business_name": title[:40].strip(),
                "website": r.url,
                "email": "",
                "industry": query.split()[0],
                "city": query.split()[-2],
                "status": "NEW_LEAD",
                "contacted": 0,
                "replied": 0,
                "converted": 0,
                "contacted_at": "",
                "follow_up_1_sent": 0,
                "follow_up_2_sent": 0,
            }
            jobs = pd.concat([jobs, pd.DataFrame([new_job])], ignore_index=True)
            existing_urls.add(r.url)
            added += 1
        except Exception:
            continue

jobs.to_csv(JOBS_FILE, index=False)
print(f"Lead worker: added {added} jobs (NEW_LEAD).")
