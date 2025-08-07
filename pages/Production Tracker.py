import streamlit as st
from supabase import create_client
import datetime
import uuid
import tempfile
import os
import pytz
from collections import defaultdict

# --- Timezone setup ---
LOCAL_TZ = pytz.timezone("US/Central")
local_today = datetime.datetime.now(LOCAL_TZ).date()

# --- Connect to Supabase ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Machine Daily Production", layout="wide")
st.title("🛠️ Machine Production Input")

# --- Load machines & employees ---
machines = supabase.table("machines").select("*").execute().data
employee_roles = supabase.table("employee_roles").select("*").execute().data

# --- Sort employees by sort_order ---
grouped_roles = defaultdict(list)
for r in employee_roles:
    r["sort_order"] = int(r.get("sort_order") or 9999)
    grouped_roles[r["name"]].append(r)

sorted_names = sorted(grouped_roles.items(), key=lambda x: min(r["sort_order"] for r in x[1]))
all_employees = [name for name, _ in sorted_names]

# --- Add "Fiber Pulling" to the list of selectable machines ---
machine_names = {m["name"]: m["id"] for m in machines}

# --- Select date ---
with st.expander("📆 Select Date"):
    selected_date = st.date_input("Choose Date", local_today)

# --- Production entry form ---
with st.expander("📝 Submit New Production Log", expanded=True):
    with st.form("machine_production_form"):
        selected_machine_name = st.selectbox("🛠️ Select Machine / Operation", list(machine_names.keys()))
        selected_machine_id = machine_names[selected_machine_name]

        psa_number = st.text_input("📘 PSA# (Blueprint Number)")
        footage = st.number_input("📏 Feet Bored / Pulled", min_value=0)
        selected_names = st.multiselect("👷 Select Crew", options=all_employees)

        uploaded_photos = st.file_uploader(
            "📸 Upload Photos (optional)", type=["jpg", "jpeg", "png"], accept_multiple_files=True
        )

        submitted = st.form_submit_button("✅ Submit This Production Log")

        if submitted:
            # 1. Insert into machine_logs
            if selected_machine_id == "fiber_pulling":
                result = supabase.table("machine_logs").insert({
                    "machine_id": None,
                    "operation_type": "Fiber Pulling",
                    "date": str(selected_date),
                    "footage": footage,
                    "psa_number": psa_number
                }).execute()
            else:
                result = supabase.table("machine_logs").insert({
                    "machine_id": selected_machine_id,
                    "date": str(selected_date),
                    "footage": footage,
                    "psa_number": psa_number
                }).execute()

            machine_log_id = result.data[0]["id"]

            # 2. Insert crew members
            for name in selected_names:
                role_entry = next((r for r in employee_roles if r["name"] == name), None)
                if role_entry:
                    supabase.table("machine_employees").insert({
                        "machine_log_id": machine_log_id,
                        "employee_role_id": role_entry["id"]
                    }).execute()

            # 3. Upload photos
            if uploaded_photos:
                for photo in uploaded_photos:
                    unique_name = f"{selected_date}_{psa_number}_{uuid.uuid4()}.jpg"

                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(photo.read())
                        tmp_path = tmp.name

                    res = supabase.storage.from_("machinephotos").upload(
                        path=unique_name,
                        file=tmp_path,
                        file_options={"content-type": photo.type}
                    )

                    os.remove(tmp_path)

                    if hasattr(res, "status_code") and res.status_code >= 400:
                        st.error(f"❌ Failed to upload {photo.name}")
                    else:
                        st.success(f"✅ Uploaded: {photo.name}")

            st.success(f"✅ Production log saved for {selected_machine_name} with PSA#: {psa_number}")