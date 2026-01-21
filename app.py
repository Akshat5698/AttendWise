import streamlit as st
import pandas as pd
import re
import math
import warnings
import pytz

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
from datetime import datetime, timedelta
from collections import defaultdict

# NOTE:
# Internal columns must NEVER be rendered directly.
# Always display `display_df`, not df_priority or df_priority_full.



# Use local timezone
IST = pytz.timezone("Asia/Kolkata")
now = datetime.now(IST)

# Cutoff time: 4:35 PM
cutoff_time = now.replace(hour=16, minute=35, second=0, microsecond=0)

# Decide effective day
if now >= cutoff_time:
    effective_date = now.date() + timedelta(days=1)
else:
    effective_date = now.date()

st.markdown("""
<style>
/* Force Streamlit main container to behave */
.block-container {
    padding-top: 0rem !important;
    margin-top: 0rem !important;
    min-height: 100vh;
}
</style>
""", unsafe_allow_html=True)


if "setup_done" not in st.session_state:
    st.session_state.setup_done = False


if "attendance_file" not in st.session_state:
    st.session_state.attendance_file = None

if "group" not in st.session_state:
    st.session_state.group = None


st.set_page_config(
    page_title="AttendWise",
    page_icon="😎",
    layout="wide"
)

warnings.filterwarnings("ignore", message="Could not get FontBBox")

logo = Image.open("assets/logo.png")
st.image(logo, width=80)

# Global CSS
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

# -----------------------------
# PERMANENT TIMETABLE LOADER
# -----------------------------

@st.cache_data
def load_timetables():
    return {
        "Group A": pd.read_excel("data/timetable_group_A.xlsx"),
        "Group B": pd.read_excel("data/timetable_group_B.xlsx",)
    }
@st.cache_data
def load_saturday_calendar():
    df = pd.read_csv("data/saturday_teaching_days.csv")
    df["Date"] = pd.to_datetime(df["Date"])
    return df


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
    
DAY_MAP = {
    "Monday": "Mon",
    "Tuesday": "Tue",
    "Wednesday": "Wed",
    "Thursday": "Thu",
    "Friday": "Fri"
}

def saturday_classes_for_subject(subject_code, timetable, sat_calendar):
    count = 0

    for _, row in sat_calendar.iterrows():
        followed = row["Timetable Followed"]

        # Skip test-only Saturdays
        if "Test" in followed:
            continue

        weekday = followed.split()[0]   # "Monday"
        day_code = DAY_MAP.get(weekday)

        if not day_code:
            continue

        # If subject appears on that weekday, it gets a class
        if not timetable[
            (timetable["day"] == day_code) &
            (timetable["code"] == subject_code)
        ].empty:
            count += 1

    return count


