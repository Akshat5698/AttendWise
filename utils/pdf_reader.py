import pdfplumber
import pandas as pd
import re

def attendance_pdf_to_df(pdf_file):
    rows = []

    with pdfplumber.open(pdf_file) as pdf:
        text = pdf.pages[0].extract_text()

    for line in text.split("\n"):
        # Match course code
        code_match = re.search(r"(25[A-Z]{3}-\d+)", line)
        numbers = re.findall(r"\d+\.\d+|\d+", line)

        if not code_match or len(numbers) < 3:
            continue

        code = code_match.group(1)

        # From PDF structure:
        # Eligible Delivered = second last number
        # Eligible Attended = third last number
        total = int(numbers[-3])
        attended = int(numbers[-2])

        percent = (attended / total * 100) if total > 0 else 0

        rows.append([code, total, attended, percent])

    return pd.DataFrame(
        rows,
        columns=["code", "total", "attended", "percent"]
    )
