import streamlit as st
from supabase import create_client
import datetime
import pandas as pd
import pytz
import streamlit as st



# --- Local timezone ---
LOCAL_TZ = pytz.timezone("US/Central")
local_today = datetime.datetime.now(LOCAL_TZ).date()

# --- Password Protection ---
PASSWORD = st.secrets["auth"]["admin_password"]
st.set_page_config(page_title="Financial Overview", layout="wide")
st.title("📊 Financial Overview")

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
psa_rate_lookup = {p["psa_number"]: p for p in psa_rates}
machines = supabase.table("machines").select("*").execute().data
machine_lookup = {m["id"]: m["name"] for m in machines}

# --- Date range selection ---
with st.expander("📆 Date Range", expanded=True):
    start_date = st.date_input("Start Date", local_today - datetime.timedelta(days=7))
    end_date = st.date_input("End Date", local_today)

# --- Get logs ---
daily_logs = supabase.table("daily_logs").select("*") \
    .gte("date", str(start_date)).lte("date", str(end_date)).execute().data
machine_logs = supabase.table("machine_logs").select("*") \
    .gte("date", str(start_date)).lte("date", str(end_date)).execute().data
machine_employees = supabase.table("machine_employees").select("*").execute().data

# =========================
# 1️⃣ Weekly Payroll
# =========================
with st.expander("🧾 Weekly Payroll Summary", expanded=True):
    if daily_logs:
        payroll_rows = []
        for log in daily_logs:
            role_data = next((r for r in employee_roles if r["id"] == log["employee_role_id"]), None)
            if role_data:
                pay = role_data["daily_rate"] if log["day_type"] == "full" else role_data["daily_rate"] / 2
                payroll_rows.append({
                    "Name": role_data["name"],
                    "Role": role_data["role"],
                    "Date": log["date"],
                    "Day Type": log["day_type"],
                    "Daily Pay": pay
                })

        df_payroll = pd.DataFrame(payroll_rows)
        worker_summary = df_payroll.groupby("Name").agg(
            Total_Days=("Date", "count"),
            Total_Pay=("Daily Pay", "sum")
        ).reset_index()

        st.dataframe(worker_summary)
        total_payroll = df_payroll["Daily Pay"].sum()
        st.metric("💰 Total Weekly Payroll", f"${total_payroll:,.2f}")
    else:
        st.info("No daily logs found for selected period.")

# =========================
# 2️⃣ Machine Production
# =========================
with st.expander("🛠️ Production Per Machine", expanded=True):
    machine_financials = []
    for log in machine_logs:
        machine_name = machine_lookup.get(log["machine_id"], "Fiber Pulling" if log["machine_id"] is None else "Unknown")
        footage = log.get("footage", 0)
        labor_cost = 0

        crew_links = [e for e in machine_employees if e["machine_log_id"] == log["id"]]
        for crew in crew_links:
            role_data = next((r for r in employee_roles if r["id"] == crew["employee_role_id"]), None)
            if role_data:
                daily_entry = next(
                    (d for d in daily_logs if d["employee_role_id"] == crew["employee_role_id"] and d["date"] == log["date"]),
                    None
                )
                if daily_entry:
                    pay = role_data["daily_rate"] if daily_entry["day_type"] == "full" else role_data["daily_rate"] / 2
                    labor_cost += pay

        labor_per_foot = (labor_cost / footage) if footage > 0 else 0
        machine_financials.append({
            "Date": log["date"],
            "Machine": machine_name,
            "Footage": footage,
            "Labor Cost": labor_cost,
            "Labor Cost per Foot": round(labor_per_foot, 2)
        })

    df_machine = pd.DataFrame(machine_financials)
    if not df_machine.empty:
        st.dataframe(df_machine)

        daily_machine_totals = df_machine.groupby(["Date", "Machine"]).agg({
            "Footage": "sum",
            "Labor Cost": "sum"
        }).reset_index()
        daily_machine_totals["Labor Cost per Foot"] = daily_machine_totals.apply(
            lambda row: (row["Labor Cost"] / row["Footage"]) if row["Footage"] > 0 else 0, axis=1
        )

        st.markdown("### 📅 Daily Totals per Machine")
        st.dataframe(daily_machine_totals)

        machine_summary = df_machine.groupby("Machine").agg({
            "Footage": "sum",
            "Labor Cost": "sum"
        }).reset_index()
        machine_summary["Labor Cost per Foot"] = machine_summary.apply(
            lambda row: (row["Labor Cost"] / row["Footage"]) if row["Footage"] > 0 else 0, axis=1
        )

        st.markdown("### 📊 Machine Summary (All Days)")
        st.dataframe(machine_summary)
    else:
        st.info("No machine production logs found.")

