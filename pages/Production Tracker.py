import streamlit as st
from supabase import create_client
import datetime
import uuid
import tempfile
import os

# Connect to Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Machine Daily Production", layout="wide")
st.title("🛠️ Machine Production Input")

# Load machines and employee roles
machines = supabase.table("machines").select("*").execute().data
employee_roles = supabase.table("employee_roles").select("*").execute().data

# Custom name order
# Load employee roles
employee_roles = supabase.table("employee_roles").select("*").execute().data

# Sort names by minimum sort_order
from collections import defaultdict

grouped_roles = defaultdict(list)
for r in employee_roles:
    r["sort_order"] = int(r.get("sort_order") or 9999)
    grouped_roles[r["name"]].append(r)

sorted_names = sorted(grouped_roles.items(), key=lambda x: min(r["sort_order"] for r in x[1]))
all_employees = [name for name, _ in sorted_names]

# Extract sorted unique employee names
employee_set = set(r["name"] for r in employee_roles)
all_employees = [name for name in custom_name_order if name in employee_set]

# Select date
selected_date = st.date_input("📆 Select Date", datetime.date.today())

# Form to submit one machine at a time
with st.form("machine_production_form"):
    machine_names = {m["name"]: m["id"] for m in machines}
    selected_machine_name = st.selectbox("🛠️ Select Machine", list(machine_names.keys()))
    selected_machine_id = machine_names[selected_machine_name]

    psa_number = st.text_input("📘 PSA# (Blueprint Number)")
    footage = st.number_input("📏 Feet Bored", min_value=0)
    selected_names = st.multiselect("👷 Select Crew", options=all_employees)

    uploaded_photos = st.file_uploader(
        "📸 Upload Photos (optional)", type=["jpg", "jpeg", "png"], accept_multiple_files=True
    )

    submitted = st.form_submit_button("✅ Submit This Machine Log")

    if submitted:
        # 1. Insert machine log
        result = supabase.table("machine_logs").insert({
            "machine_id": selected_machine_id,
            "date": str(selected_date),
            "footage": footage,
            "psa_number": psa_number
        }).execute()

        machine_log_id = result.data[0]["id"]

        # 2. Insert each crew member
        for name in selected_names:
            role_entry = next((r for r in employee_roles if r["name"] == name), None)
            if role_entry:
                supabase.table("machine_employees").insert({
                    "machine_log_id": machine_log_id,
                    "employee_role_id": role_entry["id"]
                }).execute()

        # 3. Upload photos to Supabase Storage
        if uploaded_photos:
            for photo in uploaded_photos:
                unique_name = f"{selected_date}_{psa_number}_{uuid.uuid4()}.jpg"

                # Save temporarily to disk
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(photo.read())
                    tmp_path = tmp.name

                # Upload using path
                res = supabase.storage.from_("machinephotos").upload(
                    path=unique_name,
                    file=tmp_path,
                    file_options={"content-type": photo.type}
                )

                os.remove(tmp_path)  # Clean up temp file

                # Check for upload errors
                if hasattr(res, "status_code") and res.status_code >= 400:
                    st.error(f"❌ Failed to upload {photo.name}")
                else:
                    st.success(f"✅ Uploaded: {photo.name}")

        st.success(f"✅ Submission logged for {selected_machine_name} with PSA#: {psa_number}")