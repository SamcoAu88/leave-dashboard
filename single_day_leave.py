import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date

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
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
    except Exception:
        try:
            import json
            creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDS"])
        except Exception as e:
            st.error(f"Could not load Google credentials: {e}")
            return None
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_data(ttl=60)
def load_single_day_leave():
    """Load single day leave from Google Sheets. One row per day."""
    try:
        client = _get_client()
        if not client:
            return pd.DataFrame()

        sheet  = client.open_by_key(SHEET_ID).sheet1
        values = sheet.get_all_values()

        if not values or len(values) < 2:
            return pd.DataFrame()

        # Normalise headers
        headers = [h.strip().lower().replace(" ", "_") for h in values[0]]
        rows    = values[1:]
        df      = pd.DataFrame(rows, columns=headers)

        # Drop completely empty rows
        df = df.replace("", pd.NA).dropna(how="all").reset_index(drop=True)

        # Find date column
        date_col = next((c for c in df.columns if "date" in c), None)
        if not date_col:
            return df

        df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df.rename(columns={date_col: "date"})

        return df

    except Exception as e:
        st.warning(f"Could not load single day leave: {e}")
        return pd.DataFrame()


def add_entry(name, leave_date, leave_type, notes=""):
    """Append one row to Google Sheets."""
    try:
        client = _get_client()
        if not client:
            return False

        sheet = client.open_by_key(SHEET_ID).sheet1

        # Ensure header
        existing = sheet.get_all_values()
        if not existing or existing[0][:4] != ["Name","Date","Leave_type","Notes"]:
            if not existing:
                sheet.append_row(["Name","Date","Leave_type","Notes"])

        sheet.append_row([
            name,
            leave_date.strftime("%d/%m/%Y"),
            leave_type,
            notes,
        ])
        load_single_day_leave.clear()
        return True

    except Exception as e:
        st.error(f"Could not save: {e}")
        return False


def render_entry_form(staff_names):
    """Render the entry form."""
    st.markdown("#### ➕ Add single day leave")

    with st.form("sdl_form", clear_on_submit=True):
        name       = st.selectbox("Staff member", sorted(staff_names))
        leave_date = st.date_input("Date", value=date.today(),
                                   min_value=date(2025, 1, 1),
                                   max_value=date(2027, 12, 31))
        leave_type = st.selectbox("Leave type", LEAVE_TYPES)
        notes      = st.text_input("Notes (optional)",
                                   placeholder="e.g. Doctor appointment")
        submitted  = st.form_submit_button("💾 Save")

        if submitted:
            if add_entry(name, leave_date, leave_type, notes):
                st.success(f"✅ {name} — {leave_date.strftime('%d %b %Y')} ({leave_type})")
            else:
                st.error("Failed to save.")
