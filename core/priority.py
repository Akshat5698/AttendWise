import math

def compute_priority(attended, total, is_lab=False):
    if total == 0:
        return {
            "percent": 0.0,
            "needed": None,
            "bunk_budget": "∞",
            "priority": "Not Started"
        }

    percent = round((attended / total) * 100, 2)

    # Recovery math (correct, same as Phase 1)
    if percent >= 75:
        needed = 0
    else:
        needed = max(0, math.ceil((3 * total) - (4 * attended)))

    # Bunk budget
    max_bunks = math.floor((attended / 0.75) - total)
    bunk_budget = max(0, max_bunks)

    # Priority rules
    if is_lab and percent < 80:
        priority = "Must Attend"
    elif percent < 65 or needed >= 6:
        priority = "Must Attend"
    elif bunk_budget <= 1:
        priority = "Attend Carefully"
    elif percent >= 80 and bunk_budget >= 3:
        priority = "Bunkable"
    else:
        priority = "Attend Carefully"

    return {
        "percent": percent,
        "needed": needed,
        "bunk_budget": bunk_budget,
        "priority": priority
    }
