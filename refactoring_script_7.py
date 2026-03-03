import streamlit as st

st.set_page_config(
    page_title="AttendWise",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ----------------------------
# SESSION STATE INIT
# ----------------------------
if "setup_done" not in st.session_state:
    st.session_state.setup_done = False


# ----------------------------
# SETUP SCREEN
# ----------------------------
def setup_screen():
    st.markdown("""
    <style>
    /* Hide Streamlit chrome */
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stSidebar"] {
        display: none;
    }

    /* Full screen center wrapper */
    .setup-wrapper {
        display: flex;
        justify-content: center;
        margin-top: 120px;
        background: radial-gradient(
            circle at center,
            rgba(30, 58, 138, 0.25) 0%,
            #020617 60%
        );
    }

    /* Card container */
    .setup-card {
        width: 100%;
        max-width: 720px;
        display: flex;
        justify-content: center;
        flex-direction: column;
        gap: 28px;
        background-color: #0f172a;
        padding: 48px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }

    .setup-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 6px;
        color: #f1f5f9;
    }

    .setup-subtitle {
        color: #94a3b8;
        font-size: 1rem;
        margin: 0;
    }

    /* Button styling */
    .stButton > button {
        background-color: transparent !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 12px 24px !important;
        height: auto !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button:hover {
        border-color: #66c3c7 !important;
        color: #66c3c7 !important;
        background-color: rgba(102, 195, 199, 0.05) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="setup-wrapper">', unsafe_allow_html=True)
    st.markdown('<div class="setup-card">', unsafe_allow_html=True)

    st.markdown("""
        <div>
            <div class="setup-title">👋 Welcome to AttendWise</div>
            <p class="setup-subtitle">Let's set things up.</p>
        </div>
    """, unsafe_allow_html=True)

    attendance_file = st.file_uploader(
        "Upload attendance PDF",
        type=["pdf", "xlsx"],
        help="Limit 200MB per file. Accepted formats: PDF, XLSX"
    )

    group = st.selectbox(
        "Select group",
        ["Group A", "Group B"]
    )

    if st.button("Continue →", use_container_width=True):
        if attendance_file is None:
            st.warning("Please select a file first.")
        else:
            st.session_state.attendance_file = attendance_file
            st.session_state.group = group
            st.session_state.setup_done = True
            st.rerun()

    st.markdown('</div></div>', unsafe_allow_html=True)


# ----------------------------
# MAIN DASHBOARD
# ----------------------------
def main_dashboard():
    st.sidebar.title("AttendWise")
    st.sidebar.success("Setup Complete")

    st.title("📊 Dashboard")
    st.write(f"Selected Group: {st.session_state.group}")

    if st.button("Reset Setup"):
        st.session_state.setup_done = False
        st.rerun()


# ----------------------------
# ROUTER
# ----------------------------
if not st.session_state.setup_done:
    setup_screen()
else:
    main_dashboard()