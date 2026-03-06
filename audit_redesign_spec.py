"""
Single LLM call returns structured JSON: audit (problems + money_impact) + redesign (headline, services, trust_bar, testimonial, cta).
We own the HTML template; the model only fills content. Render → Playwright screenshot = agency-level after.png.
"""
from dotenv import load_dotenv
load_dotenv()

import json
import re
import os
import requests
from urllib.parse import urljoin
from openai import OpenAI

client = OpenAI()


def _normalize_hex(s):
    if not s:
        return ""
    s = str(s).strip().lower()
    m = re.search(r"#([0-9a-f]{3}|[0-9a-f]{6})\b", s)
    if m:
        h = m.group(1)
        return "#" + (h * 2 if len(h) == 3 else h)
    m = re.search(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", s)
    if m:
        return "#{:02x}{:02x}{:02x}".format(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return ""


def _extract_branding(soup, base_url):
    out = {"logo_url": "", "primary_color": "", "secondary_color": "", "font": ""}
    try:
        base = base_url.rstrip("/") or ""
        if not base.startswith("http"):
            return out
        for sel in ["header img", "nav img", "img[class*='logo']", "img[id*='logo']", "img[alt*='logo']"]:
            img = soup.select_one(sel)
            if img and img.get("src"):
                src = img["src"].strip()
                if not src.startswith("data:") and len(src) > 2:
                    out["logo_url"] = urljoin(base + "/", src)
                    return out
        for tag_name in ["header", "nav"]:
            h = soup.find(tag_name)
            if h:
                img = h.find("img")
                if img and img.get("src"):
                    out["logo_url"] = urljoin(base + "/", img["src"].strip())
                    break
        theme = soup.find("meta", attrs={"name": "theme-color"})
        if theme and theme.get("content"):
            out["primary_color"] = _normalize_hex(theme["content"])
        colors_found = []
        for tag in soup.find_all(attrs={"style": True}, limit=15):
            style = (tag.get("style") or "").lower()
            for part in re.findall(r"(?:background(?:-color)?|color)\s*:\s*[^;]+", style):
                c = _normalize_hex(part)
                if c and c not in colors_found:
                    colors_found.append(c)
        if not out["primary_color"] and colors_found:
            out["primary_color"] = colors_found[0]
        if len(colors_found) > 1:
            out["secondary_color"] = colors_found[1]
        body = soup.find("body")
        if body and body.get("style"):
            m = re.search(r"font-family\s*:\s*([^;]+)", body["style"], re.I)
            if m:
                out["font"] = m.group(1).strip().strip('"\'')[:80]
        for st in soup.find_all("style", limit=2):
            m = re.search(r"font-family\s*:\s*([^;}]+)", st.string or "", re.I)
            if m and not out["font"]:
                out["font"] = m.group(1).strip().strip('"\'')[:80]
                break
    except Exception:
        pass
    return out


def scrape_site_content(url: str) -> dict:
    """Extract headline, services, CTA, body text, phone, etc. and pre-compute audit signals for the LLM."""
    out = {
        "url": url,
        "headline": "",
        "subheadline": "",
        "services": [],
        "cta_text": "",
        "body_text": "",
        "phone": "",
        "address": "",
        "has_viewport": False,
        "word_count": 0,
        "signals": {},
        "branding": {},
    }
    if not url or not str(url).strip().startswith("http"):
        return out
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        text = r.text
        first_chars = text[:3500]  # "above the fold" heuristic
        body_text_only = ""
        soup = __import__("bs4").BeautifulSoup(text, "html.parser")
        out["has_viewport"] = soup.find("meta", attrs={"name": "viewport"}) is not None
        h1 = soup.find("h1")
        out["headline"] = (h1.get_text().strip()[:200] if h1 else "") or (soup.title.string[:200] if soup.title else "")
        h2 = soup.find("h2")
        if h2:
            out["subheadline"] = h2.get_text().strip()[:200]
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content") and not out["subheadline"]:
            out["subheadline"] = meta_desc["content"][:200]
        for li in soup.find_all(["li", "a"])[:30]:
            t = li.get_text().strip()
            if t and 10 < len(t) < 80 and not t.startswith("http"):
                out["services"].append(t)
        out["services"] = list(dict.fromkeys(out["services"]))[:10]
        cta_words = ["contact", "quote", "call", "book", "schedule", "get started", "request", "free", "estimate"]
        out["cta_text"] = ""
        for tag in soup.find_all(["button", "a"]):
            t = tag.get_text().strip().lower()
            if any(w in t for w in cta_words) and len(t) < 60:
                out["cta_text"] = tag.get_text().strip()[:100]
                break
        body = soup.find("body")
        if body:
            body_text_only = body.get_text(separator=" ", strip=True)[:3000]
            out["body_text"] = body_text_only
        out["word_count"] = len(out["body_text"].split())
        phones = re.findall(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        if phones:
            out["phone"] = phones[0].strip()
        addr = re.search(r"\d+[^<>]+,?\s*[A-Za-z\s]+,?\s*[A-Z]{2}\s+\d{5}(-\d{4})?", text)
        if addr:
            out["address"] = addr.group(0).strip()[:80]

        # Pre-compute signals for more accurate LLM audit
        first_lower = first_chars.lower()
        body_lower = body_text_only.lower()
        out["signals"] = {
            "no_viewport": not out["has_viewport"],
            "no_cta_above_fold": not any(w in first_lower for w in cta_words),
            "no_phone_in_header": not (out["phone"] and out["phone"] in first_chars),
            "no_reviews_section": not any(w in body_lower for w in ["review", "testimonial", "rating", "stars", "google"]),
            "slow_load": r.elapsed.total_seconds() > 3.0 if hasattr(r, "elapsed") else False,
        }
        out["branding"] = _extract_branding(soup, url)
    except Exception:
        pass
    return out


def run_audit_and_redesign_spec(business: str, industry: str, city: str, site_content: dict) -> dict:
    """LLM returns one JSON: audit (problems, money_impact) + redesign. Uses pre-computed signals for accurate audit."""
    headline = site_content.get("headline") or "(none found)"
    subheadline = site_content.get("subheadline") or "(none)"
    cta = site_content.get("cta_text") or "(none found)"
    services_preview = ", ".join(site_content.get("services", [])[:5]) or "(none listed)"
    word_count = site_content.get("word_count", 0)
    has_viewport = site_content.get("has_viewport", False)
    signals = site_content.get("signals") or {}

    sig_lines = []
    if signals.get("no_viewport"):
        sig_lines.append("no viewport meta (mobile may be broken)")
    if signals.get("no_cta_above_fold"):
        sig_lines.append("no CTA above the fold")
    if signals.get("no_phone_in_header"):
        sig_lines.append("phone not visible in header/fold")
    if signals.get("no_reviews_section"):
        sig_lines.append("no reviews/testimonials section")
    if signals.get("slow_load"):
        sig_lines.append("slow load (>3s)")
    signals_text = "; ".join(sig_lines) if sig_lines else "none computed"

    prompt = f"""You are a conversion-focused web strategist. Analyze this {industry} business website and produce two things: (1) a short audit, (2) improved homepage copy for a redesign.

Business: {business}. Location: {city or "N/A"}.

Current site summary:
- Headline: {headline}
- Subheadline: {subheadline}
- CTA / primary button: {cta}
- Services/offerings: {services_preview}
- Body length: ~{word_count} words. Mobile viewport: {"yes" if has_viewport else "no"}

Pre-computed signals (use these to make the audit accurate): {signals_text}

Return valid JSON only. No markdown, no explanation. Use this exact structure:

{{
  "audit": {{
    "problems": [
      "Short problem 1 (e.g. Weak headline above the fold)",
      "Short problem 2 (e.g. CTA buried below the fold)",
      "Short problem 3 (e.g. Too much dense text / mobile layout feels heavy)"
    ],
    "money_impact": [
      "One line impact (e.g. Lower conversion on first visit)",
      "One line impact",
      "One line impact (e.g. Fewer quote requests)"
    ]
  }},
  "redesign": {{
    "headline": "One strong headline for the hero (e.g. Fairfax Roofing Experts You Can Trust)",
    "subheadline": "One line under the headline (e.g. Fast estimates, clean installs, reliable repairs)",
    "cta": "Single CTA button text (e.g. Get a Free Estimate)",
    "services": [
      {{ "title": "Service name", "text": "One line description." }},
      {{ "title": "Service name", "text": "One line description." }},
      {{ "title": "Service name", "text": "One line description." }}
    ],
    "trust_bar": ["Licensed & Insured", "5-Star Service", "Free Estimates"],
    "testimonial": "One short quote (e.g. Professional team, fair pricing, great communication.)",
    "google_reviews": {{
      "rating": "4.9",
      "count": "87",
      "reviews": [
        {{ "quote": "Fast response and honest pricing.", "author": "Michael G.", "location": "Fairfax" }},
        {{ "quote": "Roof replaced in one day.", "author": "Sarah T.", "location": "Chantilly" }}
      ]
    }}
  }}
}}

Generate 3-6 services (for roofing use: Residential Roofing, Commercial Roofing, Roof Repair, Storm Damage, etc.). trust_bar should be contractor-style: e.g. "Licensed & Insured", "Free Same-Day Estimates", "15+ Years Experience". google_reviews: use local {city} area names for author locations (e.g. Fairfax, Chantilly, Vienna). Generate 2-3 short realistic contractor reviews. Keep problems and money_impact as short bullets. Base audit problems on the pre-computed signals when they are present. Write each problem with one specific reference when possible: mention the business name (e.g. "headline doesn't explain what makes {business} different") or a specific element (e.g. "the free estimate CTA is below the fold", "phone number isn't visible on mobile"). For the hero, use a problem→solution pattern when it fits: headline as question or pain point (e.g. 'Roof Problems in Fairfax?'), subheadline as the solution (e.g. 'Fast repairs, honest inspections, and durable installations trusted by homeowners across Fairfax County.')."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    if "```" in raw:
        raw = re.sub(r"^.*?```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```.*", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "audit": {"problems": ["Conversion issues on current site"], "money_impact": ["Fewer leads", "Lower trust", "Missed quotes"]},
            "redesign": {
                "headline": business,
                "subheadline": f"Quality {industry} in {city}" if city else "",
                "cta": "Get a Free Quote",
                "services": [{"title": "Services", "text": "Contact us to learn more."}],
                "trust_bar": ["Professional", "Reliable", "Local"],
                "testimonial": "Great service and communication.",
                "google_reviews": {"rating": "4.9", "count": "87", "reviews": [{"quote": "Professional and on time.", "author": "Local Customer", "location": city or "VA"}, {"quote": "Great quality work.", "author": "Satisfied Client", "location": city or "VA"}]},
            },
        }


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def format_phone(raw: str) -> str:
    """Format phone to (XXX) XXX-XXXX for display."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
    if len(digits) == 11 and digits[0] == "1":
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:11]}"
    if len(digits) >= 10:
        return f"({digits[-10:-7]}) {digits[-7:-4]}-{digits[-4:]}"
    return raw


# Fallback Unsplash image URLs when no API key (public URLs for hero + cards + projects)
_UNSPLASH_FALLBACKS = {
    "roofing": [
        "https://images.unsplash.com/photo-1597004454259-7c0e90c82a17?w=1200",
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800",
        "https://images.unsplash.com/photo-1581093588401-12c0a4fbe1c7?w=800",
        "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=800",
        "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800",
        "https://images.unsplash.com/photo-1600585154526-990dbe4eb0f3?w=800",
        "https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?w=800",
        "https://images.unsplash.com/photo-1600573472592-401b489a3cdc?w=800",
    ],
    "dental": [
        "https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=1200",
        "https://images.unsplash.com/photo-1606811841689-23dfddce3e95?w=800",
        "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=800",
        "https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=800",
        "https://images.unsplash.com/photo-1606811841689-23dfddce3e95?w=800",
        "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=800",
        "https://images.unsplash.com/photo-1606811841689-23dfddce3e95?w=800",
        "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=800",
    ],
    "dentist": None,  # use dental
    "landscaping": [
        "https://images.unsplash.com/photo-1558904541-efa843a96f01?w=1200",
        "https://images.unsplash.com/photo-1585320806297-9794b3e4eeae?w=800",
        "https://images.unsplash.com/photo-1598902108850-9b2c78b6b8b8?w=800",
        "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=800",
        "https://images.unsplash.com/photo-1585320806297-9794b3e4eeae?w=800",
        "https://images.unsplash.com/photo-1598902108850-9b2c78b6b8b8?w=800",
        "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=800",
        "https://images.unsplash.com/photo-1585320806297-9794b3e4eeae?w=800",
    ],
}


# Industry-specific Unsplash search queries (contractor/real-work photos)
_UNSPLASH_QUERIES = {
    "roofing": "roof replacement",
    "dentist": "dental office",
    "dental": "dental office",
    "landscaping": "landscaping garden",
}


def fetch_unsplash_urls(industry: str, count: int = 8) -> list:
    """Return image URLs for hero + cards + project gallery. Uses API if UNSPLASH_ACCESS_KEY set, else hardcoded fallbacks."""
    industry_key = (industry or "").strip().lower() or "roofing"
    fallback = _UNSPLASH_FALLBACKS.get(industry_key) or _UNSPLASH_FALLBACKS.get("dental") or _UNSPLASH_FALLBACKS["roofing"]
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    if not key:
        return (fallback * 2)[:count]
    query = _UNSPLASH_QUERIES.get(industry_key) or _UNSPLASH_QUERIES.get("roofing") or "roof replacement"
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": count, "client_id": key},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        urls = [r.get("urls", {}).get("regular") or r.get("urls", {}).get("small") for r in results if r.get("urls")]
        return urls if urls else (fallback * 2)[:count]
    except Exception:
        return (fallback * 2)[:count]


def render_redesign_html(spec: dict, business: str, scraped: dict, hero_image_url: str = "", card_image_urls: list = None, project_image_urls: list = None, city: str = "", industry: str = "", branding: dict = None) -> str:
    """Fill the strong template; apply scraped branding (logo, colors, font). Section 'Recent [Industry] Jobs in [City]' with captions."""
    r = spec.get("redesign", {})
    headline = _esc(r.get("headline", business))
    subheadline = _esc(r.get("subheadline", ""))
    cta = _esc(r.get("cta", "Get a Free Quote"))
    services = r.get("services", [])
    trust_bar = r.get("trust_bar", [])
    testimonial = _esc(r.get("testimonial", ""))
    card_image_urls = card_image_urls or []
    project_image_urls = project_image_urls or []

    branding = branding or {}
    primary = (branding.get("primary_color") or "").strip() or "#1a73e8"
    secondary = (branding.get("secondary_color") or "").strip() or "#0d47a1"
    font_css = ""
    if (branding.get("font") or "").strip():
        font_css = f"font-family:{_esc(branding['font'].strip())}, 'Segoe UI', system-ui, sans-serif;"
    else:
        font_css = "font-family:'Segoe UI',system-ui,-apple-system,sans-serif;"
    logo_url = (branding.get("logo_url") or "").strip()
    nav_brand_html = f'<img src="{_esc(logo_url)}" alt="">' if logo_url else _esc(business)
    industry_label = (industry or "service").replace("_", " ").title()
    city_label = city or "your area"

    contact_html = ""
    phone_display = format_phone(scraped.get("phone", "") or "")
    if phone_display:
        contact_html += f'<p><strong>Phone</strong> {_esc(phone_display)}</p>'
    if scraped.get("address"):
        contact_html += f'<p><strong>Address</strong> {_esc(scraped["address"])}</p>'
    if contact_html:
        contact_html = f'<div class="contact-block">{contact_html}</div>'

    project_grid_html = ""
    state_abbr = "VA" if city else "VA"
    job_captions = [f"{_esc(s.get('title', 'Project'))} – {_esc(city)} {state_abbr}" for s in services[:3]]
    while len(job_captions) < 3:
        job_captions.append(f"Project – {_esc(city)} {state_abbr}")
    for i in range(3):
        img_url = project_image_urls[i] if i < len(project_image_urls) else None
        cap = _esc(job_captions[i])
        if img_url:
            project_grid_html += f'<div class="project-item"><div class="project-img" style="background-image:url(\'{_esc(img_url)}\');"></div><p class="project-caption">{cap}</p></div>'
        else:
            project_grid_html += f'<div class="project-item"><div class="project-img project-img-placeholder"></div><p class="project-caption">{cap}</p></div>'
    recent_jobs_title = f"Recent {industry_label} Jobs in {_esc(city_label)}" if (industry or city) else "Recent Jobs"

    estimate_bar_html = ""
    if city or industry:
        industry_label = (industry or "service").replace("_", " ").title()
        city_label = city or "your area"
        estimate_bar_html = f'<div class="estimate-bar"><p class="estimate-bar-text">Looking for {_esc(industry_label)} in {_esc(city_label)}?</p><a class="estimate-bar-btn" href="#contact">{cta}</a></div>'
    else:
        estimate_bar_html = f'<div class="estimate-bar"><p class="estimate-bar-text">Looking for a free estimate?</p><a class="estimate-bar-btn" href="#contact">{cta}</a></div>'

    cards_html = ""
    for i, s in enumerate(services[:6]):
        t = _esc(s.get("title", ""))
        d = _esc(s.get("text", ""))
        img = card_image_urls[i] if i < len(card_image_urls) else ""
        img_tag = f'<div class="card-img" style="background-image:url(\'{_esc(img)}\');"></div>' if img else '<div class="card-img card-img-placeholder"></div>'
        cards_html += f'<div class="card">{img_tag}<div class="card-body"><h3>{t}</h3><p>{d}</p></div></div>'

    trust_html = ""
    for b in trust_bar[:4]:
        trust_html += f'<span class="badge">{_esc(b)}</span>'

    trust_rating_line = f'<p class="trust-rating"><span>★★★★★</span> 4.9 Rated {_esc(industry_label)} in {_esc(city_label)}</p>' if (industry or city) else ""

    gr = r.get("google_reviews") or {}
    gr_rating = gr.get("rating") or "4.9"
    gr_count = gr.get("count") or "87"
    gr_list = gr.get("reviews") or []
    google_reviews_html = f'<h2 class="section-title"><span class="stars">★★★★★</span> {gr_rating} from {gr_count} Google Reviews</h2><div class="google-reviews">'
    for rev in gr_list[:3]:
        q = _esc(rev.get("quote", ""))
        a = _esc(rev.get("author", ""))
        loc = _esc(rev.get("location", ""))
        google_reviews_html += f'<div class="google-review-card"><p class="review-quote">"{q}"</p><p class="review-author">— {a}{", " + loc if loc else ""}</p></div>'
    if not gr_list:
        google_reviews_html += f'<div class="google-review-card"><p class="review-quote">"Fast response and honest pricing."</p><p class="review-author">— Michael G., {_esc(city_label)}</p></div><div class="google-review-card"><p class="review-quote">"Professional work, would recommend."</p><p class="review-author">— Sarah T., {_esc(city_label)}</p></div>'
    google_reviews_html += "</div>"

    hero_actions_html = ""
    if phone_display:
        hero_actions_html = f'<a class="call-now" href="tel:{re.sub(r"[^0-9+]", "", phone_display)}">Call Now {_esc(phone_display)}</a>'
    hero_actions_html += f'<a class="cta" href="#contact">{cta}</a>'

    nav_phone_html = f'<a class="nav-phone" href="tel:{re.sub(r"[^0-9+]", "", phone_display)}">{_esc(phone_display)}</a>' if phone_display else ""

    hero_style = ""
    if hero_image_url:
        hero_style = f"background: linear-gradient(rgba(26,115,232,.85), rgba(13,71,161,.75)), url('{_esc(hero_image_url)}') center/cover no-repeat;"
    else:
        hero_style = f"background: linear-gradient(135deg,{primary} 0%,{secondary} 100%);"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(business)}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;{font_css}color:#1a1a1a;line-height:1.5}}
