import datetime
from collections import defaultdict

import pandas as pd
import pytz
import streamlit as st
from supabase import create_client
from postgrest.exceptions import APIError
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

# ---------------------------
# Helpers: load & sort people
# ---------------------------
def load_employee_roles(client):
    """Return rows from employee_roles with normalized sort_order and sane fallback ordering."""
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

    # normalize and local sort fallback (by per-row sort_order then name)
    for r in rows:
        try:
            r["sort_order"] = int(r.get("sort_order")) if r.get("sort_order") is not None else 9999
        except (TypeError, ValueError):
            r["sort_order"] = 9999
    rows.sort(key=lambda r: (r["sort_order"], r["name"]))
    return rows

def compute_name_sort_map(grouped_roles):
    """Map each name -> the minimum sort_order across that name's roles."""
    name_sort_map = {}
    for name, rows in grouped_roles.items():
        min_so = min((r.get("sort_order") if r.get("sort_order") is not None else 9999) for r in rows)
        name_sort_map[name] = min_so
    return name_sort_map

def get_next_sort_order(name_sort_map):
    """Return max(sort_order)+1, or 1 if empty."""
    return (max(name_sort_map.values()) + 1) if name_sort_map else 1

# initial load
employee_roles = load_employee_roles(supabase)

# ---- Group roles by name ----
grouped_roles = defaultdict(list)
for entry in employee_roles:
    grouped_roles[entry["name"]].append(entry)

# ---- ORDER NAMES BY THEIR sort_order (not alphabetically) ----
name_sort_map = compute_name_sort_map(grouped_roles)
all_names = [name for name, _ in sorted(name_sort_map.items(), key=lambda x: x[1])]

# ---------------------------
# Date picker
# ---------------------------
selected_date = st.date_input("📆 Select Date", local_today)

# ------------------------------------------------------
# 1) Enter today's logs for each worker (bulk save form)
# ------------------------------------------------------
st.header("📝 Enter Today’s Logs")

with st.form("today_logs_form"):
    tech_data = {}

    # Single column to preserve order on phones (no wrapping)
    for name in all_names:
        with st.container():
            st.subheader(name)
            roles_for_name = [r["role"] for r in grouped_roles[name]]
            selected_role = st.selectbox(
                "",  # compact label
                roles_for_name,
                key=f"{name}_role"
            )
            day_type = st.radio(
                "Day type",
                ["none", "full", "half"],
                key=f"{name}_daytype",
                horizontal=True
            )
            tech_data[name] = {"selected_role": selected_role, "day_type": day_type}
            st.divider()

    submitted = st.form_submit_button("✅ Save Today's Logs")

    if submitted:
        entries_upserted = 0
        try:
            for name, data in tech_data.items():
                if data["day_type"] == "none":
                    continue

                matching = next(
                    (r for r in grouped_roles[name] if r["role"] == data["selected_role"]),
                    None
                )
                if not matching:
                    continue

                payload = {
                    "employee_role_id": matching["id"],
                    "date": selected_date.isoformat(),
                    "day_type": data["day_type"],
                }

                supabase.table("daily_logs").upsert(
                    payload, on_conflict="employee_role_id,date"
                ).execute()
                entries_upserted += 1

            st.success(f"✅ {entries_upserted} logs saved for {selected_date}")
        except APIError as e:
            err = e.args[0] if e.args and isinstance(e.args[0], dict) else {"message": str(e)}
            st.error(f"Supabase error: {err.get('message')}")
            if err.get("details"):
                st.info(err["details"])
            if err.get("hint"):
                st.caption(err["hint"])
            raise

# -------------------------------------
# 2) Manual add of logs for any date(s)
# -------------------------------------
st.header("🧩 Add Log(s) Manually")

# Build role lists for multiselect convenience
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
    selected_day_type = st.radio("Work Duration", ["full", "half"], horizontal=True)
    manual_submit = st.form_submit_button("➕ Add Log(s)")

    if manual_submit:
        try:
            added = 0
            for name in selected_names:
                role_row = next(
                    (r for r in employee_roles if r["name"] == name and r["role"] == selected_role),
                    None
                )
                if not role_row:
                    continue

                payload = {
                    "employee_role_id": role_row["id"],
                    "date": manual_date.isoformat(),
                    "day_type": selected_day_type,
                }

                supabase.table("daily_logs").upsert(
                    payload, on_conflict="employee_role_id,date"
                ).execute()
                added += 1

            st.success(f"✅ {added} manual log(s) added.")
            st.rerun()
        except APIError as e:
            err = e.args[0] if e.args and isinstance(e.args[0], dict) else {"message": str(e)}
            st.error(f"Supabase error: {err.get('message')}")
            if err.get("details"):
                st.info(err["details"])
            if err.get("hint"):
                st.caption(err["hint"])
            raise

