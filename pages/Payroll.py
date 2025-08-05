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

st.set_page_config(page_title="Weekly Payroll Summary", layout="wide")
st.title("🔒 Weekly Payroll Summary")

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

psa_rate_lookup = {p["psa_number"]: p for p in psa_rates}

# --- Date range selection ---
st.header("📆 Select Week")
start_date = st.date_input("Start Date", local_today - datetime.timedelta(days=7))
end_date = st.date_input("End Date", local_today)
st.markdown(f"Showing data from **{start_date}** to **{end_date}**")

# --- Get weekly logs ---
weekly_logs = supabase.table("daily_logs").select("*") \
    .gte("date", str(start_date)).lte("date", str(end_date)).execute().data

# --- Get machine logs for revenue ---
machine_logs = supabase.table("machine_logs").select("*") \
    .gte("date", str(start_date)).lte("date", str(end_date)).execute().data

if weekly_logs:
    # --- Payroll summary dataframe ---
    summary_rows = []
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
    grouped = df.groupby("Name").agg(
        Total_Days=("Date", "count"),
        Total_Pay=("Daily Pay", "sum")
    ).reset_index()

    st.subheader("💵 Weekly Payroll Summary")
    st.dataframe(grouped)

    total_cost = df["Daily Pay"].sum()
    st.metric("Total Weekly Payroll Cost", f"${total_cost:,.2f}")

    # --- Job-Level Revenue & Labor Cost ---
    total_revenue = 0
    job_labor_rows = []

    for log in machine_logs:
        psa = log.get("psa_number")
        footage = log.get("footage", 0)
        rate_info = psa_rate_lookup.get(psa)

        pay_rate = float(rate_info.get("pay_rate") or 0) if rate_info else 0
        company_name = rate_info.get("company_name") if rate_info else "Unknown"
        revenue = footage * pay_rate
        total_revenue += revenue

        # --- Labor cost for this job ---
        crew_links = [e for e in machine_employees if e["machine_log_id"] == log["id"]]
        labor_cost = 0
        for crew in crew_links:
            role_data = next((r for r in employee_roles if r["id"] == crew["employee_role_id"]), None)
            if role_data:
                # Match with daily log for correct pay
                daily_entry = next(
                    (d for d in weekly_logs if d["employee_role_id"] == crew["employee_role_id"] and d["date"] == log["date"]),
                    None
                )
                if daily_entry:
                    rate = role_data["daily_rate"]
                    pay = rate if daily_entry["day_type"] == "full" else rate / 2
                    labor_cost += pay

        job_labor_rows.append({
            "Date": log["date"],
            "PSA Number": psa,
            "Company": company_name,
            "Footage": footage,
            "Pay Rate": pay_rate,
            "Revenue": revenue,
            "Labor Cost": labor_cost,
            "Profit/Loss": revenue - labor_cost
        })

    job_df = pd.DataFrame(job_labor_rows)

    if not job_df.empty:
        st.subheader("📊 Job-Level Profit/Loss")
        st.dataframe(job_df)

        # --- Daily totals ---
        daily_breakdown = job_df.groupby("Date").agg({
            "Revenue": "sum",
            "Labor Cost": "sum",
            "Profit/Loss": "sum"
        }).reset_index()

        st.subheader("📆 Daily Totals")
        st.dataframe(daily_breakdown)

        # --- Exports ---
        st.download_button(
            "⬇️ Download Job-Level CSV",
            data=job_df.to_csv(index=False).encode("utf-8"),
            file_name=f"job_profit_loss_{start_date}_to_{end_date}.csv",
            mime="text/csv"
        )
        st.download_button(
            "⬇️ Download Daily Totals CSV",
            data=daily_breakdown.to_csv(index=False).encode("utf-8"),
            file_name=f"daily_profit_loss_{start_date}_to_{end_date}.csv",
            mime="text/csv"
        )

    # --- Summary Metrics ---
    net_profit = total_revenue - total_cost
    st.metric("Total Weekly Revenue", f"${total_revenue:,.2f}")
    st.metric("Net Profit / Loss", f"${net_profit:,.2f}")

    # --- Download Full Payroll CSV ---
    csv_payroll = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Full Payroll CSV",
        data=csv_payroll,
        file_name=f"payroll_{start_date}_to_{end_date}.csv",
        mime="text/csv"
    )

else:
    st.info("No logs found for selected week.")