.nav{{position:sticky;top:0;z-index:100;background:rgba(255,255,255,.98);border-bottom:1px solid #eee;padding:16px 24px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.nav-brand{{font-weight:700;font-size:1.25rem;color:{primary}}}
.nav-brand img{{max-height:40px;width:auto;display:block;vertical-align:middle}}
.nav-phone{{font-weight:600;color:{primary};text-decoration:none;font-size:1rem}}
.nav-phone:hover{{text-decoration:underline}}
.nav-links{{display:flex;gap:24px;align-items:center}}
.nav-links a{{color:#444;text-decoration:none;font-size:0.95rem}}
.hero{{color:#fff;padding:80px 24px;text-align:center;min-height:420px;display:flex;flex-direction:column;justify-content:center;align-items:center}}
.hero h1{{margin:0 0 12px;font-size:2.5rem;font-weight:700;letter-spacing:-0.02em;text-shadow:0 1px 3px rgba(0,0,0,.2)}}
.hero .sub{{margin:0 0 24px;font-size:1.2rem;opacity:.98;max-width:560px;margin-left:auto;margin-right:auto;text-shadow:0 1px 2px rgba(0,0,0,.15)}}
.hero-actions{{display:flex;flex-wrap:wrap;gap:16px;justify-content:center;align-items:center}}
.hero .cta{{display:inline-block;padding:16px 36px;background:{primary};color:#fff;font-weight:700;text-decoration:none;border-radius:8px;font-size:1.1rem;box-shadow:0 4px 14px rgba(0,0,0,.25)}}
.hero .cta:hover{{background:#ffca28;transform:translateY(-1px)}}
.hero .call-now{{display:inline-block;padding:16px 28px;background:rgba(255,255,255,.2);color:#fff;font-weight:600;text-decoration:none;border-radius:8px;font-size:1.05rem;border:2px solid #fff}}
.hero .call-now:hover{{background:rgba(255,255,255,.3)}}
.trust{{background:#fff;padding:20px 24px;border-bottom:1px solid #eee;text-align:center}}
.trust-rating{{font-size:1.1rem;font-weight:600;color:#1a1a1a;margin:0 0 12px;letter-spacing:.02em}}
.trust-rating span{{color:#f5a623}}
.trust .badges{{display:flex;flex-wrap:wrap;justify-content:center;gap:12px}}
.trust .badge{{display:inline-block;padding:10px 20px;background:#f0f7ff;border:1px solid {primary};border-radius:24px;font-size:0.9rem;color:{primary};font-weight:500}}
.container{{max-width:1000px;margin:0 auto;padding:48px 24px}}
.section-title{{font-size:1.5rem;color:{primary};margin:0 0 24px;font-weight:600}}
.services{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:24px;margin-bottom:48px}}
.card{{background:#fff;border:1px solid #eee;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.06)}}
.card-img{{height:140px;background:#e3f2fd center/cover no-repeat}}
.card-img-placeholder{{background:#e3f2fd!important}}
.card-body{{padding:24px}}
.card h3{{margin:0 0 8px;font-size:1.1rem;color:{primary}}}
.card p{{margin:0;font-size:0.95rem;color:#555}}
.projects{{margin-bottom:48px}}
.project-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:16px}}
.project-item{{text-align:center}}
.project-img{{height:180px;background:#e3f2fd center/cover no-repeat;border-radius:12px}}
.project-img-placeholder{{background:#e3f2fd!important}}
.project-caption{{margin:8px 0 0;font-size:0.9rem;color:#555;font-weight:500}}
.testimonial{{background:#fff;border:2px solid {primary};border-radius:12px;padding:32px;margin-bottom:24px;box-shadow:0 4px 12px rgba(26,115,232,.12)}}
.testimonial p{{margin:0;font-size:1.05rem;color:#333;font-style:italic}}
.google-reviews-section{{margin-bottom:48px}}
.google-reviews{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:20px;margin-top:16px}}
.google-review-card{{background:#f8f9fa;border:1px solid #eee;border-radius:12px;padding:24px;border-left:4px solid {primary}}}
.review-quote{{margin:0 0 12px;font-size:1rem;color:#333;font-style:italic}}
.review-author{{margin:0;font-size:0.9rem;color:#666}}
.google-reviews-section .stars{{color:#f5a623;margin-right:8px}}
.reviews-title{{font-size:1.5rem;color:{primary};margin:0 0 16px;font-weight:600}}
.reviews-title span{{color:#f5a623}}
.estimate-bar{{background:{primary};color:#fff;padding:20px 24px;text-align:center;display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:16px}}
.estimate-bar-text{{margin:0;font-size:1.1rem;font-weight:500}}
.estimate-bar-btn{{display:inline-block;padding:12px 24px;background:{primary};color:#fff;font-weight:700;text-decoration:none;border-radius:8px;font-size:1rem}}
.cta-block{{text-align:center;padding:48px 24px}}
.cta-block .btn{{display:inline-block;padding:18px 40px;background:{primary};color:#fff;font-weight:700;text-decoration:none;border-radius:8px;font-size:1.1rem;box-shadow:0 4px 14px rgba(0,0,0,.15)}}
.cta-block .btn:hover{{background:#ffca28}}
.contact-block{{background:#f8f9fa;padding:20px 24px;border-radius:8px;margin:24px 0}}
.contact-block p{{margin:8px 0}}
footer{{text-align:center;padding:24px;color:#888;font-size:0.9rem;border-top:1px solid #eee}}
</style>
</head>
<body>
<nav class="nav">
  <span class="nav-brand">{nav_brand_html}</span>
  <div class="nav-links">
    <a href="#services">Services</a>
    <a href="#contact">Contact</a>
    {nav_phone_html}
  </div>
</nav>
<section class="hero" style="{hero_style}">
  <h1>{headline}</h1>
  <p class="sub">{subheadline}</p>
  <div class="hero-actions">{hero_actions_html}</div>
</section>
{estimate_bar_html}
<div class="trust">
  {trust_rating_line}
  <div class="badges">{trust_html}</div>
</div>
<div class="container">
  <h2 class="section-title" id="services">Our Services</h2>
  <div class="services">{cards_html}</div>
  <h2 class="section-title">{recent_jobs_title}</h2>
  <div class="project-grid">{project_grid_html}</div>
  {contact_html}
  <h2 class="reviews-title"><span>★★★★★</span> What Our Customers Say</h2>
  <div class="testimonial"><p>"{testimonial}"</p></div>
  <div class="google-reviews-section">{google_reviews_html}</div>
  <div class="cta-block" id="contact">
    <a class="btn" href="#contact">{cta}</a>
  </div>
</div>
<footer>Redesign concept for {_esc(business)}</footer>
</body>
</html>"""
