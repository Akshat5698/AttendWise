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
from core.forecast import forecast




warnings.filterwarnings("ignore", message="Could not get FontBBox")

logo = Image.open("assets/logo.png")
st.image(logo, width=80)

st.set_page_config(
    page_title="AttendWise",
    page_icon="😎",
    layout="wide"
)
st.markdown("""
<style>
.stApp {
    background: radial-gradient(
        circle at top left,
        #1f2937,
        #020617
    );
    color: white;
}
</style>
""", unsafe_allow_html=True)
st.markdown("""
<style>
[data-testid="stHeader"],
[data-testid="stToolbar"] {
    background: transparent;
}

.block-container {
    padding-top: 1rem;
}
</style>
""", unsafe_allow_html=True)
st.markdown("""
<style>
/* Sidebar container */
[data-testid="stSidebar"] {
    background: linear-gradient(
        180deg,
        #020617,
        #020617
    );
    border-right: 1px solid rgba(255,255,255,0.08);
}

/* Sidebar content padding */
[data-testid="stSidebar"] > div:first-child {
    padding-top: 2rem;
}

/* Sidebar text */
[data-testid="stSidebar"] * {
    color: #e5e7eb;
}

/* Sidebar headings */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #ffffff;
    font-weight: 600;
}

/* Sidebar buttons */
[data-testid="stSidebar"] button {
    background-color: #1f2937;
    color: white;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.08);
    transition: all 0.2s ease-in-out;
}

[data-testid="stSidebar"] button:hover {
    background-color: #374151;
    border-color: rgba(255,255,255,0.2);
}

/* Selectbox / inputs */
[data-testid="stSidebar"] select,
[data-testid="stSidebar"] input {
    background-color: #020617;
    color: white;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.15);
}

/* Divider lines */
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.1);
}
</style>
""", unsafe_allow_html=True)


st.markdown("""
<style>
.header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding-top: 1.5rem;
}
.header-title h1 {
    margin-bottom: 0.1rem;
}
.header-title p {
    margin-top: 0;
    opacity: 0.75;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header">
    <img src="assets/logo.png" width="80">
    <div class="header-title">
        <h1>AttendWise</h1>
        <p>📅 Attendance adjusted for holidays & exams</p>
    </div>
</div>
""", unsafe_allow_html=True)



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

    def classes_per_week(subject_code, timetable):
        return timetable[timetable["code"] == subject_code].shape[0]

    def friendly_status(priority):
        return {
            "Must Attend": "🚨 Critical",
            "Attend Carefully": "⚠️ Watch",
            "Bunkable": "😌 Safe",
            "Not Started": "🟢 Not Started"
        }.get(priority, priority)

    for _, row in att.iterrows():
        code = row["code"]
        subject = SUBJECT_MAP.get(code, code)

        attended = int(row["attended"])
        total = int(row["total"])

        is_lab = "lab" in subject.lower()
        info = compute_priority(attended, total, is_lab)

        # Days to recover (calendar-friendly)
        if isinstance(info["needed"], int) and info["needed"] > 0:
            weekly_classes = classes_per_week(code, timetable)
            if weekly_classes > 0:
                days_needed = math.ceil(info["needed"] / weekly_classes) * 7
            else:
                days_needed = "—"
        else:
            days_needed = "—"

        # ✅ APPEND MUST BE INSIDE LOOP
        # UI-friendly recovery text
        recovery_classes_ui = (
            f"Attend {info['needed']} classes"
            if isinstance(info["needed"], int) and info["needed"] > 0
            else "—"
        )

        recovery_days_ui = (
            f"~{days_needed} days"
            if isinstance(days_needed, int)
            else "—"
        )

        priority_rows.append({
            "Subject": subject,
            "Attendance %": round(info["percent"], 2),

            # internal logic
            "Recovery Needed": info["needed"] if info["needed"] is not None else 0,

            # UI
            "Recovery (Classes)": recovery_classes_ui,
            "Recovery (Days)": recovery_days_ui,
            "Bunk Budget": info["bunk_budget"],
            "Priority": info["priority"],
            "Status": friendly_status(info["priority"])
        })

    # Build dataframe
    df_priority = pd.DataFrame(priority_rows)

    # 🔒 Freeze full dataframe for other phases
    df_priority_full = df_priority.copy()

    # Softer, clearer highlighting
    def highlight_rows(row):
        if "Critical" in row["Status"]:
            return ["background-color: #3b0a0a"] * len(row)
        if "Watch" in row["Status"]:
            return ["background-color: #3b2f0a"] * len(row)
        if "Safe" in row["Status"]:
            return ["background-color: #0a3b1a"] * len(row)
        return [""] * len(row)

    # Hide internal columns from UI
    display_df = df_priority_full.drop(
        columns=["Priority", "Recovery Needed"]
    )

    st.dataframe(
        display_df.style.apply(highlight_rows, axis=1),
        use_container_width=True,
        hide_index=True
    )



    # -----------------------------
    # Attendance Forecast Graph (Phase 3)
    # -----------------------------

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
    # Today's Attendance Verdict (Phase 5)
    # -----------------------------

    st.subheader("🧭 Today’s Attendance Verdict")

    today = datetime.now().strftime("%a")

    today_subjects = [
        SUBJECT_MAP.get(row["code"], row["code"])
        for _, row in timetable[timetable["day"] == today].iterrows()
    ]

    if not today_subjects:
        st.success("🟢 No classes today")
        st.caption("Enjoy your free day. No attendance decisions required.")
        verdict = None
    else:
        verdict = daily_verdict(today_subjects, df_priority_full, health)

    if verdict:
        if "NOT SAFE" in verdict["status"]:
            st.error("❌ Not safe to bunk today")
            st.caption(verdict["reason"])
        elif "RISKY" in verdict["status"]:
            st.warning("⚠️ Risky to bunk today")
            st.caption(verdict["reason"])
        else:
            st.success("✅ Safe to bunk today")
            st.caption(verdict["reason"])


    # -----------------------------
    # Priority Subject
    # -----------------------------


    st.divider()

    # -----------------------------
    # Priority Subjects
    # -----------------------------

    st.subheader("🚨 Priority Subjects")

    TARGET = 0.75
    low_attendance = att[(att["total"] > 0) & (att["percent"] < 75)]

    if low_attendance.empty:
        st.success("🎉 All subjects are above 75%. You're safe for now.")
    else:
        for _, row in low_attendance.sort_values("percent").iterrows():
            code = row["code"]
            subject = SUBJECT_MAP.get(code, code)

            attended = int(row["attended"])
            delivered = int(row["total"])

            percent = round((attended / delivered) * 100, 2)

            required = (TARGET * delivered - attended) / (1 - TARGET)
            required_classes = max(0, math.ceil(required))

            with st.container(border=True):
                st.markdown(f"### {subject}")
                st.progress(min(percent / 75, 1))
                st.caption(f"📉 Current: **{percent}%** · 📚 Attend **{required_classes} classes** to reach 75%")



