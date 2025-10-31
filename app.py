import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import datetime
import re

# --- PAGE CONFIG ---
st.set_page_config(page_title="IMNU Smart Timetable", page_icon="📅", layout="wide")
st.title("📘 IMNU Smart Timetable Viewer")

# --- PATHS ---
DATA_DIR = "data"
ROLL_LIST_DIR = os.path.join(DATA_DIR, "roll_lists")
MASTER_FILE = os.path.join(DATA_DIR, "master_course_info.xlsx")
WEEKLY_FILE = os.path.join(DATA_DIR, "weekly_timetable.xlsx")

# --- LOAD FILES ---
@st.cache_data
def load_master_data():
    return pd.read_excel(MASTER_FILE)

@st.cache_data
def load_weekly_timetable():
    return pd.read_excel(WEEKLY_FILE)

@st.cache_data
def get_student_courses(roll_no):
    student_courses = []
    for file in os.listdir(ROLL_LIST_DIR):
        if file.endswith(".xlsx"):
            df = pd.read_excel(os.path.join(ROLL_LIST_DIR, file))
            if "Roll No." in df.columns and roll_no in df["Roll No."].astype(str).values:
                base = file.replace(".xlsx", "")
                student_courses.append(base)
    return student_courses

# --- HELPER: Extract time from session ---
def extract_start_time(session):
    session = session.replace('\n', ' ').strip()
    match = re.search(r"(\d{1,2}[:.]?\d{0,2}\s*[AP]M)", session, re.IGNORECASE)
    if match:
        time_str = match.group(1).replace('.', ':').upper()
        try:
            return datetime.strptime(time_str, "%I:%M%p").time()
        except:
            try:
                return datetime.strptime(time_str, "%I%p").time()
            except:
                return None
    return None

# --- APP LOGIC ---
roll_no = st.text_input("🎓 Enter your Roll Number (e.g., 21BCM014):")

if roll_no:
    master_df = load_master_data()
    weekly_df = load_weekly_timetable()
    enrolled_courses = get_student_courses(roll_no)

    if not enrolled_courses:
        st.warning("No courses found for this roll number. Please check again.")
    else:
        st.success(f"Found courses for Roll No. **{roll_no}**: {', '.join(enrolled_courses)}")

        results = []
        for _, row in weekly_df.iterrows():
            for session_col in weekly_df.columns[2:]:
                cell = str(row[session_col])
                for course in enrolled_courses:
                    subject_code = course.split("_")[0]
                    div_code = course.split("_")[1] if "_" in course else ""

                    # Strict regex pattern for exact matches
                    if div_code:
                        pattern = rf"\b{re.escape(subject_code)}\(['’]?\s*{div_code}\)"
                    else:
                        pattern = rf"\b{re.escape(subject_code)}(?!\()"

                    if re.search(pattern, cell):
                        results.append({
                            "Date": row["Date"],
                            "Day": row["Day"],
                            "Session": session_col.replace('\n', ' ').strip(),
                            "Subject": subject_code,
                            "Div": div_code,
                            "Cell Info": cell
                        })

        result_df = pd.DataFrame(results)

        if result_df.empty:
            st.error("No matching classes found in the current weekly timetable.")
        else:
            final_df = result_df.merge(
                master_df,
                left_on="Subject",
                right_on="Abbre.",
                how="left"
            )[["Date", "Day", "Session", "Subject", "Div", "Faculty", "Venue"]]

            final_df = final_df.drop_duplicates(subset=["Date", "Day", "Session", "Subject", "Div"])

            # --- Sort by Date and Actual Start Time ---
            final_df["Date"] = pd.to_datetime(final_df["Date"], errors="coerce")
            final_df["Start_Time"] = final_df["Session"].apply(extract_start_time)
            final_df = final_df.sort_values(by=["Date", "Start_Time"]).reset_index(drop=True)

            # --- Display-friendly formatting ---
            final_df["Display Date"] = final_df["Date"].dt.strftime("%d %b")
            final_df["Day"] = final_df["Day"].str[:3]
            today = datetime.now().date()

            st.markdown("### 🗓️ Your Class Schedule")

            # --- Modern Card UI ---
            for _, row in final_df.iterrows():
                bg_color = "#d9eafd" if row["Date"].date() == today else "#f1f3f4"
                st.markdown(
                    f"""
                    <div style="
                        background-color:{bg_color};
                        border:1px solid #ccc;
                        border-radius:12px;
                        padding:12px 16px;
                        margin-bottom:10px;
                        color:#000;
                        font-size:15px;
                        box-shadow:0 1px 3px rgba(0,0,0,0.1);
                    ">
                        <b>📅 {row['Display Date']} ({row['Day']})</b><br>
                        ⏰ {row['Session']}<br>
                        📘 <b>{row['Subject']}</b> ({row['Div']})<br>
                        👨‍🏫 <i>{row['Faculty']}</i><br>
                        📍 {row['Venue']}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # --- Download Timetable ---
            output = BytesIO()
            final_df.drop(columns=["Display Date", "Start_Time"], inplace=False).to_excel(
                output, index=False, engine='openpyxl'
            )
            output.seek(0)

            st.download_button(
                "⬇️ Download My Timetable (Excel)",
                data=output,
                file_name=f"{roll_no}_timetable.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
