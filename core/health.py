def compute_health_score(attendance_df):
    scores = []

    for _, row in attendance_df.iterrows():
        total = row["total"]
        attended = row["attended"]

        if total == 0:
            continue  # subject not started, do not punish

        percent = (attended / total) * 100

        if percent >= 85:
            score = 100
        elif percent >= 75:
            score = 80
        elif percent >= 65:
            score = 55
        else:
            score = 30

        scores.append(score)

    if not scores:
        return 100  # semester just started, calm down

    return round(sum(scores) / len(scores))

