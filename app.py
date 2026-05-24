import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import tempfile

from single_day_leave import load_single_day_leave, render_entry_form
from data_parser import (
    parse_excel, build_leave_df, get_all_weeks, get_week_labels,
    concurrent_by_week, LEAVE_COLORS, QLD_PUBLIC_HOLIDAYS_2026
)

st.set_page_config(
    page_title="Leave Dashboard — Stafford DC",
    page_icon="📅",
    layout="wide",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    div[data-testid="stSidebar"] { background: #1a1a2e; }
    div[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    div[data-testid="stSidebar"] .stSelectbox label,
    div[data-testid="stSidebar"] .stMultiselect label { color: #adb5bd !important; font-size: 0.8rem; }
    h1 { font-size: 1.6rem !important; }
    h2 { font-size: 1.2rem !important; }
    h3 { font-size: 1rem !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_data(filepath):
    staff_list = parse_excel(filepath)
    df = build_leave_df(staff_list)
    return staff_list, df


DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leave_data.xlsx")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📅 Leave Dashboard")
    st.markdown("**Brisbane Central — Stafford DC**")
    st.divider()

    uploaded = st.file_uploader("Upload Excel file", type=["xlsx"])
    if uploaded:
        tmp_path = os.path.join(tempfile.gettempdir(), "leave_upload.xlsx")
        with open(tmp_path, "wb") as f:
            f.write(uploaded.read())
        DATA_FILE = tmp_path
        st.cache_data.clear()
        st.success("File loaded!")

    st.divider()
    st.markdown("#### Filters")

    # If default file doesn't exist, require upload
    if not os.path.exists(DATA_FILE) and DATA_FILE == os.path.join(os.path.dirname(os.path.abspath(__file__)), "leave_data.xlsx"):
        st.warning("Please upload your leave Excel file above to get started.")
        st.stop()

    staff_list, df_all = load_data(DATA_FILE)

    all_weeks   = get_all_weeks()

    # Extend weeks 52 weeks beyond last data week for future sliding
    last_wk = all_weeks[-1]
    extra_weeks = []
    for i in range(1, 53):
        extra_wk = last_wk + timedelta(weeks=i)
        extra_weeks.append(extra_wk)
    all_weeks_extended = all_weeks + extra_weeks

    week_labels = get_week_labels(all_weeks_extended)
    week_map    = dict(zip(week_labels, all_weeks_extended))

    all_months = []
    seen_m = set()
    for wk in all_weeks:
        key = wk.strftime("%b %Y")
        if key not in seen_m:
            all_months.append(key)
            seen_m.add(key)

    # Extend all_months to cover 13 months beyond the last data month
    # so slider can reach into the future
    last_data_dt = pd.to_datetime("01 " + all_months[-1], dayfirst=True)
    extra_dt = last_data_dt
    for _ in range(14):
        extra_dt = extra_dt + pd.DateOffset(months=1)
        key = extra_dt.strftime("%b %Y")
        if key not in seen_m:
            all_months.append(key)
            seen_m.add(key)

    # ── Time period ──
    period_type = st.radio("Time period", ["Monthly", "Weekly", "Daily"], horizontal=True, label_visibility="collapsed")
    st.caption("Time period")

    if period_type == "Monthly":
        # Slider = start month only, always show 13 months from that point
        from datetime import date
        today_m = date.today().replace(day=1)
        default_start = (today_m - pd.DateOffset(months=1)).strftime("%b %Y")
        default_start = default_start if default_start in all_months else all_months[0]

        start_month = st.select_slider(
            "Start month",
            options=all_months,
            value=default_start,
            label_visibility="collapsed",
        )
        # Always show exactly 13 months from selected start
        i0 = all_months.index(start_month)
        month_filter = all_months[i0:i0 + 13]
        # Pad to 13 if not enough months in list (shouldn't happen with 14 extra)
        while len(month_filter) < 13:
            last = pd.to_datetime("01 " + month_filter[-1], dayfirst=True)
            month_filter.append((last + pd.DateOffset(months=1)).strftime("%b %Y"))
        week_filter = None
        st.caption(f"📅 {month_filter[0]} → {month_filter[-1]}  (13 months)")
    elif period_type == "Weekly":
        default_week_start = week_labels[0]
        start_week = st.select_slider(
            "Start week",
            options=week_labels,
            value=default_week_start,
            label_visibility="collapsed",
        )
        i0 = week_labels.index(start_week)
        week_filter  = week_labels[i0:i0 + 52]
        month_filter = None
        end_label = week_filter[-1] if week_filter else "—"
        st.caption(f"📅 {start_week} → {end_label}  (52 weeks)")
    else:
        # Daily mode — go back 3 months and forward 6 months
        from datetime import date as date_cls
        today_d = date_cls.today()
        _start = today_d - timedelta(days=today_d.weekday())  # this Monday
        _start = _start - timedelta(weeks=13)  # go back ~3 months
        all_working_days = []
        _d = _start
        while len(all_working_days) < 260:  # ~12 months of working days
            if _d.weekday() < 5:
                all_working_days.append(_d)
            _d += timedelta(days=1)
        day_labels = [d.strftime("%a %d %b %Y") for d in all_working_days]
        day_map    = dict(zip(day_labels, all_working_days))
        # Default = today's Monday
        default_day = today_d.strftime("%a %d %b %Y")
        if default_day not in day_labels:
            default_day = day_labels[13*5]  # approx 3 months in
        start_day = st.select_slider(
            "Start day", options=day_labels, value=default_day,
            label_visibility="collapsed",
        )
        i0 = day_labels.index(start_day)
        day_filter   = day_labels[i0:i0 + 20]
        week_filter  = None
        month_filter = None
        st.caption(f"📅 {day_filter[0][:10]} -> {day_filter[-1][:10]}  (20 working days)")
    st.divider()

    # ── Team / Area (formerly Depot) ──
    # Clean up depot names: remove blanks, rename Admin/Ops → Admin, remove 4am Slotters
    def clean_depot(d):
        if not d or str(d).strip() == "":
            return None
        d = str(d).strip()
        if d == "Admin/Ops":
            return "Admin"
        if d == "4am Slotters":
            return None
        return d

    # Apply cleaning to df_all for filter options
    depot_clean_map = {d: clean_depot(d) for d in df_all["depot"].unique()}
    all_depots = sorted(set(v for v in depot_clean_map.values() if v), key=str)

    st.caption("Team / Area")
    selected_depots = [d for d in all_depots
                       if st.checkbox(d, value=True, key=f"depot_{d}")]
    # Map back to original depot values
    depot_filter = [orig for orig, cleaned in depot_clean_map.items()
                    if cleaned in selected_depots]

    st.divider()

    # ── Route team ──
    has_route = df_all["route_team"].nunique() > 1 if not df_all.empty else False
    if has_route:
        # Remove blank/None/empty route teams
        all_route_teams = sorted([
            t for t in df_all["route_team"].dropna().unique()
            if str(t).strip() not in ("", "None", "No team")
        ], key=str)
        st.caption("Route team")
        if all_route_teams:
            cols_rt = st.columns(min(len(all_route_teams), 4))
            route_team_filter = []
            for i, t in enumerate(all_route_teams):
                label = f"T{t}"
                if cols_rt[i % 4].checkbox(label, value=True, key=f"rt_{t}"):
                    route_team_filter.append(t)
        else:
            route_team_filter = None
    else:
        route_team_filter = None

    # ── Vehicle type ──
    has_vehicle = df_all["vehicle_type"].nunique() > 1 if not df_all.empty else False
    if has_vehicle:
        # Rename Unknown → N/A
        all_vehicles = sorted(set(
            "N/A" if v == "Unknown" else v
            for v in df_all["vehicle_type"].dropna().unique()
        ))
        st.caption("Vehicle type")
        veh_icons = {"Motorbike": "🏍️", "EDV": "🚐", "Both": "🔀", "N/A": "—"}
        vehicle_filter_display = []
        for v in all_vehicles:
            icon = veh_icons.get(v, "")
            if st.checkbox(f"{icon} {v}", value=True, key=f"veh_{v}"):
                vehicle_filter_display.append(v)
        # Map N/A back to Unknown for filtering
        vehicle_filter = ["Unknown" if v == "N/A" else v for v in vehicle_filter_display]
    else:
        vehicle_filter = None

    st.divider()

    # ── Staff member ──
    all_names = sorted(df_all["name"].unique().tolist()) if not df_all.empty else []
    st.caption("Staff member")
    name_search = st.text_input("Search name", placeholder="Type to filter...", label_visibility="collapsed")
    filtered_name_opts = [n for n in all_names if name_search.lower() in n.lower()] if name_search else all_names
    select_all = st.checkbox("Select all", value=True, key="name_all")
    if select_all:
        name_filter = all_names
    else:
        name_filter = st.multiselect("Staff", filtered_name_opts, default=filtered_name_opts,
                                     label_visibility="collapsed")

    # ── Leave type ──
    all_types = sorted(df_all["leave_type"].unique().tolist()) if not df_all.empty else []
    st.caption("Leave type")
    type_filter = []
    for lt in all_types:
        if st.checkbox(lt, value=True, key=f"lt_{lt}"):
            type_filter.append(lt)

    st.divider()

    # ── Thresholds ──
    st.caption("🚨 Alert thresholds")
    threshold = st.slider("Max concurrent on leave", 1, 30, 15)
    st.caption("📊 Minimum staff on duty")
    st.caption("Slide to set minimum number of staff required on duty.")
    min_motorbike = st.slider("🏍️ Motorbike", 0, 30, 25)
    min_edv       = st.slider("🚐 EDV",        0, 30, 25)
    min_relief    = st.slider("👤 Relief",      0, 20, 15)


# ── Load single day leave from Google Sheets ─────────────────────────────────
sdl_df = load_single_day_leave()

# ── Apply filters ─────────────────────────────────────────────────────────────
if period_type != "Daily":
    day_filter = None
    day_map    = {}
    day_labels = []
if df_all.empty:
    st.error("No data found. Please check the Excel file.")
    st.stop()

df = df_all[df_all["name"].str.strip().astype(bool)].copy()

# Time filter
if period_type == "Monthly" and month_filter:
    df = df[df["month"].isin(month_filter)]
    filtered_weeks = [wk for wk in all_weeks if wk.strftime("%b %Y") in month_filter]
elif period_type == "Weekly" and week_filter:
    # Only filter df on weeks that have actual data
    data_week_labels = get_week_labels(all_weeks)
    df = df[df["iso_week"].isin(week_filter)]
    filtered_weeks      = [week_map[w] for w in week_filter if w in week_map]
    future_week_labels  = [w for w in week_filter if w not in data_week_labels]
    future_week_dates   = [week_map[w] for w in future_week_labels if w in week_map]
elif period_type == "Daily":
    filtered_weeks = all_weeks  # daily uses its own day_filter
else:
    filtered_weeks = all_weeks

if depot_filter:
    df = df[df["depot"].isin(depot_filter)]
if route_team_filter:
    df = df[df["route_team"].isin(route_team_filter)]
if vehicle_filter:
    df = df[df["vehicle_type"].isin(vehicle_filter)]
if name_filter:
    df = df[df["name"].isin(name_filter)]
if type_filter:
    df = df[df["leave_type"].isin(type_filter)]

filtered_names = name_filter if name_filter else all_names
# Only pass weeks that exist in actual data to concurrent_by_week
data_weeks = [wk for wk in filtered_weeks if wk <= pd.Timestamp("2026-12-28")]
conc_df = concurrent_by_week(df, data_weeks) if data_weeks else pd.DataFrame(
    columns=["week_start","iso_week","concurrent_count","staff_on_leave","month"])

# ── Metrics ───────────────────────────────────────────────────────────────────
total_leave_weeks = len(df)
unique_staff      = df["name"].nunique()
avg_weeks         = round(total_leave_weeks / unique_staff, 1) if unique_staff else 0
peak_row          = conc_df.loc[conc_df["concurrent_count"].idxmax()] if not conc_df.empty and conc_df["concurrent_count"].max() > 0 else None
peak_count        = int(peak_row["concurrent_count"]) if peak_row is not None else 0
peak_label        = peak_row["iso_week"] if peak_row is not None else "-"
alert_weeks_df    = conc_df[conc_df["concurrent_count"] >= threshold]

logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Australia_Post_logo_logotype.png")

if os.path.exists(logo_path):
    import base64
    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:18px; margin-bottom:0.5rem; padding-top:1rem;">
        <img src="data:image/png;base64,{logo_b64}" style="height:64px; width:auto; border-radius:8px;">
        <div>
            <div style="font-size:1.6rem; font-weight:600; color:var(--color-text-primary); line-height:1.2;">Annual Leave Dashboard</div>
            <div style="font-size:0.85rem; color:var(--color-text-secondary); margin-top:2px;">
                Brisbane Central — Stafford DC &nbsp;|&nbsp; 2025/2026 &nbsp;|&nbsp; {datetime.today().strftime('%d %b %Y')}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.title("Annual Leave Dashboard")
    st.caption(f"Brisbane Central — Stafford DC &nbsp;|&nbsp; 2025/2026 &nbsp;|&nbsp; {datetime.today().strftime('%d %b %Y')}")

c1, c2, c3, c4, c5 = st.columns(5)
with c1: st.metric("Staff tracked",     len(filtered_names))
with c2: st.metric("Total leave weeks", total_leave_weeks)
with c3: st.metric("Avg weeks / person",avg_weeks)
with c4: st.metric("Peak concurrent",   f"{peak_count} staff", delta=peak_label, delta_color="off")
with c5: st.metric("High-risk weeks",   len(alert_weeks_df), delta="above threshold", delta_color="inverse" if len(alert_weeks_df) > 0 else "off")

st.divider()

# ── Staffing load chart + who's off table ─────────────────────────────────────
st.markdown("#### ⚠️ Concurrent leave — staffing load")

if period_type == "Daily" and day_filter:
    # ── Daily view chart ──────────────────────────────────────────────────────
    from single_day_leave import load_single_day_leave
    sdl = load_single_day_leave()

    depot_color_map = {
        "PDO":"#0077BB","Relief":"#EE7733","Night Shift":"#AA4499",
        "Mid Shift":"#DDAA33","Admin":"#BB5522","Admin/Ops":"#BB5522",
        "GPO":"#88BBDD","Management":"#CC3377",
    }
    all_depots_daily = sorted([
        d for d in df_all["depot"].dropna().unique()
        if str(d).strip() not in ("","4am Slotters")
    ])

    day_dates = [day_map[dl] for dl in day_filter if dl in day_map]
    data_cutoff = datetime(2026, 12, 28).date()

    fig_daily = go.Figure()
    for depot in all_depots_daily:
        label = "Admin" if depot == "Admin/Ops" else depot
        color = depot_color_map.get(depot, "#BBBBBB")
        y_vals, x_vals, hover_vals = [], [], []
        for day_date in day_dates:
            x_vals.append(day_date.strftime("%a %d %b"))
            if day_date > data_cutoff:
                y_vals.append(0)
                hover_vals.append(f"<b>{day_date.strftime('%a %d %b %Y')}</b><br>📭 No data yet")
                continue
            # Count from leave_data (weekly — if week contains this day)
            wk_start = day_date - timedelta(days=day_date.weekday())
            wk_dt    = datetime.combine(wk_start, datetime.min.time())
            depot_df = df_all[df_all["depot"] == depot]
            wk_count = depot_df[depot_df["week_start"] == wk_dt]["name"].nunique()
            # Add single day leave
            sdl_count = 0
            if not sdl.empty and "date" in sdl.columns:
                sdl_day = sdl[pd.to_datetime(sdl["date"]).dt.date == day_date]
                if "depot" in sdl_day.columns:
                    sdl_count = sdl_day[sdl_day["depot"] == depot]["name"].nunique()
                else:
                    sdl_count = 0
            total = wk_count + sdl_count
            y_vals.append(total)
            hover_vals.append(f"<b>{label}</b><br>{day_date.strftime('%a %d %b %Y')}<br>{total} on leave")

        fig_daily.add_trace(go.Bar(
            x=x_vals, y=y_vals, name=label,
            marker_color=color,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_vals,
        ))

    fig_daily.add_hline(y=threshold, line_dash="dash", line_color="#E24B4A",
                        line_width=1.5,
                        annotation_text=f"Max concurrent ({threshold})",
                        annotation_position="top right",
                        annotation_font_color="#111111",
                        annotation_bgcolor="rgba(255,255,255,0.8)")

    fig_daily.update_layout(
        barmode="stack", height=320,
        margin=dict(l=0,r=0,t=10,b=10),
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickangle=-45, tickfont=dict(size=10), showgrid=False),
        yaxis=dict(title="Staff on leave", gridcolor="#f0f0f0", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_daily, use_container_width=True)
# Total staff counts for minimum thresholds (used in weekly/monthly chart)
total_motorbike = int((df_all["vehicle_type"] == "Motorbike").sum() / max(df_all["name"].nunique(), 1) * df_all["name"].nunique()) if not df_all.empty else 0
total_motorbike = df_all[df_all["vehicle_type"] == "Motorbike"]["name"].nunique() if not df_all.empty else 0
total_edv       = df_all[df_all["vehicle_type"] == "EDV"]["name"].nunique()        if not df_all.empty else 0
total_relief    = df_all[df_all["depot"] == "Relief"]["name"].nunique()             if not df_all.empty else 0

# Always build conc_display — even if conc_df is empty (future months)
if period_type != "Daily":
    # For monthly view: group concurrent counts by month
    # For weekly view: keep weekly granularity
    if period_type == "Monthly":
        # Build full 13-month spine — include future/no-data months as 0
        if not conc_df.empty:
            conc_df["month_label"] = conc_df["week_start"].apply(lambda w: w.strftime("%b %Y"))
            conc_agg = (conc_df.groupby("month_label")
                               .agg(concurrent_count=("concurrent_count","max"),
                                    staff_on_leave=("staff_on_leave", lambda x: sorted(set(
                                        [name for sublist in x for name in sublist]))))
                               .reset_index())
        else:
            conc_agg = pd.DataFrame(columns=["month_label","concurrent_count","staff_on_leave"])

        rows_cm = []
        for m in month_filter:
            has = m in conc_agg["month_label"].values if not conc_agg.empty else False
            if has:
                r = conc_agg[conc_agg["month_label"]==m].iloc[0]
                rows_cm.append({"x_label": m, "concurrent_count": r["concurrent_count"],
                                 "staff_on_leave": r["staff_on_leave"], "has_data": True})
            else:
                rows_cm.append({"x_label": m, "concurrent_count": 0,
                                 "staff_on_leave": [], "has_data": False})
        conc_display = pd.DataFrame(rows_cm)
    elif period_type == "Weekly" and week_filter:
        # Build full 52-week spine including future no-data weeks
        data_week_set = set(get_week_labels(all_weeks))
        rows_wk = []
        for wlbl in week_filter:
            wk_dt = week_map.get(wlbl)
            is_future = wlbl not in data_week_set
            if not is_future and not conc_df.empty:
                match = conc_df[conc_df["week_start"] == wk_dt]
                if not match.empty:
                    r = match.iloc[0]
                    rows_wk.append({"x_label": wk_dt.strftime("%d %b") if wk_dt else wlbl,
                                    "concurrent_count": r["concurrent_count"],
                                    "staff_on_leave": r["staff_on_leave"],
                                    "has_data": True})
                    continue
            rows_wk.append({"x_label": wk_dt.strftime("%d %b") if wk_dt else wlbl,
                             "concurrent_count": 0,
                             "staff_on_leave": [],
                             "has_data": False})
        conc_display = pd.DataFrame(rows_wk) if rows_wk else pd.DataFrame(
            columns=["x_label","concurrent_count","staff_on_leave","has_data"])
    else:
        # Daily mode — conc_display not used for main chart
        conc_display = pd.DataFrame(
            columns=["x_label","concurrent_count","staff_on_leave","has_data"])

    month_boundaries = []

    # Per-week breakdown: how many motorbike/edv/relief are on leave each week
    wk_vehicle_counts = {}
    wk_relief_counts  = {}
    for wk in filtered_weeks:
        wk_df_v = df[df["week_start"] == wk]
        wk_vehicle_counts[wk] = {
            "Motorbike": wk_df_v[wk_df_v["vehicle_type"] == "Motorbike"]["name"].nunique(),
            "EDV":       wk_df_v[wk_df_v["vehicle_type"] == "EDV"]["name"].nunique(),
        }
        wk_relief_counts[wk] = wk_df_v[wk_df_v["depot"] == "Relief"]["name"].nunique()

    def get_bar_color(wk, count):
        """Green if all minimums met, amber at threshold, red critical."""
        mb_on_leave = wk_vehicle_counts.get(wk, {}).get("Motorbike", 0)
        edv_on_leave= wk_vehicle_counts.get(wk, {}).get("EDV", 0)
        rel_on_leave= wk_relief_counts.get(wk, 0)
        mb_avail    = total_motorbike - mb_on_leave
        edv_avail   = total_edv       - edv_on_leave
        rel_avail   = total_relief    - rel_on_leave
        below_min = (
            (min_motorbike > 0 and mb_avail  < min_motorbike) or
            (min_edv       > 0 and edv_avail < min_edv)       or
            (min_relief    > 0 and rel_avail < min_relief)
        )
        if below_min or count >= threshold + 2:
            return "#E24B4A"   # red
        elif count >= threshold:
            return "#EF9F27"   # amber
        else:
            return "#1D9E75"   # green — all good

    bar_colors = [get_bar_color(row["week_start"], row["concurrent_count"])
                  for _, row in conc_df.iterrows()]

    # Build rich hover — full/partial breakdown + days lost + vehicle availability
    from data_parser import _days_in_range

    def days_for_leave(leave_type, raw_vals):
        """Calculate working days lost for a list of raw cell values."""
        total = 0
        for v in raw_vals:
            s = str(v).strip().upper().replace(" ", "")
            if s == "1":
                total += 5
            elif s in ("2","3","4","5","6","7","8","9","10"):
                try: total += int(s)
                except: total += 5
            else:
                r = _days_in_range(s)
                total += r[1] - r[0] + 1 if r else 1
        return total

    hover_texts = []
    for _, row in conc_display.iterrows():
        total   = row["concurrent_count"]
        x_label = row["x_label"]

        if period_type == "Monthly":
            has_data = row.get("has_data", True)
            if not has_data:
                h = f"<b>{x_label}</b><br>📭 No data available yet"
            else:
                h = (f"<b>{x_label}</b><br>"
                     f"<b>Peak: {total} staff on leave</b>")
        else:
            has_data = row.get("has_data", True)
            if not has_data:
                h = f"<b>{x_label}</b><br>📭 No data available yet"
            else:
                # Look up week_start from week_map using x_label
                wk = next((week_map[wl] for wl in week_filter
                           if week_map.get(wl) is not None
                           and week_map[wl].strftime("%d %b") == x_label), None)
                if wk is None:
                    h = f"<b>{x_label}</b><br>{total} on leave"
                else:
                    wk_df_h = df[df["week_start"] == wk]
                    full_wk = wk_df_h[wk_df_h["leave_type"] == "Annual Leave"]
                    partial = wk_df_h[wk_df_h["leave_type"] == "Annual Leave (partial week)"]
                    n_full, n_partial = len(full_wk), len(partial)
                    days_lost = n_full*5 + n_partial*3 + len(wk_df_h[~wk_df_h["leave_type"].isin(
                        ["Annual Leave","Annual Leave (partial week)"])])*5
                    mb_leave  = wk_vehicle_counts.get(wk, {}).get("Motorbike", 0)
                    edv_leave = wk_vehicle_counts.get(wk, {}).get("EDV", 0)
                    rel_leave = wk_relief_counts.get(wk, 0)
                    mb_avail  = total_motorbike - mb_leave
                    edv_avail = total_edv       - edv_leave
                    rel_avail = total_relief    - rel_leave

                    def avail_line(avail, minimum, label):
                        if minimum == 0: return ""
                        icon = "✅" if avail >= minimum else "🔴"
                        return f"<br>{icon} {label}: {avail} available (min {minimum})"

                    partial_detail = f" ({n_partial*3} days)" if n_partial > 0 else ""
                    h = (
                        f"<b>{wk.strftime('%d %b %Y')}</b><br>"
                        f"<b>{total} on leave</b>  ({n_full} full week + {n_partial} partial{partial_detail})<br>"
                        f"≈ {days_lost} working days lost"
                        + avail_line(mb_avail, min_motorbike, "Motorbike")
                        + avail_line(edv_avail, min_edv, "EDV")
                        + avail_line(rel_avail, min_relief, "Relief")
                    )
        hover_texts.append(h)

    fig_load = go.Figure()
    # Use small placeholder height for no-data months so they're visible
    y_vals = []
    for _, crow in conc_display.iterrows():
        has_data = crow.get("has_data", True)
        y_vals.append(crow["concurrent_count"] if has_data else 0.3)

    fig_load.add_trace(go.Bar(
        x=conc_display["x_label"],
        y=y_vals,
        marker_color=bar_colors,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts,
        name="Staff on leave",
        text=["📭 No data" if not row.get("has_data", True) else ""
              for _, row in conc_display.iterrows()],
        textposition="inside",
        textfont=dict(color="rgba(150,150,150,0.8)", size=10),
    ))
    fig_load.add_hline(
        y=threshold, line_dash="dash", line_color="#E24B4A", line_width=1.5,
        annotation_text=f"Max concurrent ({threshold})",
        annotation_position="top right",
        annotation_font_color="#111111",
        annotation_bgcolor="rgba(255,255,255,0.8)",
    )
    # Threshold lines — use annotations list to avoid overlap
    extra_annotations = []
    if min_motorbike > 0:
        fig_load.add_hline(y=min_motorbike, line_dash="dot", line_color="#0077BB", line_width=1.5)
        extra_annotations.append(dict(
            xref="paper", yref="y", x=1.0, y=min_motorbike,
            text=f"🏍️ Min motorbike ({min_motorbike})",
            showarrow=False, xanchor="right", yanchor="bottom",
            font=dict(color="#111111", size=11),
            bgcolor="rgba(255,255,255,0.85)", borderpad=3,
        ))
    if min_edv > 0:
        fig_load.add_hline(y=min_edv, line_dash="dot", line_color="#EE7733", line_width=1.5)
        extra_annotations.append(dict(
            xref="paper", yref="y", x=1.0, y=min_edv,
            text=f"🚐 Min EDV ({min_edv})",
            showarrow=False, xanchor="right", yanchor="top",
            font=dict(color="#111111", size=11),
            bgcolor="rgba(255,255,255,0.85)", borderpad=3,
        ))
    if min_relief > 0:
        fig_load.add_hline(y=min_relief, line_dash="dot", line_color="#CC3377", line_width=1.5)
        extra_annotations.append(dict(
            xref="paper", yref="y", x=1.0, y=min_relief,
            text=f"👤 Min relief ({min_relief})",
            showarrow=False, xanchor="right", yanchor="bottom",
            font=dict(color="#111111", size=11),
            bgcolor="rgba(255,255,255,0.85)", borderpad=3,
        ))

    # Add month divider lines for monthly view
    shapes, annotations = [], extra_annotations
    if period_type == "Monthly" and month_boundaries:
        for i, (x_pos, month_name) in enumerate(month_boundaries):
            if i > 0:
                shapes.append(dict(
                    type="line", xref="x", yref="paper",
                    x0=x_pos, x1=x_pos, y0=0, y1=1,
                    line=dict(color="rgba(150,150,150,0.4)", width=1, dash="dot")
                ))
            annotations.append(dict(
                xref="x", yref="paper",
                x=x_pos, y=1.04,
                text=f"<b>{month_name}</b>",
                showarrow=False,
                font=dict(size=10, color="#888"),
                xanchor="left"
            ))

    fig_load.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=30, b=10),
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickangle=-60, tickfont=dict(size=10), showgrid=False),
        yaxis=dict(title="Staff on leave", gridcolor="#f0f0f0", zeroline=False),
        showlegend=False,
        shapes=shapes,
        annotations=annotations,
    )

    leg_l, leg_a, leg_ok, _ = st.columns([1, 1, 1, 5])
    with leg_ok: st.markdown('<span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:#1D9E75;margin-right:4px"></span><small>All minimums met</small>', unsafe_allow_html=True)
    with leg_a:  st.markdown('<span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:#EF9F27;margin-right:4px"></span><small>Near threshold</small>', unsafe_allow_html=True)
    with leg_l:  st.markdown('<span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:#E24B4A;margin-right:4px"></span><small>Critical / below minimum</small>', unsafe_allow_html=True)

    st.plotly_chart(fig_load, use_container_width=True)

    # Who's off table — only alert weeks
    if not alert_weeks_df.empty:
        st.markdown(f"**{len(alert_weeks_df)} weeks above threshold — who's on leave:**")

        table_rows = []
        for _, row in alert_weeks_df.sort_values("week_start").iterrows():
            wk    = row["week_start"]
            wk_df = df[df["week_start"] == wk]
            total = row["concurrent_count"]

            # Team breakdown: "T1: 3  T2: 2  T3: 4  No team: 5"
            teams = wk_df["route_team"].replace("", "No team").value_counts().to_dict()
            team_parts = []
            for t, c in sorted(teams.items()):
                label = f"T{t}" if t not in ("No team", "—") else "No team"
                pct   = round(c / total * 100)
                team_parts.append(f"{label}: {c} ({pct}%)")
            team_str = "   |   ".join(team_parts)

            # Vehicle breakdown: "Motorbike: 6  EDV: 4  Unknown: 3"
            vehicles = wk_df["vehicle_type"].value_counts().to_dict()
            veh_parts = []
            for v, c in sorted(vehicles.items(), key=lambda x: -x[1]):
                pct = round(c / total * 100)
                veh_parts.append(f"{v}: {c} ({pct}%)")
            veh_str = "   |   ".join(veh_parts)

            staff_names = sorted(row["staff_on_leave"])
            table_rows.append({
                "Week":        row["iso_week"],
                "Date (Mon)":  wk.strftime("%d %b %Y"),
                "# on leave":  total,
                "By team":     team_str or "—",
                "By vehicle":  veh_str  or "—",
                "Staff":       ", ".join(staff_names),
            })

        tbl_df = pd.DataFrame(table_rows)

        def colour_count(val):
            if val >= threshold + 2:
                return "background-color: #fde8e8; color: #a32d2d; font-weight:600"
            elif val >= threshold:
                return "background-color: #fef3cd; color: #854f0b; font-weight:600"
            return ""

        styled = (tbl_df.style
                  .map(colour_count, subset=["# on leave"])
                  .set_properties(subset=["Staff"], **{"white-space": "normal", "font-size": "12px"})
                  .set_properties(subset=["By team","By vehicle"], **{"font-size": "12px", "white-space": "normal"})
                  .set_properties(subset=["Week","Date (Mon)","# on leave"], **{"white-space": "nowrap"}))

        st.dataframe(styled, use_container_width=True, hide_index=True,
                     column_config={
                         "Staff":      st.column_config.TextColumn(width="large"),
                         "By team":    st.column_config.TextColumn(width="medium"),
                         "By vehicle": st.column_config.TextColumn(width="medium"),
                     })

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab2, tab1, tab3, tab4, tab5 = st.tabs(["📊 Analysis", "📆 Calendar view", "👥 By staff", "📋 Raw data", "📝 Single Day Leave"])

# ── Tab 1: Calendar ───────────────────────────────────────────────────────────
with tab1:
    st.markdown("#### Leave calendar — each row = staff member, each column = week")
    st.caption("Coloured = on leave. Numbers at bottom = concurrent count. Red = above threshold.")

    if not df.empty and filtered_weeks:
        # ── Legend ABOVE calendar ──
        st.markdown("**Legend:**")
        leg_cols = st.columns(len(LEAVE_COLORS))
        for i, (lt, color) in enumerate(LEAVE_COLORS.items()):
            with leg_cols[i]:
                st.markdown(
                    f'<div style="background:{color};border-radius:4px;padding:4px 6px;'                    f'font-size:11px;color:white;text-align:center;margin-bottom:8px">{lt}</div>',
                    unsafe_allow_html=True)

        def format_name(n):
            """Show as SURNAME, Firstname — last word = surname."""
            parts = str(n).strip().split()
            if len(parts) >= 2:
                surname = parts[-1].upper()
                firstname = ' '.join(parts[:-1])
                return f"{surname}, {firstname}"
            return str(n).strip().upper()

        display_names_raw = sorted(
            [n for n in all_names
             if n in filtered_names and str(n).strip() not in ("", "None", "nan")],
            key=lambda n: format_name(n).upper()
        )
        display_names = display_names_raw
        display_labels = [format_name(n) for n in display_names_raw]
        display_weeks = sorted(set(filtered_weeks))[:60]

        cal_data = {}
        for name in display_names:
            cal_data[name] = {}
            person_df = df[df["name"] == name]
            for _, row in person_df.iterrows():
                if row["week_start"] in display_weeks:
                    cal_data[name][row["week_start"]] = row["leave_type"]

        color_map = {lt: i+1 for i, lt in enumerate(LEAVE_COLORS.keys())}

        z_vals, hover_text = [], []
        for name in display_names:
            row_z, row_h = [], []
            for wk in display_weeks:
                lt = cal_data[name].get(wk, "")
                row_z.append(color_map.get(lt, 0))
                row_h.append(
                    f"{name}<br>{wk.strftime('%d %b %Y')}<br>{lt if lt else 'Working'}")
            z_vals.append(row_z)
            hover_text.append(row_h)

        # X-axis: always use unique date per week so Plotly doesn't merge columns
        # Monthly view → show "Feb 2026" only at month boundary via tickvals/ticktext
        week_labels_display = [wk.strftime("%d %b") for wk in display_weeks]

        if period_type == "Monthly":
            # Build custom tick positions: only show label at first week of each month
            tickvals, ticktext = [], []
            prev_month = None
            for wk_label, wk in zip(week_labels_display, display_weeks):
                m = wk.strftime("%b %Y")
                if m != prev_month:
                    tickvals.append(wk_label)
                    ticktext.append(m)
                    prev_month = m
            cal_xaxis = dict(tickangle=-45, tickfont=dict(size=10),
                             tickvals=tickvals, ticktext=ticktext)
        else:
            cal_xaxis = dict(tickangle=-45, tickfont=dict(size=10))

        conc_row   = [conc_df[conc_df["week_start"] == wk]["concurrent_count"].sum()
                      for wk in display_weeks]
        conc_hover = [f"{wk.strftime('%d %b %Y')}<br>{c} staff on leave"
                      for wk, c in zip(display_weeks, conc_row)]

        color_scale = [
            [0.00, "#f0f0f0"], [0.13, "#0077BB"], [0.26, "#88BBDD"],
            [0.39, "#EE7733"], [0.52, "#CC3377"], [0.65, "#AA4499"],
            [0.78, "#DDAA33"], [0.90, "#BB5522"], [1.00, "#BBBBBB"],
        ]

        fig_cal = go.Figure()
        fig_cal.add_trace(go.Heatmap(
            z=z_vals, x=week_labels_display, y=display_labels,
            text=hover_text, hovertemplate="%{text}<extra></extra>",
            colorscale=color_scale, showscale=False, xgap=1, ygap=1,
            zmin=0, zmax=len(LEAVE_COLORS),
        ))
        n_staff = len(display_labels)
        # Top labels via annotations — most reliable way with heatmap
        top_annotations = []
        if period_type == "Monthly":
            prev_m = None
            for lbl, wk in zip(week_labels_display, display_weeks):
                m = wk.strftime("%b %Y")
                if m != prev_m:
                    top_annotations.append(dict(
                        x=lbl, y=1.04, xref="x", yref="paper",
                        text=f"<b>{m}</b>",
                        showarrow=False,
                        font=dict(size=10, color="#555"),
                        xanchor="left",
                        yanchor="bottom",
                    ))
                    prev_m = m
        else:
            for lbl in week_labels_display:
                top_annotations.append(dict(
                    x=lbl, y=1.04, xref="x", yref="paper",
                    text=lbl,
                    showarrow=False,
                    font=dict(size=9, color="#555"),
                    xanchor="center",
                    textangle=-45,
                    yanchor="bottom",
                ))

        fig_cal.update_layout(
            height=max(350, n_staff * 30 + 160),
            margin=dict(l=0, r=0, t=50, b=10),
            xaxis=cal_xaxis,
            yaxis=dict(tickfont=dict(size=11)),
            plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
            annotations=top_annotations,
        )
        st.plotly_chart(fig_cal, use_container_width=True)
    else:
        st.info("No leave data matches the current filters.")

# ── Tab 2: Analysis ───────────────────────────────────────────────────────────
with tab2:
    st.markdown("---")

    # Team / vehicle breakdown (only if columns exist)
    if has_route or has_vehicle:
        bc1, bc2 = st.columns(2)
        if has_route and not df.empty:
            with bc1:
                st.markdown("#### Staff Leave by Delivery Team")

                # Build weekly counts per team
                team_colors = {"1":"#0077BB","2":"#EE7733","3":"#CC3377",
                               "":"#BBBBBB","No team":"#BBBBBB"}

                valid_teams = [t for t in df["route_team"].unique()
                               if str(t).strip() not in ("","None","No team")]

                fig_rt = go.Figure()
                for team in sorted(valid_teams, key=str):
                    team_df = df[df["route_team"] == team].copy()

                    if period_type == "Monthly":
                        # Group by month_num+year for proper date sorting
                        team_df["_ym"] = team_df["week_start"].dt.to_period("M").dt.to_timestamp()
                        wk_team = (team_df.groupby("_ym")["name"]
                                          .nunique().reset_index()
                                          .rename(columns={"name":"count","_ym":"date"}))
                        wk_team = wk_team.sort_values("date")
                    else:
                        wk_team = (team_df.groupby("week_start")["name"]
                                          .nunique().reset_index()
                                          .rename(columns={"name":"count","week_start":"date"}))
                        wk_team = wk_team.sort_values("date")

                    fig_rt.add_trace(go.Scatter(
                        x=wk_team["date"],
                        y=wk_team["count"],
                        mode="lines+markers",
                        name=f"Team {team}",
                        line=dict(color=team_colors.get(str(team), "#888"), width=2.5),
                        marker=dict(size=6),
                        hovertemplate=f"<b>Team {team}</b><br>%{{x|%b %Y}}<br>%{{y}} on leave<extra></extra>",
                    ))

                fig_rt.update_layout(
                    height=350,
                    margin=dict(l=0,r=0,t=30,b=10),
                    plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(
                        type="date",
                        tickangle=-45,
                        tickfont=dict(size=10),
                        tickformat="%b %Y" if period_type=="Monthly" else "%d %b",
                        showgrid=False,
                    ),
                    yaxis=dict(title="Staff on leave", gridcolor="#f0f0f0",
                               zeroline=False, rangemode="tozero"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                xanchor="right", x=1),
                )
                st.plotly_chart(fig_rt, use_container_width=True)

        if not df_all.empty:
            with bc2:
                st.markdown("#### Next two weeks — Leave by Team")
                today = datetime.today().date()
                # Find next Monday
                days_to_mon = (7 - today.weekday()) % 7 or 7
                next_mon = today + timedelta(days=days_to_mon - today.weekday() if today.weekday() != 0 else 0)
                next_mon = today - timedelta(days=today.weekday())  # this Monday
                two_weeks_days = [next_mon + timedelta(days=i) for i in range(14)
                                  if (next_mon + timedelta(days=i)).weekday() < 5]  # Mon-Fri only

                # All depots for team breakdown
                depot_colors = {
                    "PDO":        "#0077BB",
                    "Relief":     "#EE7733",
                    "Night Shift":"#AA4499",
                    "Mid Shift":  "#DDAA33",
                    "Admin":      "#BB5522",
                    "Admin/Ops":  "#BB5522",
                    "GPO":        "#88BBDD",
                    "Management": "#CC3377",
                }

                # For each day, check which weeks overlap and count per depot
                # leave data is weekly — a person on leave that week = on leave Mon-Fri
                fig_next = go.Figure()
                depots_in_data = sorted(df_all["depot"].dropna().unique())

                for depot in sorted(depots_in_data, key=lambda x: str(x).strip(), reverse=True):
                    if not depot or str(depot).strip() in ("", "4am Slotters"):
                        continue
                    depot_label = "Admin" if depot == "Admin/Ops" else depot
                    depot_df = df_all[df_all["depot"] == depot]
                    day_counts = []
                    for day in two_weeks_days:
                        # Find the Monday of this day's week
                        wk_start = day - timedelta(days=day.weekday())
                        wk_start_dt = datetime.combine(wk_start, datetime.min.time())
                        on_leave = depot_df[depot_df["week_start"] == wk_start_dt]["name"].nunique()
                        day_counts.append(on_leave)

                    color = depot_colors.get(depot, "#BBBBBB")
                    fig_next.add_trace(go.Bar(
                        x=[d.strftime("%a %d %b") for d in two_weeks_days],
                        y=day_counts,
                        name=depot_label,
                        marker_color=color,
                        hovertemplate=f"<b>{depot_label}</b><br>%{{x}}<br>%{{y}} on leave<extra></extra>",
                    ))

                fig_next.add_hline(
                    y=threshold, line_dash="dash", line_color="#E24B4A", line_width=1.5,
                    annotation_text=f"Threshold ({threshold})",
                    annotation_position="top right", annotation_font_color="#E24B4A",
                )
                fig_next.update_layout(
                    barmode="stack",
                    height=350,
                    margin=dict(l=0, r=0, t=30, b=10),
                    plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(tickangle=-45, tickfont=dict(size=10), showgrid=False),
                    yaxis=dict(title="Staff on leave", gridcolor="#f0f0f0", zeroline=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                xanchor="right", x=1, font=dict(size=10),
                                ),
                )
                st.plotly_chart(fig_next, use_container_width=True)

    st.markdown("#### Concurrent leave over time — by team")
    if not conc_df.empty and not df.empty:
        depot_color_map = {
            "PDO":         "#0077BB",
            "Relief":      "#EE7733",
            "Night Shift": "#AA4499",
            "Mid Shift":   "#DDAA33",
            "Admin":       "#BB5522",
            "Admin/Ops":   "#BB5522",
            "GPO":         "#88BBDD",
            "Management":  "#CC3377",
        }
        all_depots_conc = sorted([
            d for d in df["depot"].dropna().unique()
            if str(d).strip() not in ("", "4am Slotters")
        ])
        wk_breakdown = []
        for wk in filtered_weeks:
            wk_df_b = df[df["week_start"] == wk]
            x_lbl = wk.strftime("%b %Y") if period_type == "Monthly" else wk.strftime("%d %b")
            row = {"week_start": wk, "x_label": x_lbl}
            for depot in all_depots_conc:
                row[depot] = wk_df_b[wk_df_b["depot"] == depot]["name"].nunique()
            wk_breakdown.append(row)
        bkdn_df = pd.DataFrame(wk_breakdown)

        fig_conc = go.Figure()
        for depot in all_depots_conc:
            label = "Admin" if depot == "Admin/Ops" else depot
            color = depot_color_map.get(depot, "#BBBBBB")
            if depot in bkdn_df.columns:
                fig_conc.add_trace(go.Bar(
                    x=bkdn_df["x_label"], y=bkdn_df[depot],
                    name=label, marker_color=color,
                ))

        fig_conc.add_hline(y=threshold, line_dash="dash", line_color="#E24B4A",
                            line_width=1.5,
                            annotation_text=f"Max concurrent ({threshold})",
                            annotation_position="top right",
                            annotation_font_color="#111111",
                            annotation_bgcolor="rgba(255,255,255,0.8)")
        if min_motorbike > 0:
            fig_conc.add_hline(y=min_motorbike, line_dash="dot", line_color="#0077BB",
                                line_width=1.5,
                                annotation_text=f"Min motorbike on duty ({min_motorbike})",
                                annotation_position="top right",
                                annotation_font_color="#111111",
                                annotation_bgcolor="rgba(255,255,255,0.8)")
        if min_edv > 0:
            fig_conc.add_hline(y=min_edv, line_dash="dot", line_color="#EE7733",
                                line_width=1.5,
                                annotation_text=f"Min EDV on duty ({min_edv})",
                                annotation_position="top right",
                                annotation_font_color="#111111",
                                annotation_bgcolor="rgba(255,255,255,0.8)")

        fig_conc.update_layout(
            barmode="stack", height=300,
            margin=dict(l=0,r=0,t=10,b=10),
            plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(tickangle=-60, tickfont=dict(size=10)),
            yaxis_title="Staff on leave",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_conc, use_container_width=True)


    # Bottom row (bar + pie) — defined first so Python knows the vars
    col_l, col_r = st.columns(2)

    with col_l:
        if period_type == "Monthly":
            st.markdown("#### Staff on leave by month")
            if not df.empty:
                # Build a full 13-month spine including future months
                today_dt = pd.Timestamp.today().normalize()
                all_13_months = month_filter  # already 13 months from slider

                # Get actual data per month
                month_data = (df.groupby("month")
                               .agg(staff_count=("name","nunique"),
                                    leave_weeks=("name","count"))
                               .reset_index())

                # Build complete month list with "no data" for future
                rows = []
                for m in all_13_months:
                    m_dt = pd.to_datetime("01 " + m, dayfirst=True)
                    has_data = m in month_data["month"].values
                    is_future = m_dt > today_dt
                    if has_data:
                        r = month_data[month_data["month"]==m].iloc[0]
                        rows.append({"month": m, "staff_count": r["staff_count"],
                                     "has_data": True, "is_future": False})
                    elif is_future:
                        rows.append({"month": m, "staff_count": 0,
                                     "has_data": False, "is_future": True})
                    else:
                        rows.append({"month": m, "staff_count": 0,
                                     "has_data": False, "is_future": False})

                full_df = pd.DataFrame(rows)

                bar_colors = []
                for _, r in full_df.iterrows():
                    if r["is_future"]:
                        bar_colors.append("rgba(180,180,180,0.25)")
                    elif r["staff_count"] == 0:
                        bar_colors.append("#e0e0e0")
                    else:
                        bar_colors.append("#0077BB")

                hover_texts = []
                for _, r in full_df.iterrows():
                    if r["is_future"]:
                        hover_texts.append(f"<b>{r['month']}</b><br><i>No data available yet</i>")
                    elif r["staff_count"] == 0:
                        hover_texts.append(f"<b>{r['month']}</b><br>No leave recorded")
                    else:
                        hover_texts.append(f"<b>{r['month']}</b><br><b>{int(r['staff_count'])} staff on leave</b>")

                fig = go.Figure(go.Bar(
                    x=full_df["month"],
                    y=full_df["staff_count"].where(~full_df["is_future"], other=None),
                    marker_color=bar_colors,
                    hovertemplate="%{customdata}<extra></extra>",
                    customdata=hover_texts,
                ))

                # Add "No data" shading for future months
                future_months = full_df[full_df["is_future"]]["month"].tolist()
                if future_months:
                    fig.add_trace(go.Bar(
                        x=future_months,
                        y=[full_df["staff_count"].max() or 5] * len(future_months),
                        marker_color="rgba(200,200,200,0.15)",
                        marker_line_color="rgba(180,180,180,0.3)",
                        marker_line_width=1,
                        hovertemplate=[f"<b>{m}</b><br><i>📭 No data available yet</i><extra></extra>"
                                       for m in future_months],
                        showlegend=False,
                    ))

                fig.update_layout(
                    margin=dict(l=0,r=0,t=10,b=10),
                    yaxis_title="Unique staff on leave",
                    plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                    xaxis_tickangle=-45,
                    barmode="overlay",
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown("#### Staff on leave by week")
            if not df.empty:
                wk_df = (df.groupby("iso_week")
                           .agg(staff_count=("name", "nunique"),
                                leave_weeks=("name", "count"))
                           .reset_index())
                ordered_wks = [w for w in week_labels if w in wk_df["iso_week"].values]
                wk_df["iso_week"] = pd.Categorical(wk_df["iso_week"], categories=ordered_wks, ordered=True)
                wk_df = wk_df.sort_values("iso_week")
                wk_df["full_wks"]   = df[df["leave_type"]=="Annual Leave"].groupby("iso_week")["name"].count().reindex(wk_df["iso_week"].astype(str)).fillna(0).values
                wk_df["partial_wks"]= df[df["leave_type"]=="Annual Leave (partial week)"].groupby("iso_week")["name"].count().reindex(wk_df["iso_week"].astype(str)).fillna(0).values
                wk_df["days_lost"]  = wk_df["full_wks"]*5 + wk_df["partial_wks"]*3 + (wk_df["leave_weeks"]-wk_df["full_wks"]-wk_df["partial_wks"])*5
                wk_df["hover"] = wk_df.apply(
                    lambda r: (f"<b>{r['iso_week']}</b><br>"
                               f"<b>{int(r['staff_count'])} staff on leave</b><br>"
                               f"{int(r['full_wks'])} full week  +  {int(r['partial_wks'])} partial<br>"
                               f"≈ {int(r['days_lost'])} working days lost"), axis=1)
                wk_df["x_label"] = wk_df["iso_week"].apply(
                    lambda w: pd.to_datetime(week_map[w]).strftime("%d %b") if w in week_map else w)
                fig = go.Figure(go.Bar(
                    x=wk_df["x_label"],
                    y=wk_df["staff_count"],
                    marker_color=wk_df["staff_count"],
                    marker_colorscale=["#85B7EB","#378ADD","#E24B4A"],
                    hovertemplate="%{customdata}<extra></extra>",
                    customdata=wk_df["hover"],
                ))
                fig.update_layout(margin=dict(l=0,r=0,t=10,b=10),
                                  yaxis_title="Unique staff on leave",
                                  plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                                  xaxis_tickangle=-60)
                st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("#### Leave type breakdown")
        if not df.empty:
            type_df = df.groupby("leave_type").size().reset_index(name="count").sort_values("count", ascending=False)
            fig = px.pie(type_df, values="count", names="leave_type",
                         color="leave_type", color_discrete_map=LEAVE_COLORS, hole=0.45)
            fig.update_traces(
                textposition="inside", textinfo="percent+label",
                insidetextfont=dict(size=10),
                texttemplate="%{label}<br>%{percent}",
            )
            fig.update_layout(
                height=350,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

# ── Tab 3: By staff ───────────────────────────────────────────────────────────
with tab3:
    st.markdown("#### Leave summary per staff member")
    if not df.empty:
        grp_cols = ["name", "depot", "designation"]
        if has_route:  grp_cols.append("route_team")
        if has_vehicle: grp_cols.append("vehicle_type")

        staff_summary = (df.groupby(grp_cols)
                           .agg(total_weeks=("leave_type","count"),
                                leave_types=("leave_type", lambda x: ", ".join(sorted(x.unique()))))
                           .reset_index()
                           .sort_values("total_weeks", ascending=False))

        color_by = "route_team" if has_route else "depot"
        fig_staff = px.bar(staff_summary, x="name", y="total_weeks",
                           color=color_by, text="total_weeks",
                           labels={"name":"","total_weeks":"Weeks on leave"})
        fig_staff.update_traces(textposition="outside")
        fig_staff.update_layout(margin=dict(l=0,r=0,t=10,b=10),
                                plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                                xaxis_tickangle=-30)
        st.plotly_chart(fig_staff, use_container_width=True)

        st.markdown("#### Individual leave timeline")
        selected_person = st.selectbox("Select staff member", sorted(df["name"].unique()))
        person_df = df[df["name"] == selected_person].sort_values("week_start")
        if not person_df.empty:
            # Build full week spine so gaps show as zero (continuous line)
            all_wk_dates = pd.DataFrame({"week_start": filtered_weeks})
            leave_types  = person_df["leave_type"].unique()

            fig_tl = go.Figure()

            for lt in sorted(leave_types):
                lt_df = person_df[person_df["leave_type"] == lt]
                # Merge onto full week spine — 1 if on leave that week, 0 otherwise
                merged = all_wk_dates.merge(
                    lt_df[["week_start"]].assign(on_leave=1),
                    on="week_start", how="left"
                ).fillna(0)
                color = LEAVE_COLORS.get(lt, "#888")
                # Convert hex to rgba for transparent fill
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                fill_color = f"rgba({r},{g},{b},0.15)"
                fig_tl.add_trace(go.Scatter(
                    x=merged["week_start"],
                    y=merged["on_leave"],
                    mode="lines+markers",
                    name=lt,
                    line=dict(color=color, width=2, shape="hv"),
                    marker=dict(size=6, color=color),
                    fill="tozeroy",
                    fillcolor=fill_color,
                    hovertemplate=f"<b>{lt}</b><br>%{{x|%d %b %Y}}<br>On leave<extra></extra>",
                ))

            fig_tl.update_layout(
                height=220,
                margin=dict(l=0, r=0, t=10, b=10),
                plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(
                    type="date",
                    tickformat="%b %Y",
                    dtick="M1",
                    tickangle=-45, tickfont=dict(size=10),
                    showgrid=True, gridcolor="#f0f0f0",
                ),
                yaxis=dict(showticklabels=False, showgrid=False,
                           range=[-0.1, 1.4], zeroline=False),
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            xanchor="right", x=1),
                showlegend=True,
            )
            st.plotly_chart(fig_tl, use_container_width=True)

            info = person_df.iloc[0]
            meta = f"**{selected_person}** — {info['designation']} | Depot: {info['depot']}"
            if has_route and info.get("route_team"):
                meta += f" | Team: {info['route_team']}"
            if has_vehicle and info.get("vehicle_type"):
                meta += f" | Vehicle: {info['vehicle_type']}"
            st.markdown(meta)
            st.dataframe(
                person_df[["iso_week","week_start","leave_type"]].rename(
                    columns={"iso_week":"Week","week_start":"Week of","leave_type":"Leave type"}),
                use_container_width=True, hide_index=True)
    else:
        st.info("No data.")

# ── Tab 4: Raw data ───────────────────────────────────────────────────────────
with tab4:
    st.markdown("#### Full leave register")
    st.caption("Includes APS number and designation for each staff member — mirrors the Excel register.")
    if not df.empty:
        # Merge APS and designation from staff_list
        staff_meta = pd.DataFrame([
            {"name": s["name"], "APS Number": s["aps"], "Designation": s["designation"]}
            for s in staff_list
        ])
        display_df = df.merge(staff_meta, on="name", how="left")

        show_cols = ["name", "APS Number", "Designation",
                     "depot", "route_team", "vehicle_type",
                     "iso_week", "week_start", "leave_type", "month"]
        show_cols = [c for c in show_cols if c in display_df.columns]
        display_df = display_df[show_cols].copy()
        display_df["week_start"] = display_df["week_start"].dt.strftime("%d %b %Y")
        # Rename Unknown vehicle → N/A and Admin/Ops → Admin for display
        if "vehicle_type" in display_df.columns:
            display_df["vehicle_type"] = display_df["vehicle_type"].replace("Unknown", "N/A")
        if "depot" in display_df.columns:
            display_df["depot"] = display_df["depot"].replace("Admin/Ops", "Admin")
        display_df = display_df.rename(columns={
            "name":         "Name",
            "depot":        "Depot / Annexe",
            "route_team":   "Route team",
            "vehicle_type": "Vehicle",
            "iso_week":     "Week",
            "week_start":   "Week of",
            "leave_type":   "Leave type",
            "month":        "Month",
        })
        st.dataframe(
            display_df.sort_values(["Week", "Name"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Name":         st.column_config.TextColumn(width="medium"),
                "APS Number":   st.column_config.TextColumn(width="small"),
                "Designation":  st.column_config.TextColumn(width="small"),
                "Depot / Annexe": st.column_config.TextColumn(width="medium"),
                "Route team":   st.column_config.TextColumn(width="small"),
                "Vehicle":      st.column_config.TextColumn(width="small"),
                "Week":         st.column_config.TextColumn(width="small"),
                "Week of":      st.column_config.TextColumn(width="small"),
                "Leave type":   st.column_config.TextColumn(width="medium"),
                "Month":        st.column_config.TextColumn(width="small"),
            }
        )
        csv = display_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download as CSV", data=csv,
                           file_name="leave_register.csv", mime="text/csv")
    else:
        st.info("No data matches current filters.")

# ── Tab 5: Single Day Leave ──────────────────────────────────────────────────
with tab5:
    col_form, col_data = st.columns([1, 2])

    with col_form:
        all_staff_names = sorted(df_all["name"].dropna().unique().tolist())
        render_entry_form(all_staff_names)

    with col_data:
        sdl_fresh = load_single_day_leave()

        if not sdl_fresh.empty and "date" in sdl_fresh.columns:
            today    = pd.Timestamp.today().normalize()
            two_wks  = today + pd.Timedelta(days=14)

            # Next 2 weeks
            st.markdown("#### Next 2 weeks")
            sdl_soon = sdl_fresh[
                (sdl_fresh["date"] >= today) &
                (sdl_fresh["date"] <= two_wks)
            ].copy().sort_values("date")

            if not sdl_soon.empty:
                sdl_soon["date"] = sdl_soon["date"].dt.strftime("%a %d %b %Y")
                sdl_soon.columns = [c.replace("_"," ").title() for c in sdl_soon.columns]
                st.dataframe(sdl_soon, use_container_width=True, hide_index=True)
            else:
                st.info("No single day leave in the next 2 weeks.")

            # Full register
            st.markdown("#### Full register")
            display_sdl = sdl_fresh.copy().sort_values("date", ascending=False)
            display_sdl["date"] = display_sdl["date"].dt.strftime("%d %b %Y")
            display_sdl.columns = [c.replace("_"," ").title() for c in display_sdl.columns]
            st.dataframe(display_sdl, use_container_width=True, hide_index=True)

            csv = display_sdl.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download as CSV", data=csv,
                               file_name="single_day_leave.csv", mime="text/csv")
        else:
            st.info("No entries yet. Use the form on the left to add single day leave.")

st.divider()
st.caption("Built for Brisbane Central Stafford DC · Australia Post · Annual Leave Dashboard")
