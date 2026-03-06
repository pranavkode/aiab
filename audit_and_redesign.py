"""
Pipeline: URL → scrape → LLM returns audit + redesign JSON → fill strong template → render locally → screenshot → email.
We own the template; the model only fills content. before.png + after.png + audit.json + email with 3 bullets + Calendly.
"""
from dotenv import load_dotenv
load_dotenv()

import json
import os
import pandas as pd
from audit_redesign_spec import (
    scrape_site_content,
    run_audit_and_redesign_spec,
    render_redesign_html,
    fetch_unsplash_urls,
)
from screenshot_utils import screenshot_url, screenshot_local_html

LEADS_FILE = "leads.csv"
SCREENSHOTS_DIR = "screenshots"
AUDIT_DIR = "audits"
CALENDLY_LINK = os.environ.get("CALENDLY_LINK", "").strip()


def safe_filename(business: str) -> str:
    return business.replace(" ", "_").replace("/", "-")


def run_audit_and_redesign():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(AUDIT_DIR, exist_ok=True)
    os.makedirs("demos", exist_ok=True)
    leads = pd.read_csv(LEADS_FILE)

    for index, row in leads.iterrows():
        business = row["business_name"]
        industry = row.get("industry", "")
        website = row.get("website", "")
        city = row.get("city", "")

        if not website or not str(website).strip().startswith("http"):
            print(f"  Skip {business}: no website")
            continue

        slug = safe_filename(business)
        path_before = os.path.join(SCREENSHOTS_DIR, f"{slug}_before.png")
        path_after = os.path.join(SCREENSHOTS_DIR, f"{slug}_after.png")
        path_audit_json = os.path.join(AUDIT_DIR, f"{slug}_audit.json")
        path_demo_html = os.path.join("demos", f"{slug}_demo.html")
        path_email = f"email_{slug}.txt"

        # 1. Screenshot current site
        print(f"  {business}: screenshot before...")
        screenshot_url(website, path_before)

        # 2. Scrape → single LLM call for audit + redesign spec
        print(f"  {business}: scrape + audit + redesign spec...")
        site_content = scrape_site_content(website)
        spec = run_audit_and_redesign_spec(business, industry, city, site_content)

        with open(path_audit_json, "w") as f:
            json.dump(spec, f, indent=2)

        # 3. Fill template (we own layout) → write HTML (with optional Unsplash hero + cards + project gallery)
        scraped_contact = {"phone": site_content.get("phone", ""), "address": site_content.get("address", "")}
        urls = fetch_unsplash_urls(industry, 8)
        hero_url = urls[0] if urls else ""
        card_urls = urls[1:4] if len(urls) >= 4 else (urls[1:] if len(urls) > 1 else [])
        project_urls = urls[4:7] if len(urls) >= 7 else []
        html = render_redesign_html(
            spec, business, scraped_contact,
            hero_image_url=hero_url,
            card_image_urls=card_urls,
            project_image_urls=project_urls,
            city=city,
            industry=industry,
            branding=site_content.get("branding") or {},
        )
        with open(path_demo_html, "w") as f:
            f.write(html)

        # 4. Screenshot redesign
        print(f"  {business}: screenshot after...")
        screenshot_local_html(path_demo_html, path_after)

        # 5. Email: short body, 3 audit bullets, inline after image, credibility, Calendly
        problems = spec.get("audit", {}).get("problems", [])[:3]
        bullets = "\n".join(f"• {p}" for p in problems) if problems else "• A few things that may be hurting conversions"

        email_body = f"""Subject: quick idea for {business}'s site

Hi {business},

I ran a quick review of your homepage and noticed a few things
that might be costing quote requests:

{bullets}

I mocked up what a cleaner version of your homepage could look like.

[AFTER_IMAGE]

Happy to walk through it if helpful.

"""
        if CALENDLY_LINK:
            email_body += f"Book a quick call: {CALENDLY_LINK}\n\n"
        email_body += "Pranav\nSiteRenovate"

        # Save body only (subject is set in email_sender)
        lines = email_body.strip().split("\n")
        body_lines = [l for l in lines if not l.strip().lower().startswith("subject:")]
        with open(path_email, "w") as f:
            f.write("\n".join(body_lines))

        print(f"  {business}: done (before + after + audit.json + email)")

    print("Audit + redesign complete.")


if __name__ == "__main__":
    run_audit_and_redesign()
