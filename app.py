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
from core.attendance_logic import get_subject_total_classes
from PIL import Image
import warnings

warnings.filterwarnings("ignore", message="Could not get FontBBox")

logo = Image.open("assets/logo.png")
st.image(logo, width=80)

st.set_page_config(
    page_title="AttendWise",
    page_icon="😎",
    layout="wide"
)

col1, col2 = st.columns([1, 6])

with col1:
    st.image("assets/logo.png", width=80)

with col2:
    st.title("AttendWise")
    st.caption("📅 Attendance adjusted for holidays & exams")


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

with st.sidebar:
    st.header("🎓 Setup")

    group = st.selectbox(
        "Select Group",
        ["Group A", "Group B"]
    )
# -----------------------------
# ATTENDANCE UPLOAD
# -----------------------------

att_file = st.file_uploader(
        "Upload Attendance (.xlsx or PDF)",
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

def class_card(time, subject, verdict, percent, level):
    color = {
        "SAFE": "#2ecc71",
        "RISKY": "#ffa500",
        "CRITICAL": "#ff4b4b"
    }[level]

    st.markdown(
        f"""
        <div style="
            background:#111;
            padding:14px;
            border-radius:12px;
            margin-bottom:10px;
            border-left:6px solid {color};
        ">
            <div style="opacity:0.8">{time}</div>
            <div style="font-size:16px;font-weight:600">{subject}</div>
            <div><b>{verdict}</b> ({percent}%)</div>
        </div>
        """,
        unsafe_allow_html=True
    )


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

            code = row["code"]
            subject = SUBJECT_MAP.get(code, code)

            attended = int(record["attended"].values[0])
            delivered = int(record["total"].values[0])  # ERP Eligible Delivered (till now)

            # Current attendance (correct, ERP-based)
            percent = round((attended / delivered) * 100, 2) if delivered > 0 else 0.0

            # Attendance AFTER attending today's class
            future_percent = round(((attended + 1) / (delivered + 1)) * 100, 2)

            subject = SUBJECT_MAP.get(row["code"], row["code"])
            label = f"{row['time']} | {subject}"
            
            if future_percent >= 80:
                class_card(row["time"], subject, "SAFE BUNK 😎", future_percent, "SAFE")
            elif future_percent >= 75:
                class_card(row["time"], subject, "RISKY ⚠️", future_percent, "RISKY")
            else:
                class_card(row["time"], subject, "MUST ATTEND ❌", future_percent, "CRITICAL")

                
    # -----------------------------
    # Priority Subject
    # -----------------------------

    st.subheader("🚨 Priority Subjects (Needs Immediate Attention)")

    TARGET = 0.75

    low_attendance = att[(att["total"] > 0) & (att["percent"] < 75)]

    if low_attendance.empty:
        st.success("All subjects are above 75%. Rare W 🏆")
    else:
        for _, row in low_attendance.sort_values("percent").iterrows():
            code = row["code"]
            subject = SUBJECT_MAP.get(code, code)

            attended = int(row["attended"])
            delivered = int(row["total"])  # ERP: Eligible Delivered till now

            # Current attendance (ERP-correct)
            percent = round((attended / delivered) * 100, 2) if delivered > 0 else 0.0

            # Classes needed from THIS POINT onward to reach 75%
            required = (TARGET * delivered - attended) / (1 - TARGET)
            required_classes = max(0, math.ceil(required))

            st.markdown(f"**{subject}**")
            st.progress(min(percent / 75, 1))
            st.caption(
                f"{round(percent,2)}% attendance · "
                f"Attend next {required_classes} classes to reach 75%"
)


    # -----------------------------
    # Attendance Graph
    # -----------------------------

        st.subheader("📊 Attendance Graph")

        graph_df = att.copy()

        graph_df["subject"] = graph_df["code"].map(lambda x: SUBJECT_MAP.get(x, x))

        # ERP-correct current attendance percentage
        graph_df["percent"] = graph_df.apply(
            lambda r: round(
                (r["attended"] / r["total"]) * 100, 2
            ) if r["total"] > 0 else 0.0,
            axis=1
        )

        graph_df = graph_df.sort_values("percent")
        graph_df = graph_df.set_index("subject")["percent"]
        st.bar_chart(graph_df)


    # -----------------------------
    # SMART BUNK VERDICT (WEEKLY)
    # -----------------------------

    st.subheader("🧠 Smart Bunk Verdict")

    verdicts = []

    for _, row in timetable.iterrows():
        record = att[att["code"] == row["code"]]
        if record.empty:
            continue
        
        code = row["code"]
        subject = SUBJECT_MAP.get(code, code)

        attended = int(record["attended"].values[0])

        # Semester-aware total (correct for bunk decisions)
        total = get_subject_total_classes(code, timetable)

        # Current semester-level percentage (projection baseline)
        percent = round((attended / total) * 100, 2) if total > 0 else 0.0



        verdicts.append({
            "day": row["day"],
            "time": row["time"],
            "subject": SUBJECT_MAP.get(row["code"], row["code"]),
            "status": "BUNK 😎" if bunk_allowed(attended, total) else "ATTEND 💀",
            "budget": bunk_budget(attended, total),
            "warn": warning(percent)
        })

    weekly = group_weekly(verdicts)
    
    # -----------------------------
    # DAY SELECTOR (SEMESTER-AWARE)
    # -----------------------------

    # Order we want to respect
    DAY_SEQUENCE = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    # Days that actually exist in the semester timetable
    available_days = sorted(
        timetable["day"].unique(),
        key=lambda d: DAY_SEQUENCE.index(d)
    )

    selected_day = st.selectbox(
        "📅 Select Day",
        available_days
    )

    if selected_day not in weekly or not weekly[selected_day]:
        st.info("No classes scheduled for this day 🎉")
    else:
        for v in weekly[selected_day]:
            icon = "🟢" if "BUNK" in v["status"] else "🔴"

            st.markdown(
                f"{icon} **{v['time']}** — {v['subject']}  \n"
                f"Budget: {v['budget']} · {v['warn']}"
            )


    # -----------------------------
    # Future Prediction
    # -----------------------------

    st.subheader("🔮 Future Attendance Prediction")
    weeks = st.slider("Weeks Ahead", 1, 12)

    for _, row in att.iterrows():
        code = row["code"]
        subject = SUBJECT_MAP.get(code, code)

        attended = int(row["attended"])

        semester_total = get_subject_total_classes(code, timetable)

        future = predict(attended, semester_total, weeks, 5)

        st.markdown(f"**{subject}** → {round(future, 2)}%")

    # -----------------------------
    # Classes Needed to Reach 75%
    # -----------------------------

    st.subheader("📈 Classes Needed to Reach 75% Attendance")

    TARGET = 0.75
    rows = []

    for _, row in att.iterrows():
        code = row["code"]
        subject = SUBJECT_MAP.get(code, code)

        attended = int(row["attended"])
        delivered = int(row["total"])  # ERP: classes delivered till now

        # ✅ Subject not yet started
        if delivered == 0:
            rows.append([subject, "⏳ Not started"])
            continue

        percent = attended / delivered
        if percent >= TARGET:
            rows.append([subject, "✅ Already above 75%"])
            continue

        required = (TARGET * delivered - attended) / (1 - TARGET)
        required_classes = math.ceil(required)

        rows.append([subject, f"📚 Attend next {required_classes} classes"])

    df_needed = pd.DataFrame(rows, columns=["Subject", "Status"])

    st.dataframe(df_needed, use_container_width=True, hide_index=True)


        # if required_classes == 0:
        #     st.success(f"{subject} → Already above 75% 😎")
        # else:
        #     st.warning(
        #         f"{subject} → Attend next {required_classes} classes continuously to reach 75%"
        #     )
            
    # -----------------------------
    # Subject-wise Bunk Options
    # -----------------------------
    st.subheader("🎯 Subject-wise Bunking Options")

    rows = []

    for _, row in att.iterrows():
        code = row["code"]
        subject = SUBJECT_MAP.get(code, code)

        attended = int(row["attended"])
        delivered = int(row["total"])  # ERP delivered till now

        # Subject not yet started
        if delivered == 0:
            rows.append({
                "Subject": subject,
                "Bunk Status": "⏳ Not started"
            })
            continue

        # Semester-aware total (correct for bunking)
        semester_total = get_subject_total_classes(code, timetable)

        percent = (
            (attended / semester_total) * 100
            if semester_total > 0 else 0.0
        )

        if percent >= 80:
            status = "🟢 Safe to bunk"
        elif percent >= 75:
            status = "🟠 Limited bunk"
        else:
            status = "🔴 No bunk"

        rows.append({
            "Subject": subject,
            "Bunk Status": status
        })

    df_bunk = pd.DataFrame(rows)

    st.dataframe(
        df_bunk,
        use_container_width=True,
        hide_index=True
    )
