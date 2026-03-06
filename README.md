# AI Website Agent

Fully automated pipeline: **find leads → generate demos → host demos → generate outreach → send emails**. Run on your Mac now; same setup can run 24/7 on a Mac Mini.

## Project layout

```
aiab/
├── leads.csv                  # business_name, email, website, industry, city, contacted
├── demos/                     # *_demo.html — deployed to GitHub Pages
├── lead_finder.py             # search → weak-site detection → append to leads.csv
├── website_copy_generator.py  # → site_*.txt + demos/*_demo.html
├── outreach_generator.py     # → email_*.txt (includes live demo link)
├── email_sender.py           # send outreach emails, mark leads as contacted
├── run_pipeline.sh           # full pipeline including send
├── requirements.txt
└── README.md
```

## Setup

### 1. Install dependencies

```bash
cd /Users/pranavkode/Documents/GitHub/aiab
pip3 install -r requirements.txt
```

No extra package needed for email — Python’s built-in `smtplib` is used.

### 2. Environment (.env)

Copy `.env.example` to `.env` and set:

- `OPENAI_API_KEY` — for copy and outreach generation.
- `GITHUB_PAGES_BASE` — base URL for demo links (e.g. `https://YOURUSERNAME.github.io/aiab`).
- `OUTREACH_EMAIL` — Gmail address used to send outreach.
- `OUTREACH_PASSWORD` — Gmail App Password (required if 2FA is on; create under Google Account → Security → App passwords).

### 3. GitHub Pages (one-time)

1. Push branch: `git push origin main:gh-pages` (or create `gh-pages` and push).
2. GitHub → **Settings → Pages** → Deploy from branch `gh-pages`, root.
3. Demos: `https://YOURUSERNAME.github.io/aiab/demos/Business_Name_demo.html`

### 4. Leads

- **Manual:** Edit `leads.csv` — columns: `business_name,email,website,industry,city` (and optionally `contacted`).
- **Automatic:** `lead_finder.py` searches by industry/location and appends leads with weak sites (&lt; 300 words). Many leads will have empty `email` until you add **email extraction** (see below).

## Run the pipeline

**Full pipeline (find → generate → deploy → outreach → send)**

```bash
./run_pipeline.sh
```

Order:

1. `lead_finder.py` — add new leads to `leads.csv`
2. `website_copy_generator.py` — write copy and `demos/*_demo.html`
3. Git — add/commit/push `demos/` to `main` and `gh-pages`
4. `outreach_generator.py` — generate emails with live demo links
5. `email_sender.py` — send emails, mark leads as `contacted=1`

**Safety:** `email_sender.py` waits **45 seconds** between emails (~80/hour) to reduce spam/block risk.

**Output**

- `leads.csv` — new leads + `contacted` updated after sends
- `demos/*_demo.html` — live on GitHub Pages
- `email_*.txt` — outreach text (with link); emails sent via Gmail SMTP

## 24/7 loop (cron)

```bash
crontab -e
```

Add (use your path):

```
0 */4 * * * /Users/pranavkode/Documents/GitHub/aiab/run_pipeline.sh
```

`chmod +x run_pipeline.sh` if needed.

## Next upgrade: automatic email discovery

Most sites don’t expose email in search results, so many leads have empty `email` and never get outreach.

**Automatic email extraction** from websites (e.g. scrape contact pages, mailto links, common patterns) can increase usable leads by roughly **5–10×** and is the next high-impact step.

After that: reply tracking and pausing outreach when someone responds.
