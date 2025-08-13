# lib/auth.py
import streamlit as st
from supabase import create_client

def get_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def load_profile(supabase, user_id: str):
    res = supabase.table("user_profiles").select("*").eq("user_id", user_id).single().execute()
    return (res.data or {}) if hasattr(res, "data") else {}

def is_logged_in():
    return st.session_state.get("user") is not None

def current_role():
    return st.session_state.get("role")

def login(email: str, password: str):
    supabase = get_client()
    auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
    user = getattr(auth_res, "user", None)
    if not user:
        return False, "Invalid email or password."

    profile = load_profile(supabase, user.id)
    if not profile or not profile.get("is_approved", False):
        # Immediately sign out if not approved
        supabase.auth.sign_out()
        return False, "Your account is pending approval."

    st.session_state.user = {"id": user.id, "email": user.email}
    st.session_state.role = profile.get("role", "tech")
    return True, None

def logout():
    supabase = get_client()
    supabase.auth.sign_out()
    for k in ("user", "role"):
        st.session_state.pop(k, None)

def require_login(allowed_roles=None):
    """
    Call at the very top of each page file.
    If not logged in or role not allowed, stop the script.
    """
    if not is_logged_in():
        st.switch_page("streamlit_app.py")  # send to login
    if allowed_roles and current_role() not in allowed_roles:
        st.error("You don’t have access to this page.")
        st.stop()