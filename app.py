import streamlit as st
import pandas as pd
import re
import math
import warnings
import pytz
from pathlib import Path

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
from core.calendar_logic import get_effective_timetable_day, is_holiday
from core.attendance_logic import get_day_subjects_from_timetable


# -----------------------------
# Rendering Guardrails
# -----------------------------
# NOTE:
# Internal columns must NEVER be rendered directly.
# Always display `display_df`, not df_priority or df_priority_full.


# -----------------------------
# App Time Context
# -----------------------------
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

st.set_page_config(
    page_title="AttendWise",
    page_icon="😎",
    layout="wide"
)

# -----------------------------
# Global CSS Loader
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent


def inject_css(filename):
    css_path = BASE_DIR / "assets" / filename
    with open(css_path, encoding="utf-8") as css_file:
        st.markdown(f"<style>{css_file.read()}</style>", unsafe_allow_html=True)


inject_css("styles.css")


# -----------------------------
# Session Defaults
# -----------------------------
if "setup_done" not in st.session_state:
    st.session_state.setup_done = False


if "attendance_file" not in st.session_state:
    st.session_state.attendance_file = None

if "group" not in st.session_state:
    st.session_state.group = None


# -----------------------------
# Runtime Assets
# -----------------------------
warnings.filterwarnings("ignore", message="Could not get FontBBox")