# -------------------------
# 3) Update / Delete Day Logs
# -------------------------
with st.expander("✏️ Update / Delete Logs"):
    all_logs = (
        supabase.table("daily_logs")
        .select("id,employee_role_id,day_type,date")
        .eq("date", selected_date.isoformat())
        .execute()
    ).data or []

    # Build a mapping for quick name/role lookup
    role_map = {r["id"]: r for r in employee_roles}
    display_rows = []
    for log in all_logs:
        role_row = role_map.get(log["employee_role_id"])
        if not role_row:
            continue
        display_rows.append(
            {
                "id": log["id"],
                "name": role_row["name"],
                "role": role_row["role"],
                "day_type": log["day_type"],
                "sort_order": role_row.get("sort_order", 9999),
            }
        )

    # ORDER the update list by the same person-level sort
    display_rows.sort(key=lambda x: (name_sort_map.get(x["name"], 9999), x["name"], x["role"]))

    if display_rows:
        df = pd.DataFrame([{k: v for k, v in row.items() if k != "sort_order"} for row in display_rows])
        st.dataframe(df, hide_index=True, use_container_width=True)

        # Simple per-row editor
        for row in display_rows:
            col1, col2, col3 = st.columns([2,2,1])
            with col1:
                st.text_input("Name", row["name"], disabled=True, key=f"upd_name_{row['id']}")
            with col2:
                new_day = st.selectbox(
                    "Day Type",
                    ["full", "half", "off"],
                    index=["full","half","off"].index(row["day_type"]) if row["day_type"] in ["full","half","off"] else 0,
                    key=f"upd_day_{row['id']}"
                )
            with col3:
                if st.button("Update", key=f"btn_upd_{row['id']}"):
                    try:
                        supabase.table("daily_logs").update(
                            {"day_type": new_day}
                        ).eq("id", row["id"]).execute()
                        st.success("Updated.")
                        st.rerun()
                    except APIError as e:
                        err = e.args[0] if e.args and isinstance(e.args[0], dict) else {"message": str(e)}
                        st.error(f"Supabase error: {err.get('message')}")
                        if err.get("details"):
                            st.info(err["details"])
                        if err.get("hint"):
                            st.caption(err["hint"])

        st.divider()
        for row in display_rows:
            if st.button(f"🗑️ Delete {row['name']} ({row['role']})", key=f"btn_del_{row['id']}"):
                try:
                    supabase.table("daily_logs").delete().eq("id", row["id"]).execute()
                    st.success("Deleted.")
                    st.rerun()
                except APIError as e:
                    err = e.args[0] if e.args and isinstance(e.args[0], dict) else {"message": str(e)}
                    st.error(f"Supabase error: {err.get('message')}")
                    if err.get("details"):
                        st.info(err["details"])
                    if err.get("hint"):
                        st.caption(err["hint"])
    else:
        st.info("No logs available to update or delete for this date.")

# --------------------------
# 4) Manage workers & roles
# --------------------------
st.header("👤 Manage Workers & Roles")

with st.expander("➕ Add Worker / Role"):
    with st.form("add_worker_form"):
        new_name = st.text_input("Name")
        new_role = st.text_input("Role")
        new_daily_rate = st.number_input("Daily Rate", min_value=0.0, step=1.0, format="%.2f")
        add_btn = st.form_submit_button("Add")

        if add_btn:
            if not new_name or not new_role:
                st.error("Please provide both a name and a role.")
            else:
                try:
                    # If name exists, inherit that name's sort_order; else append to bottom
                    if new_name in name_sort_map:
                        sort_for_name = name_sort_map[new_name]
                    else:
                        sort_for_name = get_next_sort_order(name_sort_map)

                    payload = {
                        "name": new_name,
                        "role": new_role,
                        "daily_rate": new_daily_rate,
                        "sort_order": sort_for_name,
                    }
                    res = supabase.table("employee_roles").insert(payload).execute()
                    if isinstance(res.data, list) and res.data:
                        st.success(f"Added {new_name} ({new_role}).")
                    else:
                        st.success("Added.")

                    st.rerun()
                except APIError as e:
                    err = e.args[0] if e.args and isinstance(e.args[0], dict) else {"message": str(e)}
                    st.error(f"Supabase error: {err.get('message')}")
                    if err.get("details"):
                        st.info(err["details"])
                    if err.get("hint"):
                        st.caption(err["hint"])
                except Exception as e:
                    st.error(f"Unexpected error: {e}")

