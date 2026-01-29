from collections import defaultdict
from core.calendar_logic import get_all_teaching_days

def calculate_total_classes_datewise(timetable_df):
    """
    Calculates subject-wise total classes using:
    - calendar-aware teaching days
    - timetable DataFrame with columns: day, time, code
    """

    subject_totals = defaultdict(int)
    teaching_days = get_all_teaching_days()

    for day in teaching_days:
        weekday = day.strftime("%a")  # Mon, Tue, Wed...

        day_rows = timetable_df[timetable_df["day"] == weekday]

        for _, row in day_rows.iterrows():
            subject_totals[row["code"]] += 1

    return dict(subject_totals)


# ==============================
# ATTENDANCE CALCULATIONS
# ==============================

def future_percent(attended, total):
    """
    Percentage AFTER attending the next class
    """
    return (attended + 1) / (total + 1) * 100


def bunk_allowed(attended, total):
    """
    Checks if student can bunk the NEXT class
    and still stay >= 75%
    """
    future = attended / (total + 1) * 100
    return future >= 75


def can_bunk(attended, total):
    """
    Returns:
    (can_bunk_boolean, future_percentage_if_bunked)
    """
    future = attended / (total + 1) * 100
    return future >= 75, round(future, 2)

from utils.subject_map import SUBJECT_MAP

def get_subject_total_classes(subject_or_code, timetable):
    """
    Returns total classes for a subject or course code
    adjusted for holidays, exams, and Saturdays.

    Accepts:
    - course code (e.g. 25CSH-114)
    - subject name (e.g. Data Structures and Algorithms-I)
    """

    subject_totals = calculate_total_classes_datewise(timetable)

    # Case 1: direct match (course code passed)
    if subject_or_code in subject_totals:
        return subject_totals[subject_or_code]

    # Case 2: subject name passed → reverse map to code
    for code, name in SUBJECT_MAP.items():
        if name == subject_or_code and code in subject_totals:
            return subject_totals[code]

    # Not found in timetable
    from datetime import datetime

def get_effective_timetable_day(effective_date):
    """
    Returns timetable day short form:
    Mon, Tue, Wed, Thu, Fri, Sat
    Returns None for holidays / non-academic days
    """

    # Convert date to weekday name
    weekday = effective_date.strftime("%a")  # Mon, Tue, etc.

    # Normal academic days
    if weekday in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
        return weekday

    # Handle Saturday logic
    if weekday == "Sat":
        # Example rule: working Saturdays only
        # Change this condition if you have a calendar
        return "Sat"

    # Sunday or anything else
    return None

def get_day_subjects_from_timetable(day_short, timetable):
    """
    Returns subject_code -> number of classes
    for a given timetable day.
    Example: {"25CSH-114": 2, "25MAT-101": 1}
    """

    if day_short is None:
        return {}

    day_rows = timetable[
        timetable["day"]
        .astype(str)
        .str.strip()
        .str.lower()
        .str.startswith(day_short.lower())
    ]

    subject_count = {}

    for _, row in day_rows.iterrows():
        code = row["code"]
        subject_count[code] = subject_count.get(code, 0) + 1

    return subject_count


