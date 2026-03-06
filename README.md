# AI Website Agent

Fully automated outbound pipeline: **find leads → extract emails → generate demos → host → outreach → send → follow up**. Supports both **batch mode** (cron) and **queue mode** (24/7 worker loop).

## Project layout

```
aiab/
├── leads.csv                  # Batch mode: leads + contacted, replied, converted, contacted_at, follow_up_*
├── jobs.csv                  # Queue mode: same fields + status (NEW_LEAD → EMAIL_FOUND → DEMO_GENERATED → EMAIL_SENT)
├── demos/                    # *_demo.html — deployed to GitHub Pages
├── lead_finder.py            # Batch: find weak sites (bad_score >= 2), append to leads.csv
├── lead_worker.py            # Queue: find weak sites, append to jobs.csv as NEW_LEAD
├── email_extractor.py        # Batch: fill missing emails from websites
├── email_worker.py          # Queue: NEW_LEAD → extract email → EMAIL_FOUND
├── website_copy_generator.py # Batch + shared: generate site_*.txt + demos/*_demo.html
├── demo_worker.py            # Queue: EMAIL_FOUND → generate demo → DEMO_GENERATED
├── outreach_generator.py     # Batch + shared: generate email_*.txt with demo link
├── outreach_worker.py       # Queue: DEMO_GENERATED → generate + send → EMAIL_SENT
├── email_sender.py          # Batch: send outreach, set contacted=1, contacted_at
├── follow_up_sender.py      # Send Day 3 / Day 7 follow-ups (leads.csv)
├── run_pipeline.sh          # Batch: full pipeline + follow-ups
├── worker_loop.sh           # Queue: continuous loop (lead → email → demo → outreach), sleep 120s
├── requirements.txt
└── README.md
```

## Setup

- **Dependencies:** `pip3 install -r requirements.txt`
- **.env:** `OPENAI_API_KEY`, `GITHUB_PAGES_BASE`, `OUTREACH_EMAIL`, `OUTREACH_PASSWORD`, and optionally `OUTREACH_SENDER_NAME`, `OUTREACH_SENDER_COMPANY` (see `.env.example`)
- **GitHub Pages:** Deploy from branch `gh-pages` so demos are live at `https://USERNAME.github.io/aiab/demos/`

## Two ways to run

### 1. Batch mode (cron every 4 hours)

Uses `leads.csv`. Good for scheduled runs.

```bash
./run_pipeline.sh
```

Order: `lead_finder` → `email_extractor` → `website_copy_generator` → git deploy demos → `outreach_generator` → `email_sender` → `follow_up_sender`.

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
