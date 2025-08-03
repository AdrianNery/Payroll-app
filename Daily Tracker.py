import streamlit as st
from supabase import create_client
import datetime
import pandas as pd

# Connect to Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Daily Crew Tracker", layout="wide")
st.title("📅 Daily Crew Role Tracker")

selected_date = st.date_input("Select Work Date", datetime.date.today())

# Load all employee roles
employee_roles = supabase.table("employee_roles").select("*").execute().data

# Custom name order
custom_name_order = [
    "Lica", "Kelvin", "Mara", "Dany", "Mainor", "Gamaliel", "Chepe", "Devora",
    "Fortino", "Abelardo", "William", "Edgar", "Angela", "Martin", "Jose Luis",
    "Wicho", "Abel", "Jairo", "Robert", "Frankly", "Rigo", "Adrian", "Paolo", "Rigoberto"
]

# Extract and sort names
all_names = set(r["name"] for r in employee_roles)
unique_names = sorted(all_names, key=lambda n: custom_name_order.index(n) if n in custom_name_order else 999)

tech_data = {}

# Technician input form
with st.form("log_form"):
    st.subheader("👷 Daily Technician Inputs")
    for name in unique_names:
        st.markdown(f"**{name}**")
        roles_for_tech = [r["role"] for r in employee_roles if r["name"] == name]
        selected_role = st.selectbox(f"Role for {name}", roles_for_tech, key=f"{name}_role")
        day_type = st.radio(f"{name} worked:", ["none", "full", "half"], key=f"{name}_daytype", horizontal=True)
        tech_data[name] = {
            "role": selected_role,
            "day_type": day_type
        }
        st.markdown("---")

    submitted = st.form_submit_button("✅ Submit Today's Logs")

    if submitted:
        entries_upserted = 0
        for name, data in tech_data.items():
            if data["day_type"] != "none":
                matching = next((r for r in employee_roles if r["name"] == name and r["role"] == data["role"]), None)
                if matching:
                    # Use upsert to insert or update on conflict
                    supabase.table("daily_logs").upsert({
                        "employee_role_id": matching["id"],
                        "date": str(selected_date),
                        "day_type": data["day_type"]
                    }, on_conflict=["employee_role_id", "date"]).execute()
                    entries_upserted += 1

        st.success(f"✅ {entries_upserted} logs upserted for {selected_date}")

# Show logs
st.header("📋 Today's Work Log")
logs = supabase.table("daily_logs").select("*").eq("date", str(selected_date)).execute().data

if logs:
    display = []
    for log in logs:
        role = next((r for r in employee_roles if r["id"] == log["employee_role_id"]), None)
        if role:
            pay = role["daily_rate"] if log["day_type"] == "full" else role["daily_rate"] / 2
            display.append({
                "Name": role["name"],
                "Role": role["role"],
                "Day Type": log["day_type"],
                "Daily Pay": f"${pay:.2f}"
            })
    df = pd.DataFrame(display)
    st.dataframe(df)
else:
    st.info("No logs found for this date.")