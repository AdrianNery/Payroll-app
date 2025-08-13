
import datetime
from collections import defaultdict

import pandas as pd
import pytz
import streamlit as st
from supabase import create_client
from streamlit_sortables import sort_items

st.set_page_config(page_title="Daily Crew Tracker", layout="wide")
st.title("📅 Daily Tracker")

# ---- Local date (US/Central) ----
LOCAL_TZ = pytz.timezone("US/Central")
local_today = datetime.datetime.now(LOCAL_TZ).date()

# ---- Supabase ----
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---- Date picker ----
selected_date = st.date_input("📆 Select Date", local_today)

# ---- Load employee roles safely (ignore company_id) ----
def load_employee_roles(client):
    rows = []
    try:
        rows = (
            client.table("employee_roles")
            .select("id,name,role,daily_rate,sort_order")
            .order("sort_order", desc=False)
            .execute()
        ).data or []
    except Exception:
        try:
            rows = (
                client.table("employee_roles")
                .select("id,name,role,daily_rate,sort_order")
                .execute()
            ).data or []
            st.info("Could not order by sort_order in DB; ordering locally.")
        except Exception:
            rows = (
                client.table("employee_roles")
                .select("id,name,role,daily_rate")
                .execute()
            ).data or []
            for r in rows:
                r["sort_order"] = None

    for r in rows:
        try:
            r["sort_order"] = int(r.get("sort_order")) if r.get("sort_order") is not None else 9999
        except (TypeError, ValueError):
            r["sort_order"] = 9999
    rows.sort(key=lambda r: (r["sort_order"], r["name"]))
    return rows

employee_roles = load_employee_roles(supabase)

# ---- Group roles by name & sort names ----
grouped_roles = defaultdict(list)
for entry in employee_roles:
    grouped_roles[entry["name"]].append(entry)

sorted_names = sorted(
    grouped_roles.items(),
    key=lambda item: min(row["sort_order"] for row in item[1])
)

# -----------------------------
# Technician bulk check-in form
# -----------------------------
tech_data = {}
with st.form("log_form"):
    with st.expander("👷 Technician Check-in", expanded=True):
        for name, role_entries in sorted_names:
            st.markdown(f"**{name}**")
            role_options = [row["role"] for row in role_entries]
            selected_role = st.selectbox(
                f"Role for {name}",
                role_options,
                key=f"{name}_role"
            )
            day_type = st.radio(
                f"{name} worked:",
                ["none", "full", "half"],
                key=f"{name}_daytype",
                horizontal=False
            )
            tech_data[name] = {"selected_role": selected_role, "day_type": day_type}
            st.markdown("---")

    submitted = st.form_submit_button("✅ Save Today's Logs")

    if submitted:
        entries_upserted = 0
        for name, data in tech_data.items():
            if data["day_type"] == "none":
                continue

            matching = next(
                (r for r in grouped_roles[name] if r["role"] == data["selected_role"]),
                None
            )
            if not matching:
                continue

            existing = (
                supabase.table("daily_logs")
                .select("id")
                .eq("employee_role_id", matching["id"])
                .eq("date", str(selected_date))
                .execute()
            )
            if existing.data:
                supabase.table("daily_logs").update(
                    {"day_type": data["day_type"]}
                ).eq("id", existing.data[0]["id"]).execute()
            else:
                supabase.table("daily_logs").insert(
                    {
                        "employee_role_id": matching["id"],
                        "date": str(selected_date),
                        "day_type": data["day_type"],
                    }
                ).execute()

            entries_upserted += 1

        st.success(f"✅ {entries_upserted} logs saved for {selected_date}")

# ----------------
# Manual Entry UI
# ----------------
with st.expander("✍️ Manual Entry"):
    all_names = sorted(set(r["name"] for r in employee_roles))
    name_to_roles = {
        name: sorted(set(row["role"] for row in rows))
        for name, rows in grouped_roles.items()
    }
    distinct_roles = sorted(set(r["role"] for r in employee_roles))

    with st.form("manual_entry_form"):
        manual_date = st.date_input("📅 Date for Manual Entry", local_today, key="manual_date")
        selected_names = st.multiselect("Select Worker(s)", all_names)

        possible_roles = (
            sorted(set(role for n in selected_names for role in name_to_roles.get(n, [])))
            if selected_names else distinct_roles
        )
        selected_role = st.selectbox("Select Role", possible_roles)
        selected_day_type = st.radio("Work Duration", ["full", "half"], horizontal=False)
        manual_submit = st.form_submit_button("➕ Add Log(s)")

        if manual_submit:
            added = 0
            for name in selected_names:
                role_row = next(
                    (r for r in employee_roles if r["name"] == name and r["role"] == selected_role),
                    None
                )
                if not role_row:
                    continue

                exists = (
                    supabase.table("daily_logs")
                    .select("id")
                    .eq("employee_role_id", role_row["id"])
                    .eq("date", str(manual_date))
                    .execute()
                )
                if exists.data:
                    # skip duplicates; switch to update(...) if you want "last write wins"
                    continue

                supabase.table("daily_logs").insert(
                    {
                        "employee_role_id": role_row["id"],
                        "date": str(manual_date),
                        "day_type": selected_day_type,
                    }
                ).execute()
                added += 1

            st.success(f"✅ {added} manual log(s) added.")
            st.rerun()

