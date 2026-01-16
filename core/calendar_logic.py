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


def is_mid_sem_day(date_obj: datetime) -> bool:
    return date_to_str(date_obj) in MID_SEM_DAYS


def is_teaching_day(date_obj: datetime) -> bool:
    """
    Teaching day = within semester range AND
                   not Sunday AND
                   not holiday AND
                   not mid-sem test day
    """
    if date_obj < SEMESTER_START or date_obj > SEMESTER_END:
        return False

    if is_sunday(date_obj):
        return False

    if is_holiday(date_obj):
        return False

    if is_mid_sem_day(date_obj):
        return False

    return True


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
