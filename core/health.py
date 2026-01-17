def attendance_health_score(priority_df):
    subjects = len(priority_df)
    if subjects == 0:
        return 100

    score = 100

    must_attend = 0
    avg_percent = priority_df["Attendance %"].mean()

    # 1. Average attendance penalty (bounded)
    if avg_percent < 75:
        score -= min(30, (75 - avg_percent) * 1.2)

    # 2. Priority-based penalties (capped)
    for _, row in priority_df.iterrows():
        if row["Priority"] == "Must Attend":
            must_attend += 1

    score -= min(30, must_attend * 10)

    # 3. Recovery pressure (soft)
    recovery_vals = [
        r for r in priority_df["Recovery Needed"]
        if isinstance(r, int) and r > 0
    ]

    if recovery_vals:
        avg_recovery = sum(recovery_vals) / len(recovery_vals)
        score -= min(25, avg_recovery * 3)

    return max(0, round(score))
