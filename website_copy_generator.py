"""
Option 1 style: LLM returns structured JSON (headline, subheadline, services, about, cta);
we fill a modern template so demos feel like a real redesign.
Scrapes: phone, address, city, and optional rating from the business site.
"""
from dotenv import load_dotenv
load_dotenv()

import json
import re
import os
import requests
from openai import OpenAI
import pandas as pd

client = OpenAI()


def scrape_business_info(url):
    """Scrape phone, address, and optional rating from the lead's site so the demo feels real."""
    out = {"phone": "", "address": "", "rating": ""}
    if not url or not str(url).strip().startswith("http"):
        return out
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        text = r.text
        # US-style phone
        phones = re.findall(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        if phones:
            out["phone"] = phones[0].strip()
        # Address with zip
        addr = re.search(r"\d+[^<>]+,?\s*[A-Za-z\s]+,?\s*[A-Z]{2}\s+\d{5}(-\d{4})?", text)
        if addr:
            out["address"] = addr.group(0).strip()[:80]
        # Rating: schema.org aggregateRating or "4.5 stars" / "4.8/5" style
        schema_rating = re.search(r'"ratingValue"\s*:\s*["]?(\d\.\d)["]?', text)
        if schema_rating:
            out["rating"] = schema_rating.group(1)
        else:
            for pat in [r"(\d\.\d)\s*[/]?\s*5\s*(?:stars?|rating)?", r"(\d\.\d)\s*stars?", r"rated\s*(\d\.\d)"]:
                m = re.search(pat, text, re.I)
                if m and 3.0 <= float(m.group(1)) <= 5.0:
                    out["rating"] = m.group(1)
                    break
    except Exception:
        pass
    return out


def generate_demo_for_row(row):
    """Generate structured copy (LLM JSON) + fill modern template. Includes business name, phone, city, services, rating when available."""
    business = row["business_name"]
    industry = row["industry"]
    city = row.get("city", "")
    website = row.get("website", "")

    scraped = scrape_business_info(website) if website else {}
    # Always have city from our data if scrape didn't find address
    display_city = city or (scraped.get("address") and scraped["address"].split(",")[-2].strip() if scraped.get("address") else "")

    prompt = f"""Create homepage content for a {industry} company called {business} in {city or 'the local area'}.

Return valid JSON only, no other text. Use this exact structure:
{{
  "headline": "Short headline for the hero (e.g. 'Modern Dental Care in Chantilly')",
  "subheadline": "One line under the headline (e.g. 'Comfortable, family-focused dentistry')",
  "about": "One short paragraph about the business (2-3 sentences).",
  "services": [
    {{ "title": "Service name", "description": "One line description" }},
    ... (4 to 6 services for this industry)
  ],
  "cta": "Button text (e.g. 'Schedule Your Visit Today' or 'Request a Free Quote')"
}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    if "```" in raw:
        raw = re.sub(r"^.*?```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```.*", "", raw)

    try:
        data = json.loads(raw)
        headline = data.get("headline", business)
        subheadline = data.get("subheadline", f"Quality {industry} in {city}" if city else "")
        about = data.get("about", "")
        services = data.get("services", [])
        cta = data.get("cta", "Request a Quote")
    except (json.JSONDecodeError, TypeError):
        headline = business
        subheadline = f"Quality {industry} in {city}" if city else ""
        about = f"{business} serves {city or 'the area'} with professional {industry} services."
        services = [{"title": "Services", "description": "Contact us to learn more."}]
        cta = "Request a Quote"

    # Normalize services: allow {"title","description"} or plain strings
    cards = []
    for s in services:
        if isinstance(s, dict):
            cards.append({"title": s.get("title", ""), "description": s.get("description", "")})
        else:
            cards.append({"title": str(s), "description": ""})

    # Plain text copy for reference
    copy_lines = [f"{headline}\n{subheadline}\n\nAbout\n{about}\n\nServices"]
    for c in cards:
        copy_lines.append(f"- {c['title']}: {c['description']}" if c["description"] else f"- {c['title']}")
    os.makedirs("demos", exist_ok=True)
    with open(f"site_{business.replace(' ', '_')}.txt", "w") as f:
        f.write("\n".join(copy_lines))

    # Service cards HTML
    cards_html = ""
    for c in cards:
        t = (c["title"] or "").replace("<", "&lt;").replace(">", "&gt;")
        d = (c["description"] or "").replace("<", "&lt;").replace(">", "&gt;")
        cards_html += f'<div class="card"><h3>{t}</h3>'
        if d:
            cards_html += f'<p>{d}</p>'
        cards_html += "</div>"

    # Contact section: phone, city, address, rating — so it feels like "someone redesigned my site"
    contact_parts = []
    if scraped.get("phone"):
        contact_parts.append(f'<p><strong>Phone:</strong> {scraped["phone"]}</p>')
    if display_city:
        contact_parts.append(f'<p><strong>Location:</strong> {display_city}</p>')
    if scraped.get("address"):
        contact_parts.append(f'<p><strong>Address:</strong> {scraped["address"]}</p>')
    if scraped.get("rating"):
        contact_parts.append(f'<p class="rating"><strong>Rating:</strong> {scraped["rating"]} ★</p>')
    contact_html = f'<div class="contact-block">{"".join(contact_parts)}</div>' if contact_parts else ""

    about_escaped = (about or "").replace("<", "&lt;").replace(">", "&gt;")
    headline_escaped = (headline or business).replace("<", "&lt;").replace(">", "&gt;")
    subheadline_escaped = (subheadline or "").replace("<", "&lt;").replace(">", "&gt;")
    cta_escaped = (cta or "Request a Quote").replace("<", "&lt;").replace(">", "&gt;")

    html = f"""<!DOCTYPE html>
<html>
<head>
<title>{business}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font-family:Arial,sans-serif;margin:0;background:#f7f7f7;color:#333;}}
.hero{{background:#1a73e8;color:white;padding:48px 24px;text-align:center;}}
.hero h1{{margin:0 0 8px 0;font-size:2em;}}
.hero .subheadline{{margin:0;opacity:.95;font-size:1.1em;}}
.container{{max-width:1000px;margin:auto;padding:40px;background:white;box-shadow:0 0 20px rgba(0,0,0,.06);}}
.contact-block{{background:#f9f9f9;padding:20px 24px;border-radius:8px;margin:24px 0;}}
.contact-block p{{margin:8px 0;}}
.contact-block p:first-child{{margin-top:0;}}
.contact-block .rating{{color:#d97706;}}
h2{{color:#1a73e8;margin-top:40px;}}
.services{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:20px;margin-top:20px;}}
.card{{border:1px solid #eee;padding:20px;border-radius:8px;background:#fafafa;}}
.card h3{{margin:0 0 8px 0;color:#1a73e8;font-size:1.1em;}}
.card p{{margin:0;font-size:0.95em;color:#555;line-height:1.4;}}
.cta{{text-align:center;margin-top:50px;}}
.cta h2{{margin-bottom:16px;}}
button{{padding:15px 30px;font-size:16px;background:#1a73e8;color:white;border:none;border-radius:6px;cursor:pointer;}}
button:hover{{background:#1557b0;}}
footer{{text-align:center;padding:30px;color:#777;font-size:14px;}}
</style>
</head>
<body>
<section class="hero">
<h1>{headline_escaped}</h1>
<p class="subheadline">{subheadline_escaped}</p>
</section>
<div class="container">
<h2>About Us</h2>
<p>{about_escaped}</p>
{contact_html}
<h2>Our Services</h2>
<div class="services">
{cards_html}
</div>
<div class="cta">
<h2>Get In Touch</h2>
<button>{cta_escaped}</button>
</div>
</div>
<footer>Demo redesign generated for {business}</footer>
</body>
</html>"""

    business_file = business.replace(" ", "_")
    with open(os.path.join("demos", f"{business_file}_demo.html"), "w") as f:
        f.write(html)


if __name__ == "__main__":
    leads = pd.read_csv("leads.csv")
    for index, row in leads.iterrows():
        generate_demo_for_row(row)
    print("Website copy generated.")
