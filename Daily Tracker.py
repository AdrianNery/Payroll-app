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

# Load employee roles ordered by sort_order
employee_roles = supabase.table("employee_roles").select("*").order("sort_order", desc=False).execute().data

tech_data = {}

# Technician input form
with st.form("log_form"):
    st.subheader("👷 Daily Technician Inputs")
    for role_entry in employee_roles:
        name = role_entry["name"]
        role_id = role_entry["id"]

        st.markdown(f"**{name}**")

        roles_for_tech = [r["role"] for r in employee_roles if r["name"] == name]
        selected_role = st.selectbox(
            f"Role for {name}",
            roles_for_tech,
            key=f"{role_id}_role"
        )
        day_type = st.radio(
            f"{name} worked:",
            ["none", "full", "half"],
            key=f"{role_id}_daytype",
            horizontal=True
        )

        tech_data[role_id] = {
            "name": name,
            "selected_role": selected_role,
            "day_type": day_type
        }

        st.markdown("---")

    submitted = st.form_submit_button("✅ Submit Today's Logs")

    if submitted:
        entries_upserted = 0
        for role_id, data in tech_data.items():
            if data["day_type"] != "none":
                # Match by name + role to get correct ID again
                matching = next(
                    (r for r in employee_roles if r["name"] == data["name"] and r["role"] == data["selected_role"]),
                    None
                )
                if matching:
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

# --- Manage Employee List ---
st.header("➕ Add / Remove / Reorder Employees")

action = st.radio("Choose Action", ["Add", "Remove", "Reorder"], horizontal=True)

if action == "Add":
    with st.form("add_worker_form"):
        new_name = st.text_input("👤 Name")
        new_role = st.selectbox("🛠 Role", ["driller", "locater", "labor"])
        new_rate = st.number_input("💰 Daily Pay", min_value=0.0, step=1.0)
        new_order = st.number_input("🔢 Sort Order", min_value=0, step=1)

        submit_add = st.form_submit_button("✅ Add Worker")
        if submit_add:
            supabase.table("employee_roles").insert({
                "name": new_name,
                "role": new_role,
                "daily_rate": new_rate,
                "sort_order": int(new_order)
            }).execute()
            st.success(f"{new_name} added.")

elif action == "Remove":
    with st.form("remove_worker_form"):
        all_names = sorted(set(r["name"] for r in employee_roles))
        name_to_remove = st.selectbox("👤 Select name", all_names)
        confirm = st.checkbox("⚠️ Confirm removal of all roles for this name")

        submit_remove = st.form_submit_button("🗑 Remove Worker")
        if submit_remove and confirm:
            supabase.table("employee_roles").delete().eq("name", name_to_remove).execute()
            st.success(f"{name_to_remove} removed.")

elif action == "Reorder":
    st.subheader("📥 Reorder / Edit Employee List")

    df_roles = pd.DataFrame(employee_roles)[["id", "name", "role", "daily_rate", "sort_order"]]
    df_edited = st.experimental_data_editor(df_roles, use_container_width=True, num_rows="dynamic")

    if st.button("💾 Save Reordering and Changes"):
        for _, row in df_edited.iterrows():
            supabase.table("employee_roles").update({
                "name": row["name"],
                "role": row["role"],
                "daily_rate": float(row["daily_rate"]),
                "sort_order": int(row["sort_order"])
            }).eq("id", row["id"]).execute()
        st.success("✅ Employee list updated.")