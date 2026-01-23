from datetime import datetime, timedelta

# ==============================
# SEMESTER CONFIG (Even Sem 2025–26)
# ==============================

SEMESTER_START = datetime(2026, 1, 5)
SEMESTER_END = datetime(2026, 5, 5)

HOLIDAYS = {
    "2026-01-14",  # Makar Sankranti
    "2026-01-26",  # Republic Day
    "2026-03-04",  # Holi
    "2026-03-20",  # Eid ul Fitr
    "2026-03-27",  # Ram Navmi
    "2026-04-14",  # Dr. Ambedkar Jayanti
    "2026-05-27",  # Bakrid (outside teaching range, safety)
}

# ==============================
# WORKING SATURDAYS (with timetable mapping)
# ==============================

WORKING_SATURDAYS = {
    "2026-01-23": "Monday",
    "2026-01-31": "Wednesday",
    "2026-02-14": "Friday",
    "2026-02-28": "Wednesday",
    "2026-03-14": "Thursday",
    "2026-03-28": "Friday",
    "2026-04-11": "Test",      # Mid-sem test day
    "2026-04-25": "Tuesday",
}

MID_SEM_DAYS = {
    # 1st MST
    "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",

    # Lab MST week
    "2026-03-23", "2026-03-24", "2026-03-25",
    "2026-03-26", "2026-03-28",

    # 2nd MST
    "2026-04-08", "2026-04-09", "2026-04-10", "2026-04-11",
}


# ==============================
# CORE HELPERS
# ==============================

def date_to_str(date_obj: datetime) -> str:
    return date_obj.strftime("%Y-%m-%d")


def is_sunday(date_obj: datetime) -> bool:
    return date_obj.weekday() == 6  # Sunday only


def is_holiday(date_obj: datetime) -> bool:
    return date_to_str(date_obj) in HOLIDAYS

def is_working_saturday(date_obj: datetime) -> bool:
    return (
        date_obj.weekday() == 5 and
        date_to_str(date_obj) in WORKING_SATURDAYS and
        WORKING_SATURDAYS[date_to_str(date_obj)] != "Test"
    )


def is_mid_sem_day(date_obj: datetime) -> bool:
    return date_to_str(date_obj) in MID_SEM_DAYS


def is_teaching_day(date_obj: datetime) -> bool:
    """
    Teaching day = within semester range AND
                   not Sunday AND
                   not holiday AND
                   (
                       weekday Mon–Fri OR
                       approved working Saturday
                   ) AND
                   not mid-sem test day
    """

    if date_obj < SEMESTER_START or date_obj > SEMESTER_END:
        return False

    if is_sunday(date_obj):
        return False

    if is_holiday(date_obj):
        return False

    # Mid-sem tests override everything
    if is_mid_sem_day(date_obj):
        return False

    # Normal weekdays (Mon–Fri)
    if date_obj.weekday() < 5:
        return True

    # Saturday: only if explicitly marked working
    if is_working_saturday(date_obj):
        return True

    return False

def date_to_str(date_obj) -> str:
    return date_obj.strftime("%Y-%m-%d")


def get_effective_timetable_day(date_obj) -> str | None:
    """
    Returns the academic timetable day: mon/tue/wed/thu/fri
    or None if it's a test-only day
    """

    date_str = date_to_str(date_obj)

    if date_str in WORKING_SATURDAYS:
        mapped = WORKING_SATURDAYS[date_str]
        if mapped == "Test":
            return None
        return mapped[:3].lower()

    return date_obj.strftime("%a").lower()



# ==============================
# DATE ITERATOR
# ==============================

def get_all_teaching_days():
    """
    Returns a list of datetime objects representing
    valid teaching days in the semester.
    Saturdays are INCLUDED if they pass the rules.
    """
    days = []
    current = SEMESTER_START

    while current <= SEMESTER_END:
        if is_teaching_day(current):
            days.append(current)
        current += timedelta(days=1)

    return days
