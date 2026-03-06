from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
import os
import pandas as pd

client = OpenAI()


def generate_demo_for_row(row):
    """Generate site copy and demo HTML for one lead/job row. Used by batch script and demo_worker."""
    business = row["business_name"]
    industry = row["industry"]
    city = row.get("city", "")
    prompt = f"""
Create homepage website copy for a {industry} company called {business} located in {city}.

Include:
- headline
- services section
- about section
- call to action
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    copy = response.choices[0].message.content
    filename = f"site_{business}.txt".replace(" ", "_")
    with open(filename, "w") as f:
        f.write(copy)
    copy_html = copy.replace("\n", "<br>\n")
    html_template = f"""
<html>
<head>
<title>{business}</title>
<style>
body {{ font-family: Arial; margin:40px; }}
h1 {{ color:#1a73e8; }}
.section {{ margin-bottom:30px; }}
button {{ padding:12px 20px; background:#1a73e8; color:white; border:none; }}
</style>
</head>

<body>

<h1>{business}</h1>

<div class="section">
{copy_html}
</div>

<button>Request a Free Quote</button>

</body>
</html>
"""
    os.makedirs("demos", exist_ok=True)
    business_file = business.replace(" ", "_")
    with open(os.path.join("demos", f"{business_file}_demo.html"), "w") as f:
        f.write(html_template)


leads = pd.read_csv("leads.csv")

for index, row in leads.iterrows():
    generate_demo_for_row(row)

print("Website copy generated.")
