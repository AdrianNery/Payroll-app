# blueprint_live.py
import streamlit as st
import json
from supabase import create_client
import requests
import time

# ---- CONFIG (match what you used above) ----
SUPABASE_URL = "https://YOUR-project-id.supabase.co"
SUPABASE_ANON_KEY = "YOUR_ANON_KEY"
BUCKET_PUBLIC_URL = f"{SUPABASE_URL}/storage/v1/object/public"

# init client
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

st.set_page_config(page_title="Blueprint Live", layout="wide")

st.title("Blueprint Live")

# 1. pick which job to view
jobs_resp = supabase.table("blueprint_jobs").select("*").execute()
jobs = jobs_resp.data or []

if not jobs:
    st.warning("No blueprint jobs found. Run the tile builder script first.")
    st.stop()

job_options = { j["job_name"]: j for j in jobs }
job_name = st.selectbox("Select Job", list(job_options.keys()))
job = job_options[job_name]

job_id = job["id"]
tile_base_path = job["tile_base_path"]
max_zoom = job["max_zoom_level"]

# 2. pull annotations for that job
ann_resp = supabase.table("blueprint_annotations").select("*").eq("job_id", job_id).execute()
annotations = ann_resp.data or []

# shape data for the frontend component
frontend_payload = {
    "tileBaseUrl": f"{BUCKET_PUBLIC_URL}/{tile_base_path}",
    "maxZoom": max_zoom,
    "annotations": annotations,
    # you will also eventually pass current user info for edit permissions
}

# 3. display the interactive map component
# We'll write a placeholder for now:
component_html = f"""
<div id="blueprint-root" style="width:100%;height:80vh;border:1px solid #444;"></div>
<script>
const payload = {json.dumps(frontend_payload)};

// For now, just dump JSON so we can confirm data flows:
document.getElementById('blueprint-root').innerText = JSON.stringify(payload, null, 2);
</script>
"""

st.components.v1.html(component_html, height=700)

st.caption("This is the viewer stub. Next step: replace with Leaflet-based tile layer + SVG overlay.")