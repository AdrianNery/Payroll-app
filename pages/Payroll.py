import streamlit as st
from supabase import create_client
import datetime
import pandas as pd

# 🔐 Simple password (replace with stronger system later)
PASSWORD = st.secrets["auth"]["admin_password"]

st.set_page_config(page_title="Weekly Payroll Summary", layout="wide")
st.title("🔒 Weekly Payroll Summary")

# Ask for password
entered = st.text_input("Enter admin password to continue", type="password")
if entered != PASSWORD:
    st.warning("Access restricted. Enter valid password.")
    st.stop()

# Connect to Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Get all employee roles
employee_roles = supabase.table("employee_roles").select("*").execute().data

# Date range input
st.header("📆 Select Week")
start_date = st.date_input("Start of Week", datetime.date.today())
end_date = start_date + datetime.timedelta(days=6)
st.markdown(f"Showing data from **{start_date}** to **{end_date}**")

# Get weekly logs
weekly_logs = supabase.table("daily_logs").select("*") \
    .gte("date", str(start_date)).lte("date", str(end_date)).execute().data

# Process logs
summary_rows = []
if weekly_logs:
    for log in weekly_logs:
        role_data = next((r for r in employee_roles if r["id"] == log["employee_role_id"]), None)
        if role_data:
            name = role_data["name"]
            role = role_data["role"]
            rate = role_data["daily_rate"]
            pay = rate if log["day_type"] == "full" else rate / 2
            summary_rows.append({
                "Name": name,
                "Role": role,
                "Date": log["date"],
                "Day Type": log["day_type"],
                "Daily Pay": pay
            })

    df = pd.DataFrame(summary_rows)

    # Group by employee
    grouped = df.groupby("Name").agg(
        Total_Days=("Date", "count"),
        Total_Pay=("Daily Pay", "sum")
    ).reset_index()

    st.subheader("💵 Weekly Payroll Summary")
    st.dataframe(grouped)

    # Total company payroll
    total_cost = df["Daily Pay"].sum()
    st.metric("Total Weekly Payroll Cost", f"${total_cost:,.2f}")

    # Download CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Full Payroll CSV",
        data=csv,
        file_name=f"payroll_{start_date}_to_{end_date}.csv",
        mime="text/csv"
    )
else:
    st.info("No logs found for selected week.")