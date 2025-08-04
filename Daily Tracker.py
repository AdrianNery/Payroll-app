import streamlit as st
from supabase import create_client
import datetime
import pandas as pd
from collections import defaultdict

# Connect to Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Daily Crew Tracker", layout="wide")
st.title("📅 Daily Tracker")

selected_date = st.date_input("Select Date", datetime.date.today())

# Load employee roles ordered by sort_order
employee_roles = supabase.table("employee_roles").select("*").order("sort_order", desc=False).execute().data

# Group employee roles by name
grouped_roles = defaultdict(list)
for entry in employee_roles:
    # Default sort_order to a high value if missing
    entry["sort_order"] = int(entry.get("sort_order") or 9999)
    grouped_roles[entry["name"]].append(entry)

# Sort names based on the minimum sort_order of any of their roles
sorted_names = sorted(grouped_roles.items(), key=lambda x: min(r["sort_order"] for r in x[1]))

tech_data = {}

# Technician input form
with st.form("log_form"):
    st.subheader("👷 Technician Check-in")
    for name, role_entries in sorted_names:
        st.markdown(f"**{name}**")
        role_options = [r["role"] for r in role_entries]
        selected_role = st.selectbox(f"Role for {name}", role_options, key=f"{name}_role")
        day_type = st.radio(f"{name} worked:", ["none", "full", "half"], key=f"{name}_daytype", horizontal=True)
        tech_data[name] = {"selected_role": selected_role, "day_type": day_type}
        st.markdown("---")

    submitted = st.form_submit_button("✅ Submit Today's Logs")

    if submitted:
        entries_upserted = 0
        for name, data in tech_data.items():
            if data["day_type"] != "none":
                matching = next((r for r in grouped_roles[name] if r["role"] == data["selected_role"]), None)
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
st.header("➕ Add / Remove / Reorder")

action = st.radio("Choose Action", ["Add", "Remove", "Reorder"], horizontal=True)

if action == "Add":
    with st.form("add_worker_form"):
        new_name = st.text_input("👤 Name")
        new_role = st.selectbox("👷 Role", ["driller", "locater", "labor"])
        new_rate = st.number_input("💰 Daily Pay", min_value=0.0, step=1.0)

        submit_add = st.form_submit_button("✅ Add Tech")
        if submit_add:
            # Automatically assign the next sort order
            current_sorts = [int(r.get("sort_order") or 0) for r in employee_roles]
            next_sort_order = max(current_sorts, default=0) + 1

            supabase.table("employee_roles").insert({
                "name": new_name,
                "role": new_role,
                "daily_rate": new_rate,
                "sort_order": next_sort_order
            }).execute()
            st.success(f"{new_name} added to bottom of list.")

elif action == "Remove":
    with st.form("remove_worker_form"):
        all_names = sorted(set(r["name"] for r in employee_roles))
        name_to_remove = st.selectbox("👤 Select name", all_names)
        confirm = st.checkbox("⚠️ Confirm removal of all roles for this name")

        submit_remove = st.form_submit_button("🗑 Remove Tech")
        if submit_remove and confirm:
            supabase.table("employee_roles").delete().eq("name", name_to_remove).execute()
            st.success(f"{name_to_remove} removed.")

elif action == "Reorder":
    st.subheader("📥 Reorder")

    # Create a sort map from lowest current sort_order per employee name
    name_sort_map = {}
    for r in employee_roles:
        name = r["name"]
        current_sort = r.get("sort_order", 9999)
        if name not in name_sort_map or current_sort < name_sort_map[name]:
            name_sort_map[name] = current_sort

    sorted_names = sorted(name_sort_map.keys(), key=lambda n: name_sort_map[n])
    df_reorder = pd.DataFrame({"Name": sorted_names})
    df_reorder["Sort Order"] = df_reorder.index

    edited = st.data_editor(df_reorder, use_container_width=True, num_rows="dynamic")

    if st.button("💾 Save Sort Order"):
        for _, row in edited.iterrows():
            name = row["Name"]
            sort = int(row["Sort Order"])
            supabase.table("employee_roles").update({"sort_order": sort}).eq("name", name).execute()
        st.success("✅ Sort order updated.")