def setup_screen():
    # Hide sidebar + header during setup
    st.markdown("""
    <style>
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stSidebar"] {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

    # Vertical spacing
    st.write("")
    st.write("")
    st.write("")

    # Centered layout using columns (THIS WORKS)
    col_left, col_center, col_right = st.columns([2, 3, 2])

    with col_center:
        st.markdown("""
        <div style="
            background: rgba(255,255,255,0.06);
            padding: 2rem;
            border-radius: 18px;
            border: 1px solid rgba(255,255,255,0.12);
        ">
            <h2>👋 Welcome to AttendWise</h2>
            <p style="opacity:0.75;">Let’s set things up.</p>
        </div>
        """, unsafe_allow_html=True)

        attendance_file = st.file_uploader(
            "Upload attendance PDF",
            type=["pdf"]
        )

        group = st.selectbox(
            "Select group",
            ["Group A", "Group B"]
        )

        if st.button("Continue →", use_container_width=True):
            if attendance_file is None:
                st.warning("Upload attendance file first")
            else:
                st.session_state.attendance_file = attendance_file
                st.session_state.group = group
                st.session_state.setup_done = True
                st.rerun()



if not st.session_state.setup_done:
    setup_screen()
    st.stop()

st.toast("Setup loaded from session", icon="✅")
    
group = st.session_state.group
att_file = st.session_state.attendance_file
timetables = load_timetables()
sat_calendar = load_saturday_calendar()


with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        st.caption(f"Group: **{group}**")
        st.divider()

        timetable_source = st.radio(
            "Timetable source",
            ["Use default", "Upload timetable"],
            horizontal=True
        )

        if timetable_source == "Upload timetable":
            timetable_file = st.file_uploader(
                "Upload timetable (.xlsx)",
                type=["xlsx"]
            )

            if timetable_file:
                timetable = pd.read_excel(timetable_file, engine="openpyxl")
            else:
                st.warning("Upload a timetable file to continue.")
                st.stop()
        else:
            timetable = timetables[group]

        st.divider()

        if st.button("🔁 Change setup"):
            st.session_state.setup_done = False
            st.rerun()


# DASHBOARD-ONLY STYLES

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
    today_slot_verdicts = []  


    today = effective_date.strftime("%a")
    today_short = effective_date.strftime("%a").lower()

    today_rows = timetable[
        timetable["day"].str.strip().str.lower().str[:3] == today_short
    ]


    # Tracks how many classes of each subject are bunked today
    bunk_counter = defaultdict(int)

    if today_rows.empty:
        st.info("No classes scheduled 🎉")
    else:
        for _, row in today_rows.iterrows():
            code = row["code"]
            subject = SUBJECT_MAP.get(code, code)

            record = att[att["code"] == code]
            if record.empty:
                continue

            attended = int(record["attended"].values[0])
            delivered = int(record["total"].values[0])  # ERP delivered till now

            # Increment bunk count for this subject
            bunk_counter[code] += 1
            bunked_so_far = bunk_counter[code]

            # Current attendance
            current_percent = (
                round((attended / delivered) * 100, 2)
                if delivered > 0 else 0.0
            )

            # Attendance AFTER bunking all classes so far today for this subject
            bunk_percent = round(
                (attended / (delivered + bunked_so_far)) * 100, 2
            )

            # Decide status based on AFTER-bunk percentage
            if bunk_percent >= 80:
                status = "SAFE BUNK 😎"
                level = "SAFE"
            elif bunk_percent >= 75:
                status = "RISKY ⚠️"
                level = "RISKY"
            else:
                status = "MUST ATTEND ❌"
                level = "CRITICAL"
            # 🔥 STORE SLOT VERDICT FOR PHASE 5 (VOTING)
            today_slot_verdicts.append({
                "subject": subject,
                "status": (
                    "MUST ATTEND"
                    if level == "CRITICAL"
                    else "RISKY"
                    if level == "RISKY"
                    else "SAFE"
                )
            })

            # Render card
            class_card(
                row["time"],
                subject,
                status,
                f"{current_percent}% → {bunk_percent}%",
                level
            )

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
    st.caption("🛈 Recovery days are estimated using the official semester calendar "
    "(including extra Saturday teaching days). Actual dates may vary.")
    
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

        # Days to recover (semester-calendar aware, includes Saturdays)
        if isinstance(info["needed"], int) and info["needed"] > 0:

            weekly_classes = classes_per_week(code, timetable)

            extra_saturday_classes = saturday_classes_for_subject(
                code,
                timetable,
                sat_calendar
            )

            total_classes_available = weekly_classes + extra_saturday_classes

            if total_classes_available > 0:
                weeks_needed = math.ceil(info["needed"] / total_classes_available)
                days_needed = weeks_needed * 7
            else:
                days_needed = "—"

        else:
            days_needed = "—"


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
            "Recovery Needed": info["needed"],
            
            # UI
            "Recovery (Classes)": recovery_classes_ui,
            "Recovery (Days)": recovery_days_ui,
            "Bunk Budget": (
                info["bunk_budget"]
                if isinstance(info["bunk_budget"], int)
                else None
            ),
            "Priority": info["priority"],
            "Status": friendly_status(info["priority"])
        })

    # Build dataframe
    df_priority = pd.DataFrame(priority_rows)
    # UI-only formatting for Bunk Budget
    df_priority["Bunk Budget (UI)"] = df_priority["Bunk Budget"].apply(
    lambda x: "∞" if pd.isna(x) else int(x)
    )



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
        columns=["Priority", "Recovery Needed", "Bunk Budget","Bunk Budget (UI)"]
    )

    display_df["Bunk Budget"] = df_priority_full["Bunk Budget (UI)"]
    
    cols = display_df.columns.tolist()
    cols.insert(cols.index("Status") + 1, cols.pop(cols.index("Bunk Budget")))
    display_df = display_df[cols]

    st.dataframe(
        display_df.style.apply(highlight_rows, axis=1),
        use_container_width=True,
        hide_index=True
    )
    
    st.download_button(
    "⬇️ Download Priority Report (CSV)",
    display_df.to_csv(index=False),
    file_name="attendance_priority_report.csv",
    mime="text/csv"
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

    st.subheader("🧭 Today's Attendance Verdict")

    today_short = effective_date.strftime("%a").lower()
    
    today_classes = today_slot_verdicts.copy()

    
    # -----------------------------
    # Verdict Rendering (VOTING)
    # -----------------------------

    if not today_slot_verdicts:
        st.error("❌ No class slots detected for today.")
        st.caption("Voting cannot happen because no slot verdicts exist.")
    else:
        today_classes = today_slot_verdicts.copy()
        verdict = daily_verdict(today_classes)

        safe_votes = sum(1 for c in today_classes if c["status"] == "SAFE")
        risky_votes = sum(1 for c in today_classes if c["status"] == "RISKY")
        must_votes = sum(1 for c in today_classes if c["status"] == "MUST ATTEND")
        
        if verdict["status"] == "NOT SAFE":
            st.error("🚨 Attendance Red Zone")
            st.markdown(
                "Today is **not the day to disappear**. "
                "Too many classes are waving red flags. "
                "Show up, survive, bunk another day."
            )

        elif verdict["status"] == "RISKY":
            st.warning("⚠️ Tactical Bunk Zone")
            st.markdown(
                "You *can* bunk, but only if you choose wisely. "
                "One wrong move and attendance will remember this forever."
            )

        else:
            st.success("😌 Green Light for Bunking")
            st.markdown(
                "Attendance is on your side today. "
                "If you bunk, do it guilt-free and responsibly."
            )

    


    # -----------------------------
    # Priority Subject
    # -----------------------------
    
    st.divider()
    
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

#-----------------------
#    Copyright
#-----------------------

# -----------------------------
# Footer / Copyright
# -----------------------------

st.markdown("""
<style>
.footer {
    position: relative;
    width: 100%;
    margin-top: 4rem;
    padding: 20px 0;
    background-color: #020617;
    color: rgba(255, 255, 255, 0.5);
    text-align: center;
    font-size: 14px;
    border-top: 1px solid rgba(255,255,255,0.1);
}
</style>

<div class="footer">
    <p>&copy; 2026 Akshat N & Akshat D. All rights reserved.</p>
</div>
""", unsafe_allow_html=True)

