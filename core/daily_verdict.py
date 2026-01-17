def daily_verdict(today_subjects, priority_df, health_score):
    # Subjects today that are critical
    must_attend_today = priority_df[
        (priority_df["Subject"].isin(today_subjects)) &
        (priority_df["Priority"] == "Must Attend")
    ]

    if health_score < 50 or not must_attend_today.empty:
        return {
            "status": "❌ NOT SAFE TO BUNK",
            "reason": "Critical attendance risk today."
        }

    if health_score < 70:
        return {
            "status": "⚠️ RISKY BUNK DAY",
            "reason": "Attendance health is unstable."
        }

    return {
        "status": "✅ SAFE TO BUNK",
        "reason": "Attendance is healthy today."
    }
