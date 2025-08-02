import streamlit as st
from supabase import create_client
import datetime

# Connect to Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Machine Daily Production", layout="wide")
st.title("🛠️ Machine Production Input")

# Get data from Supabase
machines = supabase.table("machines").select("*").execute().data
employee_roles = supabase.table("employee_roles").select("*").execute().data
# Custom name order
custom_name_order = [
    "Lica", "Kelvin", "Mara", "Dany", "Mainor", "Gamaliel", "Chepe", "Devora",
    "Fortino", "Abelardo", "William", "Edgar", "Angela", "Martin", "Jose Luis",
    "Wicho", "Abel", "Jairo", "Robert", "Frankly", "Rigo", "Adrian", "Paolo", "Rigoberto"
]
# Extract full employee list
# Extract unique employee names from database
employee_set = set(r["name"] for r in employee_roles)

# Sort using custom order
all_employees = [name for name in custom_name_order if name in employee_set]

# Select the date
selected_date = st.date_input("Select Date", datetime.date.today())

# Store machine logs to batch insert
machine_log_entries = []

with st.form("machine_production_form"):
    for machine in machines:
        st.subheader(f"🔧 {machine['name']}")
        
        # Input footage bored
        footage = st.number_input(
            f"Feet Bored by {machine['name']}", min_value=0, key=f"{machine['id']}_footage"
        )

        # Select crew
        selected_names = st.multiselect(
            f"👷‍♂️ Select Workers for {machine['name']}",
            options=all_employees,
            key=f"{machine['id']}_crew"
        )

        machine_log_entries.append({
            "machine_id": machine["id"],
            "footage": footage,
            "crew_names": selected_names
        })

    submitted = st.form_submit_button("✅ Submit Production Logs")

    if submitted:
        for entry in machine_log_entries:
            # Insert machine log
            result = supabase.table("machine_logs").insert({
                "machine_id": entry["machine_id"],
                "date": str(selected_date),
                "footage": entry["footage"]
            }).execute()
            
            machine_log_id = result.data[0]["id"]
            crew_names = entry["crew_names"]

            for name in crew_names:
                # Get all role entries for the selected employee
                roles = [r for r in employee_roles if r["name"] == name]
                if roles:
                    # Pick the first role by default (you could allow selection later)
                    role_entry = roles[0]

                    # Insert into daily_logs (defaulting to full day)
                    supabase.table("daily_logs").insert({
                        "employee_role_id": role_entry["id"],
                        "date": str(selected_date),
                        "day_type": "full"  # default; change if needed
                    }).execute()

                    # Link to machine_employees
                    supabase.table("machine_employees").insert({
                        "machine_log_id": machine_log_id,
                        "employee_role_id": role_entry["id"]
                    }).execute()

        st.success("✅ All machine production logs submitted successfully.")