import pandas as pd

def parse_attendance(file):
    df = pd.read_excel(file, engine="openpyxl")

    clean = df[[
        "Course Code",
        "Eligible Delivered",
        "Eligible Attended",
        "Eligible Percentage"
    ]].copy()

    clean.columns = ["code", "total", "attended", "percent"]
    return clean
