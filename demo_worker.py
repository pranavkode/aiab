"""
Queue worker: process jobs with status=EMAIL_FOUND, generate demo site, set status=DEMO_GENERATED.
"""
import pandas as pd
from website_copy_generator import generate_demo_for_row

JOBS_FILE = "jobs.csv"

jobs = pd.read_csv(JOBS_FILE)
if jobs.empty:
    print("Demo worker: no jobs.")
    exit(0)

todo = jobs[jobs["status"] == "EMAIL_FOUND"]
if todo.empty:
    print("Demo worker: no EMAIL_FOUND jobs.")
    exit(0)

for index, row in jobs.iterrows():
    if row["status"] != "EMAIL_FOUND":
        continue
    try:
        generate_demo_for_row(row)
        jobs.at[index, "status"] = "DEMO_GENERATED"
        print(f"  Demo → {row.get('business_name', '?')}")
    except Exception as e:
        print(f"  Failed {row.get('business_name', '?')}: {e}")

jobs.to_csv(JOBS_FILE, index=False)
print("Demo worker: done.")
