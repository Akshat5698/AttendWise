from collections import defaultdict
from utils.subject_map import SUBJECT_MAP


def predict(attended, total, weeks, classes_per_week):
    future_total = total + weeks * classes_per_week
    return (attended / future_total) * 100


def enrich_verdicts(verdicts):
    """
    Takes raw verdicts coming from app.py or attendance_logic
    Replaces subject codes with subject names
    """
    enriched = []

    for v in verdicts:
        enriched.append({
            "day": v["day"],
            "time": v["time"],
            "subject": SUBJECT_MAP.get(v.get("subject") or v.get("code"), v.get("subject") or v.get("code")),
            "status": v["status"],
            "percent": v["percent"]
        })

    return enriched


def group_weekly(verdicts):
    weekly = defaultdict(list)
    for v in verdicts:
        weekly[v["day"]].append(v)
    return weekly
