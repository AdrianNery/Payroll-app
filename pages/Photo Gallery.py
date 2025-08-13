import streamlit as st
from supabase import create_client
import pandas as pd
import datetime
import pytz
import streamlit as st
from auth_helpers import require_login

# Example: Daily Tracker visible to supervisors & admins
require_login(roles=["supervisor", "admin"])
# --- Local timezone ---
LOCAL_TZ = pytz.timezone("US/Central")

# --- Supabase setup ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Page config ---
st.set_page_config(page_title="📷 Photo Gallery", layout="wide")
st.title("📷 Machine Photo Gallery")

# --- Load view_photos_by_psa ---
photo_view = supabase.table("view_photos_by_psa").select("*").order("date", desc=True).execute().data

if not photo_view:
    st.info("No photos found.")
    st.stop()

# --- Convert to DataFrame for filtering ---
df_photos = pd.DataFrame(photo_view)
df_photos["date"] = pd.to_datetime(df_photos["date"])

# --- PSA and Date filters ---
col1, col2 = st.columns(2)
unique_psas = sorted(df_photos["psa_number"].unique())
selected_psa = col1.selectbox("🔍 Select PSA#", unique_psas)

available_dates = df_photos[df_photos["psa_number"] == selected_psa]["date"].dt.date.unique()
selected_date = col2.selectbox("📅 Select Date", sorted(available_dates, reverse=True))

# --- Filter data for selected PSA and Date ---
filtered = df_photos[(df_photos["psa_number"] == selected_psa) & (df_photos["date"].dt.date == selected_date)]

if filtered.empty or not filtered.iloc[0]["photo_filenames"]:
    st.warning("No photos found for the selected PSA and date.")
    st.stop()

# --- Display gallery ---
st.markdown(f"### 🗂 Photos for PSA: `{selected_psa}` on `{selected_date}`")
photos = filtered.iloc[0]["photo_filenames"]

# --- Display thumbnails in grid ---
cols = st.columns(3)
for i, filename in enumerate(photos):
    with cols[i % 3]:
        image_url = f"{SUPABASE_URL}/storage/v1/object/public/machinephotos/{filename}"
        st.image(image_url, caption=filename.split("/")[-1], use_column_width=True)

st.markdown("---")
st.info(f"Total photos: {len(photos)} • Last uploaded: {filtered.iloc[0]['last_uploaded']}")