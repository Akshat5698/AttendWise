import pandas as pd
import re

def extract_code(cell):
    if pd.isna(cell):
        return None
    match = re.match(r"(25[A-Z]{3}-\d+)", str(cell))
    return match.group(1) if match else None

def parse_timetable(file):
    df = pd.read_excel(file, engine="openpyxl")

    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    schedule = []

    for _, row in df.iterrows():
        for day in days:
            code = extract_code(row.get(day))
            if code:
                schedule.append({
                    "day": day,
                    "time": row["Timing"],
                    "code": code
                })

    return pd.DataFrame(schedule)