logo = Image.open("assets/logo.png")

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
    card_cls = {
        "SAFE": "class-card-safe",
        "RISKY": "class-card-risky",
        "CRITICAL": "class-card-critical"
    }[level]

    st.markdown(
        f"""
        <div class="class-card {card_cls}">
            <div class="class-card-time">{time}</div>
            <div class="class-card-subject">{subject}</div>
            <div><b>{verdict}</b> ({percent}%)</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def sync_holiday_attend_toggle(attend_key, holiday_key):
    # Keep decisions consistent: holiday means no attendance on that day.
    if st.session_state.get(holiday_key, False):
        st.session_state[attend_key] = False


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
    inject_css("setup.css")

    with st.form("setup_form"):
        st.markdown(
            '''
            <div class="setup-heading">
                <h2 class="setup-title">👋 Welcome to AttendWise</h2>
                <p class="setup-subtitle">Let's set things up.</p>
            </div>
            ''',
            unsafe_allow_html=True
        )

        attendance_file = st.file_uploader(
            "Upload attendance PDF",
            type=["pdf", "xlsx"],
            help="Limit 200MB per file. Accepted formats: PDF, XLSX"
        )

        group = st.selectbox(
            "Select group",
            ["Group A", "Group B"]
        )

        submitted = st.form_submit_button("Continue →", use_container_width=True)

    if submitted:
        if attendance_file is None:
            st.warning("Please select a file first.")
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
    # Navigation Menu
    # -----------------------------
    with st.sidebar:
        st.divider()
        current_page = st.radio("Navigation", [
            "🏠 Home", 
            "📅 Skip College Planner", 
            "🗓️ Day Planner", 
            "🔮 What-If Attendance", 
            "📈 Attendance Forecast"
        ])

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



    if current_page == "🏠 Home":
        # -----------------------------
        # Dashboard 2x2 Grid Restructuring
        # -----------------------------
        
        # Calculate overall health
        health = attendance_health_score(df_priority)
        if health >= 85:
            status_cls, status_text = "status-safe", "Safe"
            health_msg = "You're on track."
            health_sub = "1 more class to stay safe."
        elif health >= 70:
            status_cls, status_text = "status-warn", "Warning"
            health_msg = "Pay Attention."
            health_sub = "Don't skip the next few classes."
        else:
            status_cls, status_text = "status-crit", "Critical"
            health_msg = "Danger Zone."
            health_sub = "Attend all upcoming classes."

        # Dashboard Single Grid Layout
        col_left, col_right = st.columns([1.6, 1], gap="large")

        overall_attended = int(att["attended"].sum())
        overall_total = int(att["total"].sum())
        overall_percent = round((overall_attended / overall_total) * 100, 2) if overall_total > 0 else 0
        overall_cls = "overall-safe" if overall_percent >= 75 else "overall-warn" if overall_percent >= 60 else "overall-crit"

        with col_left:
            # SVG math for progress ring (radius=60, circumference=377)
            circumference = 377
            offset = circumference - (health / 100) * circumference
            
            st.markdown(
f"""<div class="dash-card">
    <div class="card-title">Attendance Health Score</div>
    <div class="health-layout">
        <div class="progress-ring">
            <svg width="140" height="140">
                <circle class="bg" cx="70" cy="70" r="60"></circle>
                <circle class="fg" cx="70" cy="70" r="60" stroke-dasharray="{circumference}" stroke-dashoffset="{offset}"></circle>
            </svg>
            <div class="progress-label">{health}%</div>
        </div>
        <div>
            <div class="health-msg">{health_msg}</div>
            <div class="health-sub">{health_sub}</div>
            <div class="health-note">Keep attendance above 75% to stay safe.</div>
            <div class="status-pill {status_cls}">Status: {status_text}</div>
        </div>
    </div>
    <div class="overall-attendance {overall_cls}">
        Overall Attendance: {overall_percent}%
    </div>
</div>""", unsafe_allow_html=True
            )

        with col_right:
            st.markdown(
"""<div class="dash-card">
    <div class="card-title">Today's Smart Bunk Plan</div>""", unsafe_allow_html=True
            )
            
            today_short = get_effective_timetable_day(effective_date)
            if today_short is None:
                st.markdown("<div class='msg-test-day'>📝 Today is a test day. No bunk decisions.</div>", unsafe_allow_html=True)
            else:
                today_rows = timetable[
                    timetable["day"]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .str.startswith(today_short)
                ]

                bunk_counter = defaultdict(int)

                if today_rows.empty:
                    st.markdown("<div class='msg-no-classes'>No classes scheduled 🎉</div>", unsafe_allow_html=True)
                else:
                    for _, row in today_rows.iterrows():
                        code = row["code"]
                        subject = SUBJECT_MAP.get(code, code)

                        record = att[att["code"] == code]
                        if record.empty:
                            continue

                        attended = int(record["attended"].values[0])
                        delivered = int(record["total"].values[0])

                        bunk_counter[code] += 1
                        bunked_so_far = bunk_counter[code]

                        if delivered > 0:
                            bunk_percent = round((attended / (delivered + bunked_so_far)) * 100, 2)
                        else:
                            bunk_percent = 0.0

                        if bunk_percent >= 80:
                            status_text = "Safe Bunk"
                            dot_cls = "dot-green"
                            desc = f"Attendance drops to {bunk_percent}% if skipped."
                        elif bunk_percent >= 75:
                            status_text = "Risky"
                            dot_cls = "dot-yellow"
                            desc = f"Caution: Skipping drops you to {bunk_percent}%."
                        else:
                            status_text = "Critical"
                            dot_cls = "dot-red"
                            desc = f"Must attend! Skipping drops you to {bunk_percent}%."
                            
                        subj_short = (subject[:25] + '..') if len(subject) > 25 else subject

                        st.markdown(
f"""<div class="option-card">
    <div class="option-title"><div class="option-dot {dot_cls}"></div>{row['time']} - {subj_short}</div>
    <div class="option-desc">{desc}</div>
</div>""", unsafe_allow_html=True
                        )
            
            st.markdown("</div>", unsafe_allow_html=True)

    
        with col_left:
            # Recreate full Subject Priority Engine DataFrame
            st.markdown(
"""<div class="dash-card">
    <div class="card-title">Subject Priority Engine</div>""", unsafe_allow_html=True
            )
            st.caption("🛈 Recovery days are estimated using the official semester calendar.")

            df_priority_full = df_priority.copy()

            def highlight_subject_name(row):
                styles = [""] * len(row)
                subject_idx = row.index.get_loc("Subject")
                attendance = float(row.get("Attendance %", 0))
                if attendance < 75:
                    styles[subject_idx] = "color: #f87171; font-weight: 700;"
                elif "Critical" in row["Status"]:
                    styles[subject_idx] = "color: #f87171; font-weight: 700;"
                elif "Watch" in row["Status"]:
                    styles[subject_idx] = "color: #facc15; font-weight: 700;"
                elif "Safe" in row["Status"]:
                    styles[subject_idx] = "color: #4ade80; font-weight: 700;"
                else:
                    styles[subject_idx] = "font-weight: 700;"
                return styles

            display_df = df_priority_full.drop(
                columns=["Priority", "Recovery Needed", "Bunk Budget","Bunk Budget (UI)"]
            )
            display_df["Bunk Budget"] = df_priority_full["Bunk Budget (UI)"]
            cols = display_df.columns.tolist()
            cols.insert(cols.index("Status") + 1, cols.pop(cols.index("Bunk Budget")))
            display_df = display_df[cols]

            # Calculate height to fit all rows without scrolling (header ~40px, rows ~35px)
            table_height = (len(display_df) * 36) + 43

            st.dataframe(
                display_df.style.apply(highlight_subject_name, axis=1),
                use_container_width=True,
                hide_index=True,
                height=table_height
            )
            st.markdown("</div>", unsafe_allow_html=True)

            # --- Priority Subjects (Footer bars) ---
            st.markdown(
"""<div class="dash-card">
    <div class="card-title">Priority Subjects</div>""", unsafe_allow_html=True
            )
            
            for i, (_, row) in enumerate(df_priority.sort_values(by="Attendance %").iterrows()):
                if i >= 4:  # limit to top 4 for aesthetic
                    break
                    
                subj = row["Subject"]
                perc = float(row.get("Attendance %", 0))
                stat = row["Status"]
                
                if "Safe" in stat:
                    p_cls, fill_cls = "status-safe", "fill-safe"
                elif "Watch" in stat:
                    p_cls, fill_cls = "status-warn", "fill-warn"
                else:
                    p_cls, fill_cls = "status-crit", "fill-crit"
                    
                target = 75
                # Ensure width doesn't blow up CSS
                fill_w = min(100, max(0, perc))
                
                # Extract classes needed
                recovery_needed = row.get("Recovery Needed", 0)
                pill_text = stat.split()[-1] if 'Not Started' not in stat else 'N/A'
                
                if "Safe" not in stat and pd.notna(recovery_needed) and recovery_needed > 0:
                    pill_text = f"Need {int(recovery_needed)}"
                
                # Truncate subject name
                subj_short = (subj[:15] + '..') if len(subj) > 15 else subj
                
                st.markdown(
f"""<div class="subject-row">
    <div class="subject-name">{subj_short}</div>
    <div class="linear-bar-container">
        <div class="linear-bar-fill {fill_cls}" style="width:{fill_w}%;"></div>
        <div class="linear-bar-target"></div>
    </div>
    <div class="subject-target">{target}</div>
    <div class="status-pill status-pill-small {p_cls}">{pill_text}</div>
</div>""", unsafe_allow_html=True
                )
            
            st.markdown("</div>", unsafe_allow_html=True)

    elif current_page == "📅 Skip College Planner":
        # -----------------------------
        # Skip College Planner (Calendar + Smart Bunk Logic)
        # -----------------------------

        st.markdown(
"""<div class="dash-card">
    <div class="card-title">📅 Skip College Planner</div>
    <div class="card-subtext">Select a date range to forecast the impact of skipping college on your attendance.</div>
</div>""", unsafe_allow_html=True
        )

        col_left, col_right = st.columns([1, 1.5], gap="large")

        with col_left:
            st.markdown(
"""<div class="dash-card">
    <div class="card-title">Configuration</div>""", unsafe_allow_html=True
            )

            # --- Date inputs (SEPARATE, DD/MM/YYYY) ---
            col_from, col_to = st.columns(2)

            with col_from:
                from_date = st.date_input(
                    "From date",
                    value=effective_date,
                    min_value=effective_date,
                    format="DD/MM/YYYY"
                )

            with col_to:
                till_date = st.date_input(
                    "Till date",
                    value=effective_date,
                    min_value=effective_date,
                    format="DD/MM/YYYY"
                )

            # --- Options ---
            col_opt1, col_opt2 = st.columns(2)

            with col_opt1:
                skip_labs = st.checkbox("Skip lab classes too", value=True)

            with col_opt2:
                apply_skip = st.checkbox("Apply skip to date range")
                
            st.markdown("</div>", unsafe_allow_html=True)

        with col_right:
            st.markdown(
"""<div class="dash-card">
    <div class="card-title">Impact Analysis</div>""", unsafe_allow_html=True
            )

            # --- Validation & Calculation ---
            if apply_skip:

                if from_date > till_date:
                    st.error("❌ From date cannot be after Till date.")
                    st.stop()

                bunked_classes = defaultdict(int)
                academic_days = 0

                current_date = from_date

                while current_date <= till_date:

                    # Same resolution used in Smart Bunk
                    day_short = get_effective_timetable_day(current_date)

                    if day_short is not None:

                        day_rows = timetable[
                            timetable["day"]
                            .astype(str)
                            .str.strip()
                            .str.lower()
                            .str.startswith(day_short.lower())
                        ]

                        if not day_rows.empty:
                            academic_days += 1

                        for _, row in day_rows.iterrows():
                            code = row["code"]
                            subject_name = SUBJECT_MAP.get(code, code).lower()

                            if not skip_labs and "lab" in subject_name:
                                continue

                            bunked_classes[code] += 1

                    current_date += timedelta(days=1)

                # --- Output ---
                if academic_days == 0:
                    st.info("📭 No academic classes fall within the selected date range.")
                else:
                    rows = []

                    for code, bunk_count in bunked_classes.items():

                        record = att[att["code"] == code]
                        if record.empty:
                            continue

                        subject = SUBJECT_MAP.get(code, code)

                        attended = int(record["attended"].values[0])
                        delivered = int(record["total"].values[0])

                        current_percent = (
                            round((attended / delivered) * 100, 2)
                            if delivered > 0 else 0
                        )

                        new_total = delivered + bunk_count
                        new_percent = round((attended / new_total) * 100, 2)

                        # Classes needed to recover to 75%
                        if new_percent < 75:
                            needed = math.ceil(
                                (0.75 * new_total - attended) / (1 - 0.75)
                            )
                        else:
                            needed = 0

                        rows.append({
                            "Subject": subject,
                            "Current %": current_percent,
                            "Classes Skipped": bunk_count,
                            "After Skip %": new_percent,
                            "Classes Needed for 75%": needed if needed > 0 else "—",
                            "Status": "⚠️ Below 75%" if new_percent < 75 else "✅ Safe"
                        })


                    impact_df = pd.DataFrame(rows)

                    # --- Summary ---
                    colA, colB, colC = st.columns(3)
                    colA.metric("📅 Days Skipped", academic_days)
                    colB.metric("📚 Classes Skipped", sum(bunked_classes.values()))
                    colC.metric(
                        "⚠️ Subjects < 75%",
                        (impact_df["After Skip %"] < 75).sum()
                    )

                    # --- Highlight danger rows ---
                    def highlight(row):
                        return (
                            ["background-color: #3b0a0a"] * len(row)
                            if row["After Skip %"] < 75
                            else ["" for _ in row]
                        )

                    st.dataframe(
                        impact_df.style.apply(highlight, axis=1),
                        use_container_width=True,
                        hide_index=True
                    )

                    # --- Export ---
                    st.download_button(
                        "⬇️ Download Skip Impact Report (CSV)",
                        impact_df.to_csv(index=False),
                        file_name="skip_college_impact.csv",
                        mime="text/csv"
                    )
            else:
                st.info("Select a date range and check 'Apply skip' to instantly preview the impact on attendance.")
            
            st.markdown("</div>", unsafe_allow_html=True)
    elif current_page == "🗓️ Day Planner":
        # =============================
        # DAY PLANNER (DATE-WISE)
        # =============================

        st.markdown(
"""<div class="dash-card">
    <div class="card-title">🗓️ Day Planner</div>
    <div class="card-subtext">Plan attendance day-by-day. Mark each academic day as Attend or Skip and simulate the impact.</div>
</div>""", unsafe_allow_html=True
        )

        col_left, col_right = st.columns([1.2, 1], gap="large")

        with col_left:
            st.markdown(
"""<div class="dash-card">
    <div class="card-title">Plan Your Days</div>""", unsafe_allow_html=True
            )

            # -----------------------------
            # Date range selection
            # -----------------------------
            col1, col2 = st.columns(2)

            with col1:
                planner_from = st.date_input(
                    "From date",
                    value=effective_date,
                    format="DD/MM/YYYY"
                )

            with col2:
                planner_till = st.date_input(
                    "Till date",
                    value=effective_date,
                    format="DD/MM/YYYY"
                )

            if planner_from > planner_till:
                st.error("❌ From date cannot be after Till date.")
                st.stop()

            # -----------------------------
            # Build date list
            # -----------------------------
            planner_dates = []
            current = planner_from
            while current <= planner_till:
                planner_dates.append(current)
                current += timedelta(days=1)

            # -----------------------------
            # Plan your days (UI)
            # -----------------------------
            day_decisions = {}
            for d in planner_dates:
                weekday = d.strftime("%a")  # Mon, Tue, Wed, Thu, Fri, Sat, Sun

                # Use effective academic calendar day so working Saturdays are mapped correctly.
                effective_day_short = get_effective_timetable_day(d)
                if weekday == "Sun" or effective_day_short is None:
                    is_academic = False
                else:
                    is_academic = not timetable[
                        timetable["day"]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        .str.startswith(effective_day_short.lower())
                    ].empty

                is_weekend = weekday in ["Sat", "Sun"]
                attend_key = f"dayplanner_attend_{d}"
                holiday_key = f"dayplanner_holiday_{d}"
                default_holiday = is_holiday(datetime.combine(d, datetime.min.time()))

                if holiday_key not in st.session_state:
                    st.session_state[holiday_key] = default_holiday
                if attend_key not in st.session_state:
                    st.session_state[attend_key] = not is_weekend
                if st.session_state[holiday_key]:
                    st.session_state[attend_key] = False

                col_date, col_day, col_status, col_action = st.columns([2, 1, 2, 3])

                with col_date:
                    st.write(d.strftime("%d/%m/%Y"))

                with col_day:
                    st.write(weekday.upper())

                with col_status:
                    if is_academic:
                        if st.session_state[holiday_key]:
                            st.markdown(
                                "<span class='planner-status-holiday'>Holiday</span>",
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                "<span class='planner-status-academic'>Academic</span>",
                                unsafe_allow_html=True
                            )
                    else:
                        if weekday == "Sun":
                            st.markdown(
                                "<span class='planner-status-sun'>Sun</span>",
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                "<span class='planner-status-none'>No Class</span>",
                                unsafe_allow_html=True
                            )

                with col_action:
                    if is_academic:
                        action_col1, action_col2 = st.columns(2)

                        with action_col1:
                            attend = st.toggle(
                                "Attend",
                                key=attend_key,
                                disabled=st.session_state[holiday_key]
                            )

                        with action_col2:
                            holiday_selected = st.toggle(
                                "Holiday",
                                key=holiday_key,
                                on_change=sync_holiday_attend_toggle,
                                args=(attend_key, holiday_key)
                            )

                        day_decisions[d] = {
                            "attend": attend,
                            "holiday": holiday_selected
                        }
                    else:
                        st.write("—")

            st.caption("🟢 Attend · 🔴 Skip · 🟡 Holiday (holiday days are excluded)")
            
            # -----------------------------
            # Simulation trigger
            # -----------------------------
            simulate_day_plan = st.button("📊 Simulate Attendance Impact", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with col_right:
            st.markdown(
"""<div class="dash-card">
    <div class="card-title">Attendance Impact</div>""", unsafe_allow_html=True
            )
            # -----------------------------
            # Simulation logic
            # -----------------------------
            if simulate_day_plan:
                attended_extra = defaultdict(int)
                bunked_extra = defaultdict(int)

                for d, decision in day_decisions.items():
                    if decision["holiday"]:
                        continue

                    day_short = get_effective_timetable_day(d)
                    if day_short is None:
                        continue

                    day_rows = timetable[
                        timetable["day"]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        .str.startswith(day_short.lower())
                    ]

                    for _, row in day_rows.iterrows():
                        code = row["code"]

                        if decision["attend"]:
                            attended_extra[code] += 1
                        else:
                            bunked_extra[code] += 1

                # -----------------------------
                # Build result table
                # -----------------------------
                rows = []
                base_total_attended = 0
                base_total_conducted = 0

                for _, row in att.iterrows():

                    code = row["code"]
                    subject = SUBJECT_MAP.get(code, code)

                    base_attended = int(row["attended"])
                    base_total = int(row["total"])
                    base_total_attended += base_attended
                    base_total_conducted += base_total

                    attended = base_attended + attended_extra.get(code, 0)
                    total = base_total + attended_extra.get(code, 0) + bunked_extra.get(code, 0)

                    percent = round((attended / total) * 100, 2) if total > 0 else 0

                    # Classes needed to reach 75%
                    if percent < 75:
                        needed = math.ceil((0.75 * total - attended) / 0.25)
                    else:
                        needed = 0

                    rows.append({
                        "Subject": subject,
                        "Attended (Planned)": attended_extra.get(code, 0),
                        "Skipped (Planned)": bunked_extra.get(code, 0),
                        "Final %": percent,
                        "Classes Needed for 75%": needed if needed > 0 else "—",
                        "Status": "⚠️ Below 75%" if percent < 75 else "✅ Safe"
                    })

                total_attended_planned = sum(attended_extra.values())
                total_skipped_planned = sum(bunked_extra.values())
                overall_attended = base_total_attended + total_attended_planned
                overall_total = base_total_conducted + total_attended_planned + total_skipped_planned
                overall_percent = round((overall_attended / overall_total) * 100, 2) if overall_total > 0 else 0
                overall_needed = (
                    math.ceil((0.75 * overall_total - overall_attended) / 0.25)
                    if overall_percent < 75 else 0
                )

                rows.append({
                    "Subject": "Overall Attendance",
                    "Attended (Planned)": total_attended_planned,
                    "Skipped (Planned)": total_skipped_planned,
                    "Final %": overall_percent,
                    "Classes Needed for 75%": overall_needed if overall_needed > 0 else "—",
                    "Status": "⚠️ Below 75%" if overall_percent < 75 else "✅ Safe"
                })

                result_df = pd.DataFrame(rows)

                # -----------------------------
                # Highlight risky subjects
                # -----------------------------
                def highlight(row):
                    return (
                        ["background-color: #3b0a0a"] * len(row)
                        if row["Final %"] < 75
                        else ["" for _ in row]
                    )

                st.dataframe(
                    result_df.style.apply(highlight, axis=1),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Configure your day plan and click 'Simulate Attendance Impact' to see the results.")
                
            st.markdown("</div>", unsafe_allow_html=True)

    elif current_page == "🔮 What-If Attendance":
        # -----------------------------
        # What If Attendance
        # -----------------------------

        st.markdown(
"""<div class="dash-card">
    <div class="card-title">🔮 What-If Attendance Simulator</div>
    <div class="card-subtext">Forecast your attendance percentage based on hypothetical upcoming classes you attend or skip.</div>
</div>""", unsafe_allow_html=True
        )

        col_left, col_right = st.columns([1, 1], gap="large")
        
        with col_left:
            st.markdown(
"""<div class="dash-card">
    <div class="card-title">Configuration</div>""", unsafe_allow_html=True
            )
            
            w_subj = st.selectbox(
                "Choose Subject",
                att["code"].map(lambda x: SUBJECT_MAP.get(x, x)).unique()
            )

            w_row = att[att["code"].map(lambda x: SUBJECT_MAP.get(x, x)) == w_subj].iloc[0]

            w_attended = int(w_row["attended"])
            w_total = int(w_row["total"])

            w_col1, w_col2 = st.columns(2)

            with w_col1:
                attend_more = st.number_input(
                    "Attend next classes",
                    min_value=0,
                    step=1
                )

            with w_col2:
                bunk_more = st.number_input(
                    "Bunk next classes",
                    min_value=0,
                    step=1
                )
            st.markdown("</div>", unsafe_allow_html=True)

        with col_right:
            st.markdown(
"""<div class="dash-card">
    <div class="card-title">Forecast Result</div>""", unsafe_allow_html=True
            )

            w_result = what_if(w_attended, w_total, attend_more, bunk_more)
            w_cls = "whatif-safe" if "Safe" in w_result["status"] else "whatif-warn" if "Risky" in w_result["status"] else "whatif-crit"

            st.markdown(f"""
            <div class="whatif-result {w_cls}">
                <div class="whatif-label">Projected Attendance</div>
                <div class="whatif-percent">{w_result['percent']}%</div>
                <div class="whatif-status">Status: {w_result['status']}</div>
            </div>
            """, unsafe_allow_html=True)

            if w_result["needed"] is not None and w_result["needed"] > 0:
                st.markdown(f"""
                <div class="whatif-needed">
                    ⚠️ You must legitimately attend <b>{w_result['needed']} consecutive classes</b> from now to reach 75%.
                </div>
                """, unsafe_allow_html=True)
                
            st.markdown("</div>", unsafe_allow_html=True)
        
    elif current_page == "📈 Attendance Forecast":
        # -----------------------------
        # Attendance Forecast Graph (Phase 3)
        # -----------------------------

        st.markdown(
"""<div class="dash-card">
    <div class="card-title">📈 Attendance Forecast</div>
    <div class="card-subtext">Simulate your future attendance trajectory to visually see how close you are to the border.</div>
</div>""", unsafe_allow_html=True
        )

        col_left, col_right = st.columns([1, 2], gap="large")

        with col_left:
            st.markdown(
"""<div class="dash-card">
    <div class="card-title">Configuration</div>""", unsafe_allow_html=True
            )

            subject = st.selectbox(
                "Select subject for forecast",
                att["code"].map(lambda x: SUBJECT_MAP.get(x, x)).unique(),
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
                steps = 0
            else:
                steps = st.slider(
                    "Future classes to simulate",
                    min_value=1,
                    max_value=remaining_classes,
                    value=min(15, remaining_classes)
                )

            st.markdown("</div>", unsafe_allow_html=True)

        with col_right:
            st.markdown(
"""<div class="dash-card">
    <div class="card-title">Forecast Trend</div>""", unsafe_allow_html=True
            )

            if remaining_classes > 0 and steps > 0:
                data = forecast(attended, conducted, steps)

                chart_df = pd.DataFrame({
                    "Attend All": data["attend_all"],
                    "Strategic": data["strategic"],
                    "Bunk All": data["bunk_all"]
                })

                st.line_chart(chart_df)
                st.caption("⚠️ The simulation assumes the target minimum attendance is 75%. Keep your trajectory above the danger threshold.")
            else:
                st.write("No projection available.")
                
            st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# Footer / Copyright
# -----------------------------

st.markdown("""
<div class="footer">
    <p>&copy; 2026 Akshat N & Akshat D. All rights reserved.</p>
</div>
""", unsafe_allow_html=True)
