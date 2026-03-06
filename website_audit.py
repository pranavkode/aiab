"""
Scrape key site content and run LLM conversion audit: problems, UX, missing CTAs, impact on leads.
"""
from dotenv import load_dotenv
load_dotenv()

import re
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

client = OpenAI()


def scrape_site_content(url: str) -> dict:
    """Extract headline, services, CTA, body text, has viewport, etc. for audit."""
    out = {
        "url": url,
        "headline": "",
        "subheadline": "",
        "services": [],
        "cta_text": "",
        "body_text": "",
        "phone": "",
        "has_viewport": False,
        "word_count": 0,
    }
    if not url or not str(url).strip().startswith("http"):
        return out
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        out["has_viewport"] = soup.find("meta", attrs={"name": "viewport"}) is not None
        # Headline: first h1 or title
        h1 = soup.find("h1")
        out["headline"] = (h1.get_text().strip()[:200] if h1 else "") or (soup.title.string[:200] if soup.title else "")
        # Subheadline: first h2 or meta description
        h2 = soup.find("h2")
        if h2:
            out["subheadline"] = h2.get_text().strip()[:200]
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content") and not out["subheadline"]:
            out["subheadline"] = meta_desc["content"][:200]
        # Services: common patterns (list items, nav links)
        for li in soup.find_all(["li", "a"])[:30]:
            t = li.get_text().strip()
            if t and 10 < len(t) < 80 and not t.startswith("http"):
                out["services"].append(t)
        out["services"] = list(dict.fromkeys(out["services"]))[:10]
        # CTA: buttons and links with action words
        cta_words = ["contact", "quote", "call", "book", "schedule", "get started", "request", "free"]
        for tag in soup.find_all(["button", "a"]):
            t = tag.get_text().strip().lower()
            if any(w in t for w in cta_words) and len(t) < 60:
                out["cta_text"] = tag.get_text().strip()[:100]
                break
        # Body text
        body = soup.find("body")
        if body:
            out["body_text"] = body.get_text(separator=" ", strip=True)[:3000]
        out["word_count"] = len(out["body_text"].split())
        # Phone
        phones = re.findall(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", r.text)
        if phones:
            out["phone"] = phones[0].strip()
    except Exception:
        pass
    return out


def run_audit(business: str, industry: str, site_content: dict) -> str:
    """LLM analyzes site and returns 3 conversion problems + how fixing could increase leads."""
    headline = site_content.get("headline") or "(none found)"
    subheadline = site_content.get("subheadline") or "(none)"
    cta = site_content.get("cta_text") or "(none found)"
    services = ", ".join(site_content.get("services", [])[:5]) or "(none listed)"
    word_count = site_content.get("word_count", 0)
    has_viewport = site_content.get("has_viewport", False)

    prompt = f"""Analyze this small business website for {business}, a {industry} company.

Current site summary:
- Headline: {headline}
- Subheadline: {subheadline}
- CTA / primary button: {cta}
- Services/offerings mentioned: {services}
- Body text length: ~{word_count} words
- Mobile viewport meta: {"yes" if has_viewport else "no"}

Identify exactly 3 conversion problems (e.g. no clear CTA above the fold, generic headline, mobile issues, weak value proposition, missing trust signals). For each:
1. State the problem in one short line.
2. In one sentence, explain how fixing it could increase leads or conversions (e.g. "could increase conversions 20-40%").

Keep the reply concise and scannable. Use bullet points. No intro or conclusion—just the 3 problems and impact."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
