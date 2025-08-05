import streamlit as st
from supabase import create_client
import datetime
import pandas as pd
import pytz

# --- Local timezone ---
LOCAL_TZ = pytz.timezone("US/Central")
local_today = datetime.datetime.now(LOCAL_TZ).date()

# --- Password Protection ---
PASSWORD = st.secrets["auth"]["admin_password"]

st.set_page_config(page_title="Financial Overview", layout="wide")
st.title("📊 Financial Overview (Payroll + Machine Analysis)")

entered = st.text_input("Enter admin password to continue", type="password")
if entered != PASSWORD:
    st.warning("Access restricted. Enter valid password.")
    st.stop()

# --- Supabase connection ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Load datasets ---
employee_roles = supabase.table("employee_roles").select("*").execute().data
psa_rates = supabase.table("psa_rates").select("*").execute().data
machine_employees = supabase.table("machine_employees").select("*").execute().data
machines = supabase.table("machines").select("*").execute().data

psa_rate_lookup = {p["psa_number"]: p for p in psa_rates}
machine_lookup = {m["id"]: m["name"] for m in machines}

# --- Date range selection ---
st.header("📆 Select Date Range")
start_date = st.date_input("Start Date", local_today - datetime.timedelta(days=7))
end_date = st.date_input("End Date", local_today)

# --- Get daily logs & machine logs ---
daily_logs = supabase.table("daily_logs").select("*") \
    .gte("date", str(start_date)).lte("date", str(end_date)).execute().data
machine_logs = supabase.table("machine_logs").select("*") \
    .gte("date", str(start_date)).lte("date", str(end_date)).execute().data

if not machine_logs:
    st.info("No machine logs found for selected period.")
    st.stop()

# --- Calculate per machine log ---
machine_financials = []

for log in machine_logs:
    machine_name = machine_lookup.get(log["machine_id"], "Unknown")
    psa = log.get("psa_number")
    footage = log.get("footage", 0)

    # --- Revenue ---
    rate_info = psa_rate_lookup.get(psa, {})
    pay_rate = float(rate_info.get("pay_rate") or 0)
    company_name = rate_info.get("company_name", "Unknown")
    revenue = footage * pay_rate

    # --- Labor Cost ---
    crew_links = [e for e in machine_employees if e["machine_log_id"] == log["id"]]
    labor_cost = 0
    for crew in crew_links:
        role_data = next((r for r in employee_roles if r["id"] == crew["employee_role_id"]), None)
        if role_data:
            daily_entry = next(
                (d for d in daily_logs if d["employee_role_id"] == crew["employee_role_id"] and d["date"] == log["date"]),
                None
            )
            if daily_entry:
                rate = role_data["daily_rate"]
                pay = rate if daily_entry["day_type"] == "full" else rate / 2
                labor_cost += pay

    labor_per_foot = (labor_cost / footage) if footage > 0 else 0
    profit_loss = revenue - labor_cost

    machine_financials.append({
        "Date": log["date"],
        "Machine": machine_name,
        "PSA Number": psa,
        "Company": company_name,
        "Footage": footage,
        "Pay Rate": pay_rate,
        "Revenue": revenue,
        "Labor Cost": labor_cost,
        "Labor Cost per Foot": round(labor_per_foot, 2),
        "Profit/Loss": profit_loss
    })

df_machine = pd.DataFrame(machine_financials)

# --- Detailed machine logs ---
st.subheader("📋 Detailed Machine Logs")
st.dataframe(df_machine)

# --- Daily Totals per Machine ---
daily_machine_totals = df_machine.groupby(["Date", "Machine"]).agg({
    "Footage": "sum",
    "Revenue": "sum",
    "Labor Cost": "sum",
    "Profit/Loss": "sum"
}).reset_index()

daily_machine_totals["Labor Cost per Foot"] = daily_machine_totals.apply(
    lambda row: (row["Labor Cost"] / row["Footage"]) if row["Footage"] > 0 else 0, axis=1
)

st.subheader("📆 Daily Totals per Machine")
st.dataframe(daily_machine_totals)

# --- Machine Summary (all days) ---
machine_summary = df_machine.groupby("Machine").agg({
    "Footage": "sum",
    "Revenue": "sum",
    "Labor Cost": "sum",
    "Profit/Loss": "sum"
}).reset_index()

machine_summary["Labor Cost per Foot"] = machine_summary.apply(
    lambda row: (row["Labor Cost"] / row["Footage"]) if row["Footage"] > 0 else 0, axis=1
)

st.subheader("📊 Machine Summary (All Days)")
st.dataframe(machine_summary)

# --- Grand Totals ---
total_revenue = df_machine["Revenue"].sum()
total_labor = df_machine["Labor Cost"].sum()
total_profit = df_machine["Profit/Loss"].sum()

st.metric("Total Revenue", f"${total_revenue:,.2f}")
st.metric("Total Labor Cost", f"${total_labor:,.2f}")
st.metric("Total Net Profit/Loss", f"${total_profit:,.2f}")

# --- Exports ---
st.download_button(
    "⬇️ Download Detailed Machine Logs CSV",
    data=df_machine.to_csv(index=False).encode("utf-8"),
    file_name=f"machine_logs_{start_date}_to_{end_date}.csv",
    mime="text/csv"
)

st.download_button(
    "⬇️ Download Daily Totals per Machine CSV",
    data=daily_machine_totals.to_csv(index=False).encode("utf-8"),
    file_name=f"daily_machine_totals_{start_date}_to_{end_date}.csv",
    mime="text/csv"
)

st.download_button(
    "⬇️ Download Machine Summary CSV",
    data=machine_summary.to_csv(index=False).encode("utf-8"),
    file_name=f"machine_summary_{start_date}_to_{end_date}.csv",
    mime="text/csv"
)