# =========================
# 3️⃣ Revenue & Profit/Loss
# =========================
with st.expander("💰 Revenue & Profit/Loss", expanded=True):
    revenue_rows = []
    for log in machine_logs:
        machine_name = machine_lookup.get(log["machine_id"], "Fiber Pulling" if log["machine_id"] is None else "Unknown")
        psa = log.get("psa_number")
        footage = log.get("footage", 0)

        rate_info = psa_rate_lookup.get(psa, {})
        pay_rate = float(rate_info.get("pay_rate") or 0)
        company_name = rate_info.get("company_name", "Unknown")
        revenue = footage * pay_rate

        labor_cost = sum(
            (role["daily_rate"] if dlog["day_type"] == "full" else role["daily_rate"] / 2)
            for crew in [e for e in machine_employees if e["machine_log_id"] == log["id"]]
            for role in [next((r for r in employee_roles if r["id"] == crew["employee_role_id"]), None)]
            for dlog in [next((d for d in daily_logs if d["employee_role_id"] == crew["employee_role_id"] and d["date"] == log["date"]), None)]
            if role and dlog
        )

        profit_loss = revenue - labor_cost

        revenue_rows.append({
            "Date": log["date"],
            "Machine": machine_name,
            "PSA Number": psa,
            "Company": company_name,
            "Footage": footage,
            "Pay Rate": pay_rate,
            "Revenue": revenue,
            "Labor Cost": labor_cost,
            "Profit/Loss": profit_loss
        })

    df_revenue = pd.DataFrame(revenue_rows)
    if not df_revenue.empty:
        st.dataframe(df_revenue)

        total_revenue = df_revenue["Revenue"].sum()
        total_machine_labor = df_revenue["Labor Cost"].sum()
        total_profit = df_revenue["Profit/Loss"].sum()

        adjusted_net_profit = total_revenue - total_payroll
        unassigned_labor = total_payroll - total_machine_labor

        st.metric("💵 Total Revenue", f"${total_revenue:,.2f}")
        st.metric("🧰 Labor Cost (Machine Assigned)", f"${total_machine_labor:,.2f}")
        st.metric("📄 Total Payroll (Daily Logs)", f"${total_payroll:,.2f}")
        st.metric("⚖️ Unassigned Labor Cost", f"${unassigned_labor:,.2f}")
        st.metric("✅ Adjusted Net Profit", f"${adjusted_net_profit:,.2f}")
    else:
        st.info("No revenue data found.")

    # Add this block at the bottom of your financial overview page:

# =========================
# 4 JOB COSTING VIEW BY PSA / CLIENT
# =========================
with st.expander("📘 Job Costing by PSA Number / Client", expanded=True):
    if not df_revenue.empty:
        psa_costing = df_revenue.groupby(["PSA Number", "Company"]).agg({
            "Footage": "sum",
            "Revenue": "sum",
            "Labor Cost": "sum",
            "Profit/Loss": "sum"
        }).reset_index()

        psa_costing["Revenue per Foot"] = psa_costing.apply(
            lambda row: (row["Revenue"] / row["Footage"]) if row["Footage"] > 0 else 0, axis=1
        )
        psa_costing["Labor per Foot"] = psa_costing.apply(
            lambda row: (row["Labor Cost"] / row["Footage"]) if row["Footage"] > 0 else 0, axis=1
        )
        psa_costing["Profit Margin %"] = psa_costing.apply(
            lambda row: (row["Profit/Loss"] / row["Revenue"] * 100) if row["Revenue"] > 0 else 0, axis=1
        )

        st.dataframe(psa_costing.style.format({
            "Revenue": "$ {:,.2f}",
            "Labor Cost": "$ {:,.2f}",
            "Profit/Loss": "$ {:,.2f}",
            "Revenue per Foot": "$ {:.2f}",
            "Labor per Foot": "$ {:.2f}",
            "Profit Margin %": "{:.1f}%"
        }))
    else:
        st.info("No job costing data available for selected date range.")