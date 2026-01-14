
# 📊 AttendWise  
**Attendance Predictor & Smart Bunk Planner**

## Overview
AttendWise is a **Streamlit-based attendance analysis system** that helps students monitor attendance, predict future eligibility, calculate safe bunk limits, and determine how many classes are required to reach the mandatory **75% attendance** threshold.

The project supports **group-wise permanent timetables**, **subject-level analysis**, and **predictive warnings**, making it practical for real academic use instead of being a demo that dies after evaluation.

---

## Key Features

### 📂 Data Input
- Group-wise timetable support (Group A, Group B)
- Permanent timetable storage (no weekly re-upload)
- Excel-based data handling
- PDF attendance reading support

### 📅 Timetable Management
- Group selection dropdown
- Weekly timetable parsing
- Subject code → subject name mapping
- Separate UI logic for timetable display

### 📈 Attendance Analysis
- Current attendance percentage calculation
- Subject-wise attendance breakdown
- Overall attendance status
- Intelligent low-attendance detection

### 🚫 Bunk Prediction & Budgeting
- Calculates safe bunk limits
- Subject-wise bunk allowance
- Priority subject handling
- Prevents bunking when attendance is critical

### 🎯 Recovery Estimation
- Calculates number of classes needed to reach 75%
- Subject-wise recovery planning
- Helps students plan attendance instead of panicking later

### ⚠️ Smart Warning System
- Early warnings for risky attendance
- Clear verdicts: Safe / Warning / Critical
- Prevents accidental academic self-destruction

---

## Tech Stack
- Frontend: Streamlit  
- Backend: Python  
- Data Processing: Pandas  
- Visualization: Matplotlib / Streamlit graphs  
- File Handling: Excel, PDF  

---

## Project Structure
```
AttendWise/
├── assets/
│   └── logo.png
├── core/
│   ├── attendance_logic.py
│   ├── budget.py
│   ├── prediction.py
│   └── warnings.py
├── data/
│   ├── timetable_group_A.xlsx
│   └── timetable_group_B.xlsx
├── ui/
│   ├── graphs.py
│   └── timetable_ui.py
├── utils/
│   ├── attendance_parser.py
│   ├── file_reader.py
│   ├── pdf_reader.py
│   ├── subject_map.py
│   └── timetable_parser.py
├── app.py
├── requirements.txt
└── README.md
```

---

## Installation & Usage

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Disclaimer
This project does **not encourage bunking**.  
It simply applies mathematics before consequences appear.

---

## Author
**Akshat**  
B.Tech AIML Student
