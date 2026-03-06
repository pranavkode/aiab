from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
import os
import pandas as pd

client = OpenAI()

leads = pd.read_csv("leads.csv")

for index, row in leads.iterrows():
    business = row["business_name"]
    industry = row["industry"]
    city = row["city"]

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

    # Plain text copy (for reference)
    filename = f"site_{business}.txt".replace(" ", "_")
    with open(filename, "w") as f:
        f.write(copy)

    # Demo website as HTML — save into demos/ for GitHub Pages
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
    html_filename = f"{business_file}_demo.html"
    with open(os.path.join("demos", html_filename), "w") as f:
        f.write(html_template)

print("Website copy generated.")
