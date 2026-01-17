import math

def bunk_budget(attended, total):
    if total == 0:
        return {
            "budget": float("inf"),
            "status": "NOT STARTED"
        }

    required = math.ceil(0.75 * total)
    budget = attended - required

    if budget > 0:
        status = "SAFE"
    elif budget == 0:
        status = "WARNING"
    else:
        status = "CRITICAL"

    return {
        "budget": budget,
        "status": status
    }
