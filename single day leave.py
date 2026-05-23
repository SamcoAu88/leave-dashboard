import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date

SHEET_ID = "1cU7k5qS1NJdgWKawxqTvnBy8WxR_V3rVKcyzUaPHsgY"
SCOPES   = ["https://www.googleapis.com/auth/spreadsheets"]

LEAVE_TYPES = [
    "Single Day",
    "Training",
    "Sick Leave",
    "Rostered Leave",
    "Compassionate Leave",
    "Other",
]

def _get_client():
    """Authenticate using Streamlit secrets."""
    try:
        # Try TOML format first
        creds_dict = dict(st.secrets["gcp_service_account"])
    except Exception:
        try:
            # Try raw JSON string format
            import json
            creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDS"])
        except Exception as e:
            st.error(f"Could not load Google credentials: {e}")
            return None

    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_data(ttl=60)   # refresh every 60 seconds
def load_single_day_leave():
    """Load single day leave entries from Google Sheets."""
    try:
        client = _get_client()
        if not client:
            return pd.DataFrame()

        sheet = client.open_by_key(SHEET_ID).sheet1
        records = sheet.get_all_records()

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # Normalise column names
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # Parse date
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["date"])

        return df

    except Exception as e:
        st.warning(f"Could not load single day leave data: {e}")
        return pd.DataFrame()


def add_single_day_entry(name, leave_date, leave_type, notes=""):
    """Append a new entry to Google Sheets."""
    try:
        client = _get_client()
        if not client:
            return False

        sheet = client.open_by_key(SHEET_ID).sheet1

        # Ensure header exists
        existing = sheet.get_all_values()
        if not existing or existing[0] != ["name", "date", "leave_type", "notes"]:
            sheet.insert_row(["name", "date", "leave_type", "notes"], index=1)

        # Append row
        sheet.append_row([
            name,
            leave_date.strftime("%d/%m/%Y") if hasattr(leave_date, "strftime") else str(leave_date),
            leave_type,
            notes,
        ])

        # Clear cache so dashboard refreshes
        load_single_day_leave.clear()
        return True

    except Exception as e:
        st.error(f"Could not save entry: {e}")
        return False


def render_entry_form(staff_names):
    """Render the single day leave entry form in the sidebar or a tab."""
    st.markdown("#### ➕ Add single day leave")

    with st.form("single_day_form", clear_on_submit=True):
        name = st.selectbox("Staff member", sorted(staff_names))
        leave_date = st.date_input("Date", value=date.today(),
                                   min_value=date(2025, 1, 1),
                                   max_value=date(2027, 12, 31))
        leave_type = st.selectbox("Leave type", LEAVE_TYPES)
        notes = st.text_input("Notes (optional)", placeholder="e.g. Doctor appointment")
        submitted = st.form_submit_button("Save entry")

        if submitted:
            if add_single_day_entry(name, leave_date, leave_type, notes):
                st.success(f"✅ Saved: {name} — {leave_date.strftime('%d %b %Y')} ({leave_type})")
            else:
                st.error("Failed to save. Check Google Sheets connection.")
