import streamlit as st
import pandas as pd
import re
import math
import warnings


from core.attendance_logic import bunk_allowed
from core.budget import bunk_budget
from core.warnings import warning
from core.prediction import predict, group_weekly
from utils.subject_map import SUBJECT_MAP
from utils.pdf_reader import attendance_pdf_to_df
from datetime import datetime
from core.attendance_logic import get_subject_total_classes
from PIL import Image
from core.what_if import what_if
from core.priority import compute_priority
from core.forecast import forecast
from core.health import attendance_health_score
from core.daily_verdict import daily_verdict




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
    # What If Attendance
    # -----------------------------

    st.subheader("🔮 What-If Attendance Simulator")

    subject = st.selectbox(
        "Choose Subject",
        att["code"].map(lambda x: SUBJECT_MAP.get(x, x)).unique()
    )

    row = att[att["code"].map(lambda x: SUBJECT_MAP.get(x, x)) == subject].iloc[0]

    attended = int(row["attended"])
    total = int(row["total"])

    col1, col2 = st.columns(2)

    with col1:
        attend_more = st.number_input(
            "Attend next classes",
            min_value=0,
            step=1
        )

    with col2:
        bunk_more = st.number_input(
            "Bunk next classes",
            min_value=0,
            step=1
        )

    result = what_if(attended, total, attend_more, bunk_more)

    st.metric("Projected Attendance", f"{result['percent']}%")
    st.write("Status:", result["status"])

    if result["needed"] is not None and result["needed"] > 0:
        st.warning(f"You must attend {result['needed']} consecutive classes to reach 75%")
        
    # -----------------------------
    # Subject Priority Engine (Phase 2)
    # -----------------------------
    
    st.subheader("🎯 Subject Priority Engine")
    priority_rows = []

    for _, row in att.iterrows():
        code = row["code"]
        subject = SUBJECT_MAP.get(code, code)

        attended = int(row["attended"])
        total = int(row["total"])

        is_lab = "lab" in subject.lower()

        info = compute_priority(attended, total, is_lab)

        priority_rows.append({
            "Subject": subject,
            "Attendance %": info["percent"],
            "Recovery Needed": (
                "—" if info["needed"] is None else info["needed"]
            ),
            "Bunk Budget": info["bunk_budget"],
            "Priority": info["priority"]
        })

    df_priority = pd.DataFrame(priority_rows)
    def highlight_priority(row):
        if row["Priority"] == "Must Attend":
            return ["background-color: #3b0a0a"] * len(row)
        if row["Priority"] == "Bunkable":
            return ["background-color: #0a3b1a"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_priority.style.apply(highlight_priority, axis=1),
        use_container_width=True,
        hide_index=True
    )
    
    # -----------------------------
    # Attendance Forecast Graph (Phase 3)
    # -----------------------------

    from core.forecast import forecast

    st.subheader("📈 Attendance Forecast")

    subject = st.selectbox(
        "Select subject for forecast",
        df_priority["Subject"].unique(),
        key="forecast_subject"
    )

    # Get subject code
    row_att = att[att["code"].map(lambda x: SUBJECT_MAP.get(x, x)) == subject].iloc[0]
    row_code = row_att["code"]

    attended = int(row_att["attended"])
    conducted = int(row_att["total"])

    # Semester-aware total classes
    semester_total = get_subject_total_classes(
        row_code,
        timetable
    )

    remaining_classes = max(0, semester_total - conducted)

    if remaining_classes == 0:
        st.info("No future classes left for this subject 📭")
    else:
        steps = st.slider(
            "Future classes to simulate",
            min_value=1,
            max_value=remaining_classes,
            value=min(15, remaining_classes)
        )

        data = forecast(attended, conducted, steps)

        chart_df = pd.DataFrame({
            "Attend All": data["attend_all"],
            "Strategic": data["strategic"],
            "Bunk All": data["bunk_all"]
        })

        st.line_chart(chart_df)
        st.caption("⚠️ 75% attendance is the danger threshold")

    # -----------------------------
    # Attendance Health Score (Phase 4)
    # -----------------------------


    st.subheader("🩺 Attendance Health Score")

    health = attendance_health_score(df_priority)

    if health >= 85:
        st.success(f"Health Score: {health}/100 — You’re chilling 😌")
    elif health >= 70:
        st.warning(f"Health Score: {health}/100 — Stay sharp ⚠️")
    elif health >= 50:
        st.error(f"Health Score: {health}/100 — Dangerous territory 🚨")
    else:
        st.error(f"Health Score: {health}/100 — Academic distress 💀")

    # -----------------------------
    # Daily Attendance Verdict (Phase 5)
    # -----------------------------

    st.subheader("🧭 Today’s Attendance Verdict")

    today = datetime.now().strftime("%a")

    today_subjects = [
        SUBJECT_MAP.get(row["code"], row["code"])
        for _, row in timetable[timetable["day"] == today].iterrows()
    ]

    verdict = daily_verdict(today_subjects, df_priority, health)

    if "NOT SAFE" in verdict["status"]:
        st.error(verdict["status"])
    elif "RISKY" in verdict["status"]:
        st.warning(verdict["status"])
    else:
        st.success(verdict["status"])

    st.caption(verdict["reason"])


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

