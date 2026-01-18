# AttendWise

**AttendWise** is a smart attendance analytics and bunk-planning system built using **Streamlit**.  
It helps students track attendance, predict risks, plan recoveries, and make informed decisions while maintaining the **75% attendance threshold**, all while respecting semester timetables and special teaching days.

---

## 📌 Overview

AttendWise analyzes attendance data against predefined semester timetables and calendars to provide:

- Subject-wise attendance health
- Smart bunk recommendations
- Recovery planning to reach 75%
- Forecasts for future attendance
- Priority-based subject alerts

The system supports **group-based timetables**, **special Saturday teaching days**, and handles subjects that have **not yet started**.

---

## ✨ Key Features

- 📊 Subject-wise attendance analysis  
- 🔥 Daily smart bunk verdict  
- 🎯 Subject Priority Engine (Critical / Watch / Safe / Not Started)  
- 🔮 What-If attendance simulator  
- 📈 Attendance forecast graphs  
- 🩺 Overall attendance health score  
- 📅 Semester-aware recovery estimation  
- 🟢 Graceful handling of subjects with zero classes  
- 🗓️ Support for special Saturday teaching days  
- 🎓 Clean onboarding setup screen using session state  

---

## 🗂️ Project Structure

```
ATTENDWISE/
├── assets/
│   └── logo.png
│
├── core/
│   ├── attendance_logic.py
│   ├── budget.py
│   ├── calendar_logic.py
│   ├── daily_verdict.py
│   ├── forecast.py
│   ├── health.py
│   ├── prediction.py
│   ├── priority.py
│   ├── warnings.py
│   └── what_if.py
│
├── data/
│   ├── timetable_group_A.xlsx
│   ├── timetable_group_B.xlsx
│   └── saturday_teaching_days.csv
│
├── ui/
│   ├── graphs.py
│   └── timetable_ui.py
│
├── utils/
│   ├── attendance_parser.py
│   ├── file_reader.py
│   ├── pdf_reader.py
│   ├── subject_map.py
│   └── timetable_parser.py
│
├── app.py
├── README.md
└── requirements.txt
```

---

## 🛠️ Tech Stack

- Python 3.11+  
- Streamlit  
- Pandas  
- NumPy  
- OpenPyXL  
- PyArrow  
- PDF parsing utilities  

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the repository
```
git clone https://github.com/your-username/AttendWise.git
cd AttendWise
```

### 2️⃣ Install dependencies
```
pip install -r requirements.txt
```

### 3️⃣ Run the application
```
streamlit run app.py
```

---

## 🚀 Application Flow

1. User lands on a full-screen setup screen  
2. Uploads attendance PDF  
3. Selects academic group (A / B)  
4. App loads corresponding timetable  
5. Dashboard displays:
   - Today’s Smart Bunk Plan  
   - Subject Priority Engine  
   - Attendance forecasts  
   - Recovery requirements  
   - Attendance health score  

---

## 🎯 Subject Priority Engine

Each subject is classified into:

- 🚨 Critical – Immediate attendance required  
- ⚠️ Watch – Attend carefully  
- 😌 Safe – Bunkable  
- 🟢 Not Started – No classes conducted yet  

The engine considers:
- Current attendance percentage  
- Classes attended vs delivered  
- Weekly class frequency  
- Semester-aware recovery logic  
- Special teaching days  

---

## 📅 Semester Calendar Support

AttendWise supports non-standard teaching days, such as Saturdays that follow weekday timetables.

Calendar data is loaded from:
```
data/saturday_teaching_days.csv
```

These days are included when estimating recovery timelines.

---

## ⚠️ Limitations

- No direct ERP integration  
- Attendance files must follow the expected format  
- Forecasts assume consistent future attendance  

---

## 🔮 Future Enhancements

- PDF report export  
- ERP API integration  
- Mobile-optimized UI  
- Auto-import semester calendars  
- Multi-semester comparison  

---

## 👨‍💻 Author

**Akshat Dwivedi**  
B.Tech AIML Student  
Project: AttendWise  

---

## 📄 License

This project is intended for academic and educational use.
