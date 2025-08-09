import streamlit as st
from supabase import create_client
from datetime import datetime

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Login", layout="centered")

if "user" not in st.session_state:
    st.session_state.user = None

st.title("🔐 Field Tracker Access")

# ---------------------
# LOGIN FORM
# ---------------------
with st.expander("🔑 Login"):
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login"):
        try:
            auth = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            # Check if user is approved
            approved = supabase.table("user_requests").select("*") \
                .eq("email", auth.user.email).eq("approved", True).execute().data

            if not approved:
                st.error("🚫 Account not approved yet.")
            else:
                st.session_state.user = auth.user
                st.success("✅ Login successful!")
                st.rerun()

        except Exception as e:
            st.error("❌ Login failed. Check credentials.")

# ---------------------
# REGISTRATION FORM
# ---------------------
with st.expander("📝 Request Access"):
    reg_name = st.text_input("Full Name", key="reg_name")
    reg_email = st.text_input("Email", key="reg_email")
    reg_password = st.text_input("Password", type="password", key="reg_password")
    reg_reason = st.text_area("Why do you need access?", key="reg_reason")

    if st.button("Request Account"):
        # 1. Create Supabase auth user
        try:
            supabase.auth.sign_up({
                "email": reg_email,
                "password": reg_password
            })

            # 2. Log request in `user_requests` table
            supabase.table("user_requests").insert({
                "email": reg_email,
                "name": reg_name,
                "reason": reg_reason
            }).execute()

            st.success("✅ Request submitted! You’ll be notified once approved.")
        except Exception as e:
            st.error("⚠️ Account request failed (possibly already exists).")
            