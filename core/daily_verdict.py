def daily_verdict(today_classes):
    if not today_classes:
        return None

    votes = {
        "SAFE": 0,
        "RISKY": 0,
        "NOT SAFE": 0
    }

    for cls in today_classes:
        status = cls["status"]

        if status == "MUST ATTEND":
            votes["NOT SAFE"] += 1
        elif status == "RISKY":
            votes["RISKY"] += 1
        else:
            votes["SAFE"] += 1

    # Danger wins ties
    if votes["NOT SAFE"] >= max(votes["RISKY"], votes["SAFE"]):
        return {
            "status": "NOT SAFE",
            "reason": f"{votes['NOT SAFE']} class(es) voted NOT SAFE."
        }

    if votes["RISKY"] >= votes["SAFE"]:
        return {
            "status": "RISKY",
            "reason": f"{votes['RISKY']} class(es) voted RISKY."
        }

    return {
        "status": "SAFE",
        "reason": f"{votes['SAFE']} class(es) voted SAFE."
    }
