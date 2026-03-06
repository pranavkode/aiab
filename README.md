# AI Website Agent

Fully automated outbound pipeline: **find leads → extract emails → generate demos → host → outreach → send → follow up**. Supports both **batch mode** (cron) and **queue mode** (24/7 worker loop).

## Project layout

```
aiab/
├── leads.csv                  # Batch mode: leads + contacted, replied, converted, contacted_at, follow_up_*
├── jobs.csv                  # Queue mode: same fields + status (NEW_LEAD → EMAIL_FOUND → DEMO_GENERATED → EMAIL_SENT)
├── demos/                    # *_demo.html — deployed to GitHub Pages
├── screenshots/              # *_before.png, *_after.png (audit mode)
├── audits/                   # *_audit.txt (LLM conversion audit)
├── lead_finder.py            # Batch: find weak sites (bad_score >= 2), append to leads.csv
├── lead_worker.py            # Queue: find weak sites, append to jobs.csv as NEW_LEAD
├── email_extractor.py        # Batch: fill missing emails from websites
├── email_worker.py          # Queue: NEW_LEAD → extract email → EMAIL_FOUND
├── website_copy_generator.py # Batch + shared: generate site_*.txt + demos/*_demo.html
├── website_audit.py          # Scrape site + LLM conversion audit (legacy; see audit_redesign_spec)
├── audit_redesign_spec.py   # One LLM call → audit + redesign JSON; strong HTML template
├── screenshot_utils.py      # Playwright: screenshot URL or local HTML
├── audit_and_redesign.py    # Before ss → audit → redesign → after ss → audit email
├── demo_worker.py            # Queue: EMAIL_FOUND → generate demo → DEMO_GENERATED
├── outreach_generator.py     # Batch + shared: generate email_*.txt with demo link
├── outreach_worker.py       # Queue: DEMO_GENERATED → generate + send → EMAIL_SENT
├── email_sender.py          # Send outreach; attaches before/after PNGs when present
├── follow_up_sender.py
├── run_pipeline.sh          # Demo-link pipeline
├── run_audit_pipeline.sh    # Audit + before/after pipeline
├── worker_loop.sh           # Queue: continuous loop (lead → email → demo → outreach), sleep 120s
├── requirements.txt
└── README.md
```

## Setup

- **Dependencies:** `pip3 install -r requirements.txt` then **`playwright install chromium`** (for audit before/after screenshots).
- **.env:** `OPENAI_API_KEY`, `GITHUB_PAGES_BASE`, `OUTREACH_EMAIL`, `OUTREACH_PASSWORD`; optional: `OUTREACH_SENDER_NAME`, `OUTREACH_SENDER_COMPANY`, `CALENDLY_LINK` (see `.env.example`).
- **GitHub Pages:** Deploy from branch `gh-pages` so demos are live at `https://USERNAME.github.io/aiab/demos/`.

## Two ways to run

### 1. Batch mode (cron every 4 hours)

Uses `leads.csv`. Good for scheduled runs.

```bash
./run_pipeline.sh
```

Order: `lead_finder` → `email_extractor` → `website_copy_generator` → git deploy demos → `outreach_generator` → `email_sender` → `follow_up_sender`.

**Audit + before/after (stronger for replies):** run the audit pipeline instead so each lead gets an AI conversion audit, a before screenshot of their site, a redesign, and an after screenshot. Email includes the two images and a Calendly link.

```bash
python3 lead_finder.py
python3 email_extractor.py
./run_audit_pipeline.sh
```

Order: `audit_and_redesign` (screenshot current site → scrape → **one LLM call** for audit + redesign JSON → **fill strong template** → screenshot redesign → save **audit.json** + write email with **3 problem bullets**) → optional deploy → `email_sender` (attaches before.png + after.png) → `follow_up_sender`. Set `CALENDLY_LINK` in `.env`. The LLM produces structured JSON (audit.problems, audit.money_impact, redesign.headline, redesign.services, trust_bar, testimonial); we own the layout and only fill content, then Playwright screenshots the rendered HTML.

- **Lead finding:** Bad-site score (no SSL, no viewport, no CTA words, outdated builder). Only adds when **bad_score ≥ 2**.
- **Tracking:** `contacted`, `replied`, `converted`, `contacted_at`, `follow_up_1_sent`, `follow_up_2_sent`.
- **Follow-ups:** Day 3 and Day 7 after first contact (from `contacted_at`).

### 2. Queue mode (24/7 worker loop)

Uses `jobs.csv` and status. Good for a Mac Mini running continuously.

```bash
./worker_loop.sh
```

Loop: `lead_worker` → `email_worker` → `demo_worker` → `outreach_worker` → sleep 120s.

- **Status flow:** `NEW_LEAD` → `EMAIL_FOUND` → `DEMO_GENERATED` → `EMAIL_SENT`.
- Only processes jobs in the right status; no duplicate work.
- Deploy demos to GitHub Pages separately (e.g. after each run, or on a schedule) if you want live links in queue-generated emails.

## Demo links return 404?

1. **File path** — Demos must be at `demos/Name_Demo_demo.html`. GitHub is case-sensitive; the link must match the filename exactly.
2. **Pages branch** — GitHub → **Settings → Pages** → Source: **Deploy from branch** → Branch: **gh-pages** → Folder: **/ (root)**. If set to `main`, the push to `gh-pages` won’t be what’s served.
3. **Delay** — After a push, Pages can take 1–2 minutes. Open `https://USERNAME.github.io/aiab/` and navigate to `demos/` to confirm files appear.

## Safety and volume

- **Send rate:** 45s delay between emails (~80/hour).
- **Targeting:** One niche (e.g. roofers, dentists) often converts better than many industries.
- **$1k goal:** Typically 200–500 sends, 2–5 replies, 1 close. Automation maximizes opportunities; niche + copy close deals.

## Next upgrades

- **Reply detection** — mark `replied=1` when a reply is detected (e.g. Gmail API or manual).
- **Better site scoring** — page speed, mobile check, SSL already in place; tune thresholds or add more signals.
- **Real data in demos** — pull phone, address, services (and optionally images) from the lead’s site into the demo. Makes the redesign feel specific and can improve reply rates.
- **AI website builder API** — replace the custom HTML step with an API (e.g. Durable, Framer) that returns a full landing page. Flow: lead → scrape info → AI builder API → deploy preview URL → send outreach. Produces more polished demos with less custom code.
