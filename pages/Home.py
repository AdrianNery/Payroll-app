# streamlit_app.py
import streamlit as st
from auth_helpers import login, logout, is_logged_in, current_role

st.set_page_config(page_title="App Login", layout="wide")

def login_view():
    st.title("🔐 Sign in")
    with st.form("login_form"):
        email = st.text_input("Email", autocomplete="email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
        if submitted:
            ok, err = login(email, password)
            if ok:
                st.success("Welcome!")
                st.experimental_rerun()
            else:
                st.error(err or "Login failed.")

def home_view():
    st.title("Welcome 👋")
    st.caption(f"Role: {current_role()}")
    st.write("Choose a page from the sidebar.")
    if st.button("Log out"):
        logout()
        st.experimental_rerun()

# Always show a clean sidebar tailored by role
def sidebar_nav():
    role = current_role()
    st.sidebar.markdown("## Navigation")
    # Everyone can see Daily & Production
    st.sidebar.page_link("pages/1_Daily_Tracker.py", label="Daily Tracker")
    st.sidebar.page_link("pages/2_Production_Tracker.py", label="Production Tracker")
    # Supervisors & Admin
    if role in ("supervisor", "admin"):
        st.sidebar.page_link("pages/4_Revenue_Tracker.py", label="Revenue Tracker")
        st.sidebar.page_link("pages/5_Photo_Gallery.py", label="Photo Gallery")
    # Admin only
    if role == "admin":
        st.sidebar.page_link("pages/3_Financial_Overview.py", label="Financial Overview")

    st.sidebar.divider()
    if st.sidebar.button("Log out"):
        logout()
        st.experimental_rerun()

# Router:
if not is_logged_in():
    login_view()
else:
    sidebar_nav()
    home_view()