# -------------------------
# Update / Delete Day Logs
# -------------------------
with st.expander("✏️ Update / Delete Logs"):
    all_logs = (
        supabase.table("daily_logs")
        .select("id,employee_role_id,day_type,date")
        .eq("date", str(selected_date))
        .execute()
        .data
    )

    if all_logs:
        role_by_id = {r["id"]: r for r in employee_roles}
        logs_with_names = []
        for log in all_logs:
            role = role_by_id.get(log["employee_role_id"])
            if not role:
                continue
            logs_with_names.append(
                {
                    "Log ID": log["id"],
                    "Name": role["name"],
                    "Role": role["role"],
                    "Day Type": log["day_type"],
                }
            )

        df_edit = pd.DataFrame(logs_with_names)
        selected_row = st.selectbox(
            "Select Log to Edit",
            df_edit.index,
            format_func=lambda i: f"{df_edit.iloc[i]['Name']} • {df_edit.iloc[i]['Role']} • {df_edit.iloc[i]['Day Type']}"
        )
        selected_log = df_edit.iloc[selected_row]

        new_day_type = st.radio(
            "New Day Type",
            ["full", "half"],
            index=["full", "half"].index(selected_log["Day Type"])
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔁 Update Log"):
                supabase.table("daily_logs").update(
                    {"day_type": new_day_type}
                ).eq("id", selected_log["Log ID"]).execute()
                st.success("✅ Log updated.")
                st.rerun()
        with col2:
            if st.button("🗑 Delete Log"):
                supabase.table("daily_logs").delete().eq("id", selected_log["Log ID"]).execute()
                st.warning("⚠️ Log deleted.")
                st.rerun()
    else:
        st.info("No logs available to update or delete for this date.")

# -------------
# Show the day
# -------------
st.header("📋 Today's Work Log")
logs = (
    supabase.table("daily_logs")
    .select("id,employee_role_id,day_type,date")
    .eq("date", str(selected_date))
    .execute()
    .data
)

if logs:
    role_by_id = {r["id"]: r for r in employee_roles}
    display = []
    for log in logs:
        role = role_by_id.get(log["employee_role_id"])
        if not role:
            continue
        rate = float(role["daily_rate"] or 0)
        pay = rate if log["day_type"] == "full" else rate / 2
        display.append(
            {
                "Name": role["name"],
                "Role": role["role"],
                "Day Type": log["day_type"],
                "Daily Pay": f"${pay:.2f}",
            }
        )
    st.dataframe(pd.DataFrame(display), use_container_width=True)
else:
    st.info("No logs found for this date.")

# ----------------------------
# Add / Remove / Reorder list
# ----------------------------
st.header("➕ Add / Remove / Reorder")
action = st.radio("Choose Action", ["Add", "Remove", "Reorder"], horizontal=True)

if action == "Add":
    with st.form("add_worker_form"):
        new_name = st.text_input("👤 Name")
        distinct_roles = sorted(set(r["role"] for r in employee_roles))
        new_role = st.selectbox("👷 Role", distinct_roles or ["Driller", "Locator", "Labor"])
        new_rate = st.number_input("💰 Daily Pay", min_value=0.0, step=1.0)
        submit_add = st.form_submit_button("✅ Add Tech")

        if submit_add:
            current_sorts = [int(r.get("sort_order") or 0) for r in employee_roles if r.get("sort_order") is not None]
            next_sort_order = (max(current_sorts) if current_sorts else 0) + 1

            supabase.table("employee_roles").insert(
                {
                    "name": new_name,
                    "role": new_role,
                    "daily_rate": new_rate,
                    "sort_order": next_sort_order,
                }
            ).execute()
            st.success(f"{new_name} added to bottom of list.")
            st.rerun()

elif action == "Remove":
    with st.form("remove_worker_form"):
        all_names = sorted(set(r["name"] for r in employee_roles))
        name_to_remove = st.selectbox("👤 Select name", all_names)
        confirm = st.checkbox("⚠️ Confirm removal of all roles for this name")
        submit_remove = st.form_submit_button("🗑 Remove Tech")
        if submit_remove and confirm:
            supabase.table("employee_roles").delete().eq("name", name_to_remove).execute()
            st.success(f"{name_to_remove} removed.")
            st.rerun()

elif action == "Reorder":
    st.subheader("📥 Drag and Drop")
    name_sort_map = {}
    for r in employee_roles:
        name = r["name"]
        sort = int(r.get("sort_order") or 9999)
        if name not in name_sort_map or sort < name_sort_map[name]:
            name_sort_map[name] = sort

    sorted_names_only = [name for name, _ in sorted(name_sort_map.items(), key=lambda x: x[1])]
    if "drag_order" not in st.session_state:
        st.session_state.drag_order = sorted_names_only

    new_order = sort_items(st.session_state.drag_order, direction="vertical", key="employee_sort")

    if st.button("💾 Save Order"):
        for idx, name in enumerate(new_order, start=1):  # 1-based index
            supabase.table("employee_roles").update({"sort_order": idx}).eq("name", name).execute()
        st.session_state.drag_order = new_order
        st.success("✅ Sort order updated.")
        st.rerun()