with st.expander("🗑️ Delete Worker / Role"):
    # Build choices for easy selection
    name_choices = [n for n in all_names]
    # Flatten rows for specific-role deletion
    role_rows_display = [f"{r['name']} — {r['role']} (id={r['id']})" for r in employee_roles]
    id_by_display = {f"{r['name']} — {r['role']} (id={r['id']})": r["id"] for r in employee_roles}

    tab_by_name, tab_by_row = st.tabs(["Delete All Roles by Name", "Delete Specific Role Row"])

    with tab_by_name:
        with st.form("del_by_name_form"):
            del_name = st.selectbox("Name", name_choices) if name_choices else st.text_input("Name")
            del_btn = st.form_submit_button("Delete All Roles for Name")
            if del_btn and del_name:
                try:
                    supabase.table("employee_roles").delete().eq("name", del_name).execute()
                    st.success(f"Deleted all roles for {del_name}.")
                    st.rerun()
                except APIError as e:
                    err = e.args[0] if e.args and isinstance(e.args[0], dict) else {"message": str(e)}
                    st.error(f"Supabase error: {err.get('message')}")
                    if err.get("details"):
                        st.info(err["details"])
                    if err.get("hint"):
                        st.caption(err["hint"])

    with tab_by_row:
        with st.form("del_by_row_form"):
            del_row_display = st.selectbox("Select Role Row", role_rows_display) if role_rows_display else ""
            del_row_btn = st.form_submit_button("Delete Selected Role Row")
            if del_row_btn and del_row_display:
                try:
                    del_id = id_by_display[del_row_display]
                    supabase.table("employee_roles").delete().eq("id", del_id).execute()
                    st.success("Deleted the selected role row.")
                    st.rerun()
                except APIError as e:
                    err = e.args[0] if e.args and isinstance(e.args[0], dict) else {"message": str(e)}
                    st.error(f"Supabase error: {err.get('message')}")
                    if err.get("details"):
                        st.info(err["details"])
                    if err.get("hint"):
                        st.caption(err["hint"])

# -----------------------------------
# 5) Drag-to-sort employees by NAME
# -----------------------------------
with st.expander("🔀 Sort Employee Display Order (by Name)"):
    sorted_names_only = [name for name, _ in sorted(name_sort_map.items(), key=lambda x: x[1])]
    if "drag_order" not in st.session_state:
        st.session_state.drag_order = sorted_names_only

    new_order = sort_items(st.session_state.drag_order, direction="vertical", key="employee_sort")

    if st.button("💾 Save Order"):
        try:
            for idx, name in enumerate(new_order, start=1):  # 1-based order
                # IMPORTANT: update ALL rows for that name to keep same sort across roles
                supabase.table("employee_roles").update({"sort_order": idx}).eq("name", name).execute()
            st.session_state.drag_order = new_order
            st.success("✅ Sort order updated.")
            st.rerun()
        except APIError as e:
            err = e.args[0] if e.args and isinstance(e.args[0], dict) else {"message": str(e)}
            st.error(f"Supabase error: {err.get('message')}")
            if err.get("details"):
                st.info(err["details"])
            if err.get("hint"):
                st.caption(err["hint"])

# -------------
# Show the day
# -------------
st.header("📋 Today's Work Log")
logs = (
    supabase.table("daily_logs")
    .select("id,employee_role_id,day_type,date")
    .eq("date", selected_date.isoformat())
    .execute()
).data

role_map = {r["id"]: r for r in employee_roles}
rows = []
for log in (logs or []):
    role_row = role_map.get(log["employee_role_id"])
    if role_row:
        rows.append(
            {
                "Name": role_row["name"],
                "Role": role_row["role"],
                "Day Type": log["day_type"],
                "Date": log["date"],
                "sort_order": role_row.get("sort_order", 9999),
            }
        )

# ORDER the display by person-level sort
rows.sort(key=lambda x: (name_sort_map.get(x["Name"], 9999), x["Name"], x["Role"]))

if rows:
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "sort_order"} for r in rows])
    st.dataframe(df, hide_index=True, use_container_width=True)
else:
    st.info("No entries yet for the selected date.")
