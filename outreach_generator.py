from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
import os
import pandas as pd

client = OpenAI()

# Base URL for hosted demos (e.g. https://yourusername.github.io/aiab)
# Set GITHUB_PAGES_BASE in .env so outreach emails include the live demo link.
base_url = os.environ.get("GITHUB_PAGES_BASE", "").rstrip("/")

leads = pd.read_csv("leads.csv")

for index, row in leads.iterrows():
    business = row["business_name"]
    industry = row["industry"]
    business_file = business.replace(" ", "_")
    demo_link = f"{base_url}/demos/{business_file}_demo.html" if base_url else ""

    prompt = f"""
Write a short personalized outreach email to {business}, a {industry} company.

Mention that you made a quick demo redesign of their website and can send it.
"""
    if demo_link:
        prompt += f"""
Include this exact demo link in the email so they can click and see the redesign:
{demo_link}
"""
    prompt += """
Keep it under 70 words and conversational.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    message = response.choices[0].message.content

    filename = f"email_{business}.txt".replace(" ", "_")
    with open(filename, "w") as f:
        f.write(message)

print("Outreach emails generated.")
