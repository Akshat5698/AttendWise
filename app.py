import streamlit as st
import pandas as pd
import re
import math

from core.attendance_logic import bunk_allowed
from core.budget import bunk_budget
from core.warnings import warning
from core.prediction import predict, group_weekly
from utils.subject_map import SUBJECT_MAP
from utils.pdf_reader import attendance_pdf_to_df
from datetime import datetime


st.title("Class Bunk Predictor OS 😎")

# -----------------------------
# PERMANENT TIMETABLE LOADER
# -----------------------------

@st.cache_data
def load_timetables():
    return {
        "Group A": pd.read_excel("data/timetable_group_A.xlsx", engine="openpyxl"),
        "Group B": pd.read_excel("data/timetable_group_B.xlsx", engine="openpyxl")
    }


timetables = load_timetables()

group = st.selectbox(
    "Select your Group",
    ["Group A", "Group B"]
)

# -----------------------------
# ATTENDANCE UPLOAD
# -----------------------------

att_file = st.file_uploader(
    "Upload Attendance (.xlsx or Attendance PDF)",
    type=["xlsx", "pdf"]
)

# -----------------------------
# Helpers
# -----------------------------

def extract_course_code(text):
    if pd.isna(text):
        return None
    match = re.match(r"(25[A-Z]{3}-\d+)", str(text))
    return match.group(1) if match else None


# -----------------------------
# MAIN LOGIC
# -----------------------------

