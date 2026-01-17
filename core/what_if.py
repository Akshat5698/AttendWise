import math

def what_if(attended, total, attend_more=0, bunk_more=0):
    new_attended = attended + attend_more
    new_total = total + attend_more + bunk_more

    if new_total == 0:
        return {
            "percent": 0.0,
            "status": "Not Started",
            "needed": None
        }

    percent = round((new_attended / new_total) * 100, 2)

    if percent >= 75:
        return {
            "percent": percent,
            "status": "Safe",
            "needed": 0
        }

    # ✅ Correct recovery math
    required = math.ceil((3 * new_total) - (4 * new_attended))

    return {
        "percent": percent,
        "status": "Danger",
        "needed": max(required, 0)
    }
