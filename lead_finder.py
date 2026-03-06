from googlesearch import search
import requests
from bs4 import BeautifulSoup
import pandas as pd

industries = [
    "roofing company Fairfax VA",
    "dentist Chantilly VA",
    "landscaping Herndon VA",
]

leads_file = "leads.csv"

try:
    leads = pd.read_csv(leads_file)
except FileNotFoundError:
    leads = pd.DataFrame(columns=["business_name", "email", "website", "industry", "city"])

if "contacted" not in leads.columns:
    leads["contacted"] = 0

for query in industries:
    for url in search(query, num_results=10):
        try:
            r = requests.get(url, timeout=5)
            soup = BeautifulSoup(r.text, "html.parser")

            title = soup.title.string if soup.title else "Unknown"

            # Simple "bad site" detection: low word count = weak content
            word_count = len(soup.get_text().split())

            if word_count < 300:
                new_lead = {
                    "business_name": title[:40],
                    "email": "",
                    "website": url,
                    "industry": query.split()[0],
                    "city": query.split()[-2],
                    "contacted": 0,
                }

                leads = pd.concat([leads, pd.DataFrame([new_lead])], ignore_index=True)

        except Exception:
            continue

leads.drop_duplicates(subset=["website"], inplace=True)
leads.to_csv(leads_file, index=False)

print("New leads added.")
