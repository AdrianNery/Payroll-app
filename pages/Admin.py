import streamlit as st
from auth_helpers import get_client, require_login

require_login(["admin"])
sb = get_client()

st.title("👑 Admin – User Approvals")

# List pending users
pending = sb.table("profiles").select("*").eq("approved", False).execute().data
if pending:
    for p in pending:
        with st.form(f"approve_{p['id']}"):
            st.write(f"**{p['email']}** — requested access")
            role = st.selectbox("Role", ["tech", "supervisor", "admin"], index=0, key=f"role_{p['id']}")
            approve = st.form_submit_button("Approve")
            if approve:
                sb.table("profiles").update({"approved": True, "role": role}).eq("id", p["id"]).execute()
                st.success(f"Approved {p['email']} as {role}")
                st.experimental_rerun()
else:
    st.info("No pending approvals.")