if att_file:

    # -----------------------------
    # Attendance Parsing
    # -----------------------------

    if att_file.name.endswith(".xlsx"):
        att_raw = pd.read_excel(att_file, engine="openpyxl")

        att = att_raw[[
            "Course Code",
            "Eligible Delivered",
            "Eligible Attended",
            "Eligible Percentage"
        ]].copy()

        att.columns = ["code", "total", "attended", "percent"]

    elif att_file.name.endswith(".pdf"):
        att = attendance_pdf_to_df(att_file)

    else:
        st.error("Unsupported file type. Upload Excel or Attendance PDF.")
        st.stop()

    if att.empty:
        st.error(
            "Could not extract attendance data.\n"
            "Please upload the official attendance Excel or PDF."
        )
        st.stop()

    # -----------------------------
    # Timetable Parsing (Permanent)
    # -----------------------------

    time_raw = timetables[group]

    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    schedule = []

    for _, row in time_raw.iterrows():
        for day in days:
            code = extract_course_code(row.get(day))
            if code:
                schedule.append({
                    "day": day,
                    "time": row["Timing"],
                    "code": code
                })

    timetable = pd.DataFrame(schedule)

    # -----------------------------
    # SMART BUNK VERDICT (WEEKLY)
    # -----------------------------

    st.subheader("🧠 Smart Bunk Verdict (Weekly)")
    verdicts = []

    for _, row in timetable.iterrows():
        record = att[att["code"] == row["code"]]

        if record.empty:
            continue

        attended = int(record["attended"].values[0])
        total = int(record["total"].values[0])
        percent = float(record["percent"].values[0])

        allow = bunk_allowed(attended, total)
        budget = bunk_budget(attended, total)
        warn = warning(percent)

        verdicts.append({
            "day": row["day"],
            "time": row["time"],
            "subject": SUBJECT_MAP.get(row["code"], row["code"]),
            "status": "BUNK 😎" if allow else "ATTEND 💀",
            "percent": round(percent, 2),
            "budget": budget,
            "warn": warn
        })

    weekly = group_weekly(verdicts)
    DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    for day in DAY_ORDER:
        if day not in weekly:
            continue

        st.markdown(f"### 📅 {day}")

        for v in weekly[day]:
            msg = (
                f"{v['time']} | {v['subject']} → {v['status']} | "
                f"Budget: {v['budget']} | {v['warn']}"
            )

            if "BUNK" in v["status"]:
                st.success(msg)
            else:
                st.error(msg)

    # -----------------------------
    # Attendance Graph
    # -----------------------------

    st.subheader("📊 Attendance Graph")

    graph_df = att.copy()
    graph_df["subject"] = graph_df["code"].map(
        lambda x: SUBJECT_MAP.get(x, x)
    )
    graph_df = graph_df.set_index("subject")["percent"]

    st.bar_chart(graph_df)

    # -----------------------------
    # Future Prediction
    # -----------------------------

    st.subheader("🔮 Future Attendance Prediction")
    weeks = st.slider("Weeks Ahead", 1, 12)

    for _, row in att.iterrows():
        future = predict(row["attended"], row["total"], weeks, 5)
        subject = SUBJECT_MAP.get(row["code"], row["code"])
        st.write(f"{subject} → {round(future, 2)}%")

    # -----------------------------
    # Today's Smart Bunk Plan
    # -----------------------------

    st.subheader("🔥 Today's Smart Bunk Plan")

    today = datetime.now().strftime("%a")
    today_rows = timetable[timetable["day"] == today]

    if today_rows.empty:
        st.info("No classes scheduled for today 🎉")
    else:
        for _, row in today_rows.iterrows():
            record = att[att["code"] == row["code"]]

            if record.empty:
                continue

            attended = int(record["attended"].values[0])
            total = int(record["total"].values[0])

            future_percent = (attended / (total + 1)) * 100
            subject = SUBJECT_MAP.get(row["code"], row["code"])
            label = f"{row['time']} | {subject}"

            if future_percent >= 80:
                st.success(f"{label} → SAFE BUNK 😎 ({round(future_percent,2)}%)")
            elif future_percent >= 75:
                st.warning(f"{label} → RISKY ⚠️ ({round(future_percent,2)}%)")
            else:
                st.error(f"{label} → MUST ATTEND ❌ ({round(future_percent,2)}%)")

    # -----------------------------
    # Classes Needed to Reach 75%
    # -----------------------------

    st.subheader("📈 Classes Needed to Reach 75% Attendance")

    TARGET = 0.75

    for _, row in att.iterrows():
        attended = int(row["attended"])
        total = int(row["total"])

        required = (TARGET * total - attended) / (1 - TARGET)
        required_classes = max(0, math.ceil(required))

        subject = SUBJECT_MAP.get(row["code"], row["code"])

        if required_classes == 0:
            st.success(f"{subject} → Already above 75% 😎")
        else:
            st.warning(
                f"{subject} → Attend next {required_classes} classes continuously to reach 75%"
            )

    # -----------------------------
    # Priority Subject
    # -----------------------------

    st.subheader("🚨 Priority Subject (Needs Immediate Attention)")

    below_75 = att[att["percent"] < 75]

    if below_75.empty:
        st.success("All subjects are above 75%. Rare W 🏆")
    else:
        priority_row = below_75.sort_values("percent").iloc[0]
        subject = SUBJECT_MAP.get(priority_row["code"], priority_row["code"])

        st.error(
            f"🔥 PRIORITY SUBJECT: {subject}\n\n"
            f"Current Attendance: {round(priority_row['percent'], 2)}%\n"
            f"Attend this subject until it crosses 75%."
        )

    # -----------------------------
    # Subject-wise Bunk Options
    # -----------------------------

    st.subheader("🎯 Subject-wise Bunking Options")

    for _, row in att.iterrows():
        subject = SUBJECT_MAP.get(row["code"], row["code"])
        total = int(row["total"])
        percent = float(row["percent"])

        if total == 0:
            st.info(
                f"{subject} → NOT STARTED YET ⏳\n"
                f"No attendance data available"
            )
        elif percent >= 80:
            st.success(
                f"{subject} → SAFE TO BUNK 😎\n"
                f"Buffer: {round(percent - 75, 2)}%"
            )
        elif percent >= 75:
            st.warning(
                f"{subject} → LIMITED BUNK ⚠️\n"
                f"Buffer: {round(percent - 75, 2)}% (1–2 classes max)"
            )
        else:
            st.error(
                f"{subject} → NO BUNK ❌\n"
                f"Below 75% by {round(75 - percent, 2)}%"
            )
