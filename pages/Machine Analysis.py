import streamlit as st

# --- Password Protection ---
def password_gate():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        password = st.text_input("🔒 Enter Password", type="password")
        if password == st.secrets["auth"]["admin_password"]:
            st.session_state.authenticated = True
            st.success("Access granted.")
        elif password:
            st.error("Incorrect password")
        st.stop()

password_gate()  # Call before any app logicimport streamlit as st
from supabase import create_client
import pandas as pd
import datetime
import altair as alt

# Connect to Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Cost Per Foot", layout="wide")
st.title("📈 Machine Production Cost Report")

# Select date range
start_date = st.date_input("Start Date", datetime.date.today() - datetime.timedelta(days=7))
end_date = st.date_input("End Date", datetime.date.today())

# Load data
machines = supabase.table("machines").select("*").execute().data
employee_roles = supabase.table("employee_roles").select("*").execute().data
daily_logs = supabase.table("daily_logs").select("*").gte("date", str(start_date)).lte("date", str(end_date)).execute().data
machine_logs = supabase.table("machine_logs").select("*").gte("date", str(start_date)).lte("date", str(end_date)).execute().data
machine_employees = supabase.table("machine_employees").select("*").execute().data

# Helper maps
machine_lookup = {m["id"]: m["name"] for m in machines}
role_lookup = {r["id"]: r for r in employee_roles}

# Build report
report = []

for m_log in machine_logs:
    machine_name = machine_lookup.get(m_log["machine_id"], "Unknown")
    log_id = m_log["id"]
    log_date = m_log["date"]
    footage = m_log["footage"]
    
    crew_links = [e for e in machine_employees if e["machine_log_id"] == log_id]
    
    total_cost = 0
    crew_details = []
    
    for link in crew_links:
        role_entry = role_lookup.get(link["employee_role_id"])
        if not role_entry:
            continue
        
        daily_entry = next((d for d in daily_logs if d["employee_role_id"] == link["employee_role_id"] and d["date"] == log_date), None)
        if not daily_entry:
            continue
        
        rate = role_entry["daily_rate"]
        pay = rate if daily_entry["day_type"] == "full" else rate / 2
        total_cost += pay
        crew_details.append(f"{role_entry['name']} ({role_entry['role']}) - {daily_entry['day_type']}")

    cost_per_foot = total_cost / footage if footage else 0

    report.append({
        "Date": log_date,
        "Machine": machine_name,
        "Footage": footage,
        "Total Labor Cost": round(total_cost, 2),
        "Cost per Foot": round(cost_per_foot, 2),
        "Crew": ", ".join(crew_details)
    })

# Display report
if report:
    df = pd.DataFrame(report)
    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv, f"cost_per_foot_{start_date}_to_{end_date}.csv", "text/csv")

    st.subheader("📊 Visual Insights")

    # Bar chart: Average Cost per Foot by Machine
    st.markdown("### 💸 Average Cost per Foot by Machine")
    avg_costs = df.groupby("Machine")["Cost per Foot"].mean().reset_index()
    bar_chart = alt.Chart(avg_costs).mark_bar().encode(
        x=alt.X("Machine", sort="-y"),
        y="Cost per Foot",
        tooltip=["Machine", "Cost per Foot"]
    ).properties(height=400)
    st.altair_chart(bar_chart, use_container_width=True)

    # Line chart: Total Footage Over Time
    st.markdown("### 📈 Total Footage Bored Over Time")
    footage_per_day = df.groupby("Date")["Footage"].sum().reset_index()
    line_chart = alt.Chart(footage_per_day).mark_line(point=True).encode(
        x="Date:T",
        y="Footage",
        tooltip=["Date", "Footage"]
    ).properties(height=400)
    st.altair_chart(line_chart, use_container_width=True)

    # Stacked bar: Labor Cost per Machine per Day
    st.markdown("### 🧾 Labor Cost per Machine per Day")
    cost_by_day_machine = df.groupby(["Date", "Machine"])["Total Labor Cost"].sum().reset_index()
    stacked = alt.Chart(cost_by_day_machine).mark_bar().encode(
        x="Date:T",
        y="Total Labor Cost",
        color="Machine",
        tooltip=["Date", "Machine", "Total Labor Cost"]
    ).properties(height=400)
    st.altair_chart(stacked, use_container_width=True)
else:
    st.info("No production records found in the selected date range.")