import streamlit as st
from supabase import create_client
import pandas as pd
import datetime
import pytz

# --- Local Timezone ---
LOCAL_TZ = pytz.timezone("US/Central")

# --- Supabase Connection ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Revenue Tracker", layout="wide")
st.markdown("""
    <style>
        .block-container {
            padding: 1rem 1rem 1rem 1rem;
            max-width: 100%;
        }
        .stButton>button {
            width: 100%;
        }
        .stTextInput>div>input, .stNumberInput>div>input {
            font-size: 1.1rem;
        }
        .stSelectbox>div>div {
            font-size: 1.1rem;
        }
        .stRadio>div>label {
            font-size: 1.1rem;
        }
    </style>
""", unsafe_allow_html=True)

st.title("💰 Revenue Tracker")

# --- Add New Contract Form ---
with st.form("add_contract_form"):
    st.subheader("➕ Add New Contract / PSA")
    psa_number = st.text_input("📘 PSA Number")
    company_name = st.text_input("🏢 Company Name")
    pay_rate = st.number_input("💵 Pay Rate (per foot)", min_value=0.0, step=0.01)

    submit_contract = st.form_submit_button("✅ Add Contract")

    if submit_contract:
        if psa_number and company_name and pay_rate > 0:
            res = supabase.table("psa_rates").insert({
                "psa_number": psa_number.strip(),
                "company_name": company_name.strip(),
                "pay_rate": pay_rate,
                "created_at": datetime.datetime.now(LOCAL_TZ).isoformat()
            }).execute()

            if res.data:
                st.success(f"✅ Contract for PSA {psa_number} added.")
            else:
                st.error("❌ Failed to add contract. PSA number might already exist.")
        else:
            st.warning("⚠️ Please fill all fields.")

st.markdown("---")

# --- View All Contracts ---
st.subheader("📋 Existing Contracts")
contracts = supabase.table("psa_rates").select("*").order("created_at", desc=True).execute().data

if contracts:
    df = pd.DataFrame(contracts)
    st.dataframe(df)

    st.subheader("✏️ Edit Contract")
    psa_list = [c["psa_number"] for c in contracts]
    selected_psa = st.selectbox("Select PSA to Edit", psa_list)

    if selected_psa:
        selected_contract = next(c for c in contracts if c["psa_number"] == selected_psa)
        new_company = st.text_input("🏢 Company Name", value=selected_contract["company_name"])
        new_rate = st.number_input("💵 Pay Rate (per foot)", min_value=0.0, step=0.01, value=float(selected_contract["pay_rate"]))

        if st.button("💾 Save Changes"):
            supabase.table("psa_rates").update({
                "company_name": new_company,
                "pay_rate": new_rate
            }).eq("psa_number", selected_psa).execute()
            st.success("✅ Contract updated.")
            st.rerun()
else:
    st.info("No contracts found.")