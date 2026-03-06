from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
import os
import pandas as pd

client = OpenAI()
base_url = os.environ.get("GITHUB_PAGES_BASE", "").rstrip("/")
sender_name = os.environ.get("OUTREACH_SENDER_NAME", "Pranav").strip()
sender_company = os.environ.get("OUTREACH_SENDER_COMPANY", "SiteRenovate").strip()


def generate_outreach_for_row(row, save_to_file=True):
    """Generate short, human outreach email body. No placeholders. Subject is set in email_sender."""
    business = row["business_name"]
    industry = row["industry"]
    business_file = business.replace(" ", "_")
    demo_link = f"{base_url}/demos/{business_file}_demo.html" if base_url else ""

    prompt = f"""Write a very short outreach email BODY only (no subject line) for this scenario:

- You are writing to {business}, a {industry} company.
- You made a quick redesign of their website and want to share the demo link.
- Your name is {sender_name} and your company is {sender_company}. Use these EXACT values at the end of the email. Do NOT use [Name], [Your Name], [Your Position], or any placeholder — only real text.
- Include this exact demo link on its own line: {demo_link}
- Keep the whole email under 55 words. Short and conversational.
- Structure: brief greeting, one sentence that you made a quick redesign, "You can see it here:" then the link, one short line on why it might help, "Happy to send the files if useful.", then sign with {sender_name} and {sender_company}."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    message = response.choices[0].message.content.strip()
    # Drop any line that looks like a subject line (we set subject in email_sender)
    lines = [line for line in message.split("\n") if not line.strip().lower().startswith("subject:")]
    message = "\n".join(lines).strip()

    if save_to_file:
        filename = f"email_{business}.txt".replace(" ", "_")
        with open(filename, "w") as f:
            f.write(message)
    return message


leads = pd.read_csv("leads.csv")

for index, row in leads.iterrows():
    generate_outreach_for_row(row, save_to_file=True)

print("Outreach emails generated.")
