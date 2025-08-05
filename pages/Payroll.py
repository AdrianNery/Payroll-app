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

    # --- Payroll summary ---
    grouped = df.groupby("Name").agg(
        Total_Days=("Date", "count"),
        Total_Pay=("Daily Pay", "sum")
    ).reset_index()

    st.subheader("💵 Weekly Payroll Summary")
    st.dataframe(grouped)

    total_cost = df["Daily Pay"].sum()
    st.metric("Total Weekly Payroll Cost", f"${total_cost:,.2f}")

    # --- Revenue & Profit/Loss ---
    total_revenue = 0
    revenue_rows = []

    for log in machine_logs:
        psa = log.get("psa_number")
        footage = log.get("footage", 0)
        rate_info = psa_rate_lookup.get(psa)

        pay_rate = float(rate_info.get("pay_rate") or 0) if rate_info else 0
        company_name = rate_info.get("company_name") if rate_info else "Unknown"

        revenue = footage * pay_rate
        total_revenue += revenue
        revenue_rows.append({
            "Date": log["date"],
            "PSA Number": psa,
            "Company": company_name,
            "Footage": footage,
            "Pay Rate": pay_rate,
            "Revenue": revenue
        })

    revenue_df = pd.DataFrame(revenue_rows) if revenue_rows else pd.DataFrame()

    # --- Daily breakdown ---
    if not revenue_df.empty:
        daily_revenue = revenue_df.groupby("Date")["Revenue"].sum().reset_index()
    else:
        daily_revenue = pd.DataFrame(columns=["Date", "Revenue"])

    daily_labor = df.groupby("Date")["Daily Pay"].sum().reset_index()

    daily_breakdown = pd.merge(daily_revenue, daily_labor, on="Date", how="outer").fillna(0)
    daily_breakdown["Profit/Loss"] = daily_breakdown["Revenue"] - daily_breakdown["Daily Pay"]

    st.subheader("📊 Daily Profit/Loss Breakdown")
    st.dataframe(daily_breakdown.sort_values("Date"))

    # --- Export Daily Profit/Loss ---
    csv_profit_loss = daily_breakdown.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Daily Profit/Loss CSV",
        data=csv_profit_loss,
        file_name=f"daily_profit_loss_{start_date}_to_{end_date}.csv",
        mime="text/csv"
    )

    # --- Export Daily Labor Costs Only ---
    csv_labor_costs = daily_labor.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Daily Labor Costs CSV",
        data=csv_labor_costs,
        file_name=f"daily_labor_costs_{start_date}_to_{end_date}.csv",
        mime="text/csv"
    )

    net_profit = total_revenue - total_cost
    st.metric("Total Weekly Revenue", f"${total_revenue:,.2f}")
    st.metric("Net Profit / Loss", f"${net_profit:,.2f}")

    # --- Download Weekly Payroll CSV ---
    csv_payroll = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Full Payroll CSV",
        data=csv_payroll,
        file_name=f"payroll_{start_date}_to_{end_date}.csv",
        mime="text/csv"
    )

else:
    st.info("No logs found for selected week.")