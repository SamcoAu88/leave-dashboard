import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import tempfile

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


@st.cache_data
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
    week_labels = get_week_labels(all_weeks)
    week_map    = dict(zip(week_labels, all_weeks))   # "W03 2026" → datetime

    all_months = []
    seen_m = set()
    for wk in all_weeks:
        key = wk.strftime("%b %Y")
        if key not in seen_m:
            all_months.append(key)
            seen_m.add(key)

    # ── Time period ──
    period_type = st.radio("Time period", ["Monthly", "Weekly"], horizontal=True, label_visibility="collapsed")
    st.caption("Time period")

    if period_type == "Monthly":
        month_filter = st.select_slider(
            "Month range",
            options=all_months,
            value=(all_months[0], all_months[-1]),
            label_visibility="collapsed",
        )
        # Convert range to list
        i0 = all_months.index(month_filter[0])
        i1 = all_months.index(month_filter[1])
        month_filter = all_months[i0:i1+1]
        week_filter  = None
        st.caption(f"📅 {month_filter[0]} → {month_filter[-1]}  ({len(month_filter)} months)")
    else:
        week_filter  = st.select_slider(
            "Week range",
            options=week_labels,
            value=(week_labels[0], week_labels[-1]),
            label_visibility="collapsed",
        )
        i0 = week_labels.index(week_filter[0])
        i1 = week_labels.index(week_filter[1])
        week_filter  = week_labels[i0:i1+1]
        month_filter = None
        st.caption(f"📅 {week_filter[0]} → {week_filter[-1]}  ({len(week_filter)} weeks)")

    st.divider()

    # ── Depot ──
    all_depots = sorted(df_all["depot"].unique().tolist()) if not df_all.empty else []
    st.caption("Depot / Annexe")
    depot_filter = [d for d in all_depots
                    if st.checkbox(d, value=True, key=f"depot_{d}")]

    st.divider()

    # ── Route team ──
    has_route = df_all["route_team"].nunique() > 1 if not df_all.empty else False
    if has_route:
        all_route_teams = sorted(df_all["route_team"].dropna().unique().tolist())
        st.caption("Route team")
        cols_rt = st.columns(len(all_route_teams))
        route_team_filter = []
        for i, t in enumerate(all_route_teams):
            label = f"T{t}" if t not in ("", "No team") else "None"
            if cols_rt[i].checkbox(label, value=True, key=f"rt_{t}"):
                route_team_filter.append(t)
    else:
        route_team_filter = None

    # ── Vehicle type ──
    has_vehicle = df_all["vehicle_type"].nunique() > 1 if not df_all.empty else False
    if has_vehicle:
        all_vehicles = sorted(df_all["vehicle_type"].dropna().unique().tolist())
        st.caption("Vehicle type")
        veh_icons = {"Motorbike": "🏍️", "EDV": "🚐", "Both": "🔀", "Unknown": "❓"}
        vehicle_filter = []
        for v in all_vehicles:
            icon = veh_icons.get(v, "")
            if st.checkbox(f"{icon} {v}", value=True, key=f"veh_{v}"):
                vehicle_filter.append(v)
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
    threshold = st.slider("Max concurrent on leave", 1, 20, 3)
    st.caption("📊 Minimum staff on duty")
    min_motorbike = st.slider("🏍️ Motorbike", 0, 30, 0)
    min_edv       = st.slider("🚐 EDV",        0, 30, 0)
    min_relief    = st.slider("👤 Relief",      0, 20, 0)


# ── Apply filters ─────────────────────────────────────────────────────────────
if df_all.empty:
    st.error("No data found. Please check the Excel file.")
    st.stop()

df = df_all.copy()

# Time filter
if period_type == "Monthly" and month_filter:
    df = df[df["month"].isin(month_filter)]
    filtered_weeks = [wk for wk in all_weeks if wk.strftime("%b %Y") in month_filter]
elif period_type == "Weekly" and week_filter:
    df = df[df["iso_week"].isin(week_filter)]
    filtered_weeks = [week_map[w] for w in week_filter if w in week_map]
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
conc_df = concurrent_by_week(df, filtered_weeks)

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

# Total staff counts for minimum thresholds
total_motorbike = int((df_all["vehicle_type"] == "Motorbike").sum() / max(df_all["name"].nunique(), 1) * df_all["name"].nunique()) if not df_all.empty else 0
total_motorbike = df_all[df_all["vehicle_type"] == "Motorbike"]["name"].nunique() if not df_all.empty else 0
total_edv       = df_all[df_all["vehicle_type"] == "EDV"]["name"].nunique()        if not df_all.empty else 0
total_relief    = df_all[df_all["depot"] == "Relief"]["name"].nunique()             if not df_all.empty else 0

if not conc_df.empty:
    # X-axis labels: monthly view → "Feb 2026", weekly view → "09 Feb"
    def make_x_label(wk):
        if period_type == "Monthly":
            return wk.strftime("%b %Y")
        else:
            return wk.strftime("%d %b")

    conc_df["x_label"] = conc_df["week_start"].apply(make_x_label)

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
    for _, row in conc_df.iterrows():
        wk     = row["week_start"]
        wk_df_h = df[df["week_start"] == wk]

        # Full week vs partial
        full_wk  = wk_df_h[wk_df_h["leave_type"] == "Annual Leave"]
        partial  = wk_df_h[wk_df_h["leave_type"] == "Annual Leave (partial week)"]
        n_full   = len(full_wk)
        n_partial= len(partial)

        # Days lost — for partials use raw_value if available, else estimate
        days_full    = n_full * 5
        # Estimate partial days from leave_type label (we don't store raw here, use 3 as avg)
        days_partial = n_partial * 3
        days_other   = len(wk_df_h[~wk_df_h["leave_type"].isin(
                            ["Annual Leave","Annual Leave (partial week)"])]) * 5
        days_lost    = days_full + days_partial + days_other

        total = row["concurrent_count"]

        # Vehicle / relief availability
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

        # Partial detail
        partial_detail = f" ({days_partial} days)" if n_partial > 0 else ""

        h = (
            f"<b>{row['iso_week']}  —  {wk.strftime('%d %b %Y')}</b><br>"
            f"<b>{total} on leave</b>  ({n_full} full week  +  {n_partial} partial{partial_detail})<br>"
            f"≈ {days_lost} working days lost"
            + avail_line(mb_avail, min_motorbike, "Motorbike")
            + avail_line(edv_avail, min_edv,       "EDV")
            + avail_line(rel_avail, min_relief,    "Relief")
        )
        hover_texts.append(h)

    fig_load = go.Figure()
    fig_load.add_trace(go.Bar(
        x=conc_df["x_label"],
        y=conc_df["concurrent_count"],
        marker_color=bar_colors,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts,
        name="Staff on leave",
    ))
    fig_load.add_hline(
        y=threshold, line_dash="dash", line_color="#E24B4A", line_width=1.5,
        annotation_text=f"Max concurrent ({threshold})",
        annotation_position="top right", annotation_font_color="#E24B4A",
    )
    # Add minimum threshold lines
    if min_motorbike > 0:
        # How many motorbike riders on leave to breach the minimum
        breach_line = total_motorbike - min_motorbike
        if breach_line >= 0:
            fig_load.add_hline(
                y=breach_line, line_dash="dot", line_color="#378ADD", line_width=1.5,
                annotation_text=f"Motorbike min breach ({breach_line})",
                annotation_position="bottom right", annotation_font_color="#378ADD",
            )
    if min_edv > 0:
        breach_line = total_edv - min_edv
        if breach_line >= 0:
            fig_load.add_hline(
                y=breach_line, line_dash="dot", line_color="#1D9E75", line_width=1.5,
                annotation_text=f"EDV min breach ({breach_line})",
                annotation_position="bottom right", annotation_font_color="#1D9E75",
            )
    if min_relief > 0:
        breach_line = total_relief - min_relief
        if breach_line >= 0:
            fig_load.add_hline(
                y=breach_line, line_dash="dot", line_color="#D4537E", line_width=1.5,
                annotation_text=f"Relief min breach ({breach_line})",
                annotation_position="bottom right", annotation_font_color="#D4537E",
            )

    fig_load.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=10, b=10),
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickangle=-60, tickfont=dict(size=10), showgrid=False),
        yaxis=dict(title="Staff on leave", gridcolor="#f0f0f0", zeroline=False),
        showlegend=False,
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
tab1, tab2, tab3, tab4 = st.tabs(["📆 Calendar view", "📊 Analysis", "👥 By staff", "📋 Raw data"])

# ── Tab 1: Calendar ───────────────────────────────────────────────────────────
with tab1:
    st.markdown("#### Leave calendar — each row = staff member, each column = week")
    st.caption("Coloured = on leave. Numbers at bottom = concurrent count. Red = above threshold.")

    if not df.empty and filtered_weeks:
        display_names = [n for n in all_names if n in filtered_names]
        display_weeks = sorted(set(filtered_weeks))[:60]   # cap at 60 weeks for readability

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
                iso = f"W{wk.isocalendar()[1]:02d}"
                row_h.append(f"{name}<br>{iso} ({wk.strftime('%d %b %Y')})<br>{lt if lt else 'Working'}")
            z_vals.append(row_z)
            hover_text.append(row_h)

        week_labels_display = [f"W{wk.isocalendar()[1]:02d}" for wk in display_weeks]
        conc_row   = [conc_df[conc_df["week_start"] == wk]["concurrent_count"].sum() for wk in display_weeks]
        conc_hover = [f"{f'W{wk.isocalendar()[1]:02d}'} ({wk.strftime('%d %b %Y')})<br>{c} staff on leave"
                      for wk, c in zip(display_weeks, conc_row)]

        color_scale = [
            [0.00, "#f0f0f0"], [0.13, "#378ADD"], [0.26, "#1D9E75"],
            [0.39, "#D4537E"], [0.52, "#7F77DD"], [0.65, "#BA7517"],
            [0.78, "#D85A30"], [0.90, "#888780"], [1.00, "#888780"],
        ]

        fig_cal = go.Figure()
        fig_cal.add_trace(go.Heatmap(
            z=z_vals, x=week_labels_display, y=display_names,
            text=hover_text, hovertemplate="%{text}<extra></extra>",
            colorscale=color_scale, showscale=False, xgap=1, ygap=1,
            zmin=0, zmax=len(LEAVE_COLORS),
        ))
        conc_colors = ["#E24B4A" if c >= threshold else "#aaa" for c in conc_row]
        fig_cal.add_trace(go.Bar(
            x=week_labels_display, y=conc_row, name="Concurrent",
            marker_color=conc_colors, yaxis="y2", opacity=0.55,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=conc_hover, showlegend=False,
        ))
        n_staff = len(display_names)
        fig_cal.update_layout(
            height=max(350, n_staff * 30 + 160),
            margin=dict(l=0, r=0, t=10, b=10),
            xaxis=dict(tickangle=-60, tickfont=dict(size=10)),
            yaxis=dict(tickfont=dict(size=11)),
            yaxis2=dict(overlaying="y", side="right", showgrid=False,
                        showticklabels=False, range=[0, max(len(filtered_names), 1)]),
            plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_cal, use_container_width=True)

        st.markdown("**Legend:**")
        leg_cols = st.columns(len(LEAVE_COLORS))
        for i, (lt, color) in enumerate(LEAVE_COLORS.items()):
            with leg_cols[i]:
                st.markdown(f'<div style="background:{color};border-radius:4px;padding:4px 6px;font-size:11px;color:white;text-align:center">{lt}</div>',
                            unsafe_allow_html=True)
    else:
        st.info("No leave data matches the current filters.")

# ── Tab 2: Analysis ───────────────────────────────────────────────────────────
with tab2:
    col_l, col_r = st.columns(2)

    with col_l:
        if period_type == "Monthly":
            st.markdown("#### Staff on leave by month")
            if not df.empty:
                month_df = (df.groupby("month")
                              .agg(staff_count=("name", "nunique"),
                                   leave_weeks=("name", "count"))
                              .reset_index())
                month_df["month"] = pd.Categorical(month_df["month"], categories=all_months, ordered=True)
                month_df = month_df.sort_values("month")
                month_df["full_wks"]   = df[df["leave_type"]=="Annual Leave"].groupby("month")["name"].count().reindex(month_df["month"].astype(str)).fillna(0).values
                month_df["partial_wks"]= df[df["leave_type"]=="Annual Leave (partial week)"].groupby("month")["name"].count().reindex(month_df["month"].astype(str)).fillna(0).values
                month_df["days_lost"]  = month_df["full_wks"]*5 + month_df["partial_wks"]*3 + (month_df["leave_weeks"]-month_df["full_wks"]-month_df["partial_wks"])*5
                month_df["hover"] = month_df.apply(
                    lambda r: (f"<b>{r['month']}</b><br>"
                               f"<b>{int(r['staff_count'])} staff on leave</b><br>"
                               f"{int(r['full_wks'])} full week  +  {int(r['partial_wks'])} partial<br>"
                               f"≈ {int(r['days_lost'])} working days lost"), axis=1)
                fig = go.Figure(go.Bar(
                    x=month_df["month"],
                    y=month_df["staff_count"],
                    marker_color=month_df["staff_count"],
                    marker_colorscale=["#85B7EB","#378ADD","#E24B4A"],
                    hovertemplate="%{customdata}<extra></extra>",
                    customdata=month_df["hover"],
                ))
                fig.update_layout(margin=dict(l=0,r=0,t=10,b=10),
                                  yaxis_title="Unique staff on leave",
                                  plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                                  xaxis_tickangle=-45)
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
            fig.update_traces(textposition="outside", textinfo="label+percent")
            fig.update_layout(margin=dict(l=0,r=0,t=10,b=10), paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # Team / vehicle breakdown (only if columns exist)
    if has_route or has_vehicle:
        st.markdown("---")
        bc1, bc2 = st.columns(2)
        if has_route and not df.empty:
            with bc1:
                st.markdown("#### Leave by route team")
                rt_df = df.groupby("route_team").size().reset_index(name="weeks").sort_values("weeks", ascending=False)
                fig = px.bar(rt_df, x="route_team", y="weeks", text="weeks",
                             color="route_team",
                             labels={"route_team":"Route team","weeks":"Leave weeks"})
                fig.update_traces(textposition="outside")
                fig.update_layout(showlegend=False, margin=dict(l=0,r=0,t=10,b=10),
                                  plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

        if has_vehicle and not df.empty:
            with bc2:
                st.markdown("#### Leave weeks by vehicle type")
                vt_df = (df.groupby("vehicle_type")
                           .agg(weeks=("name","count"),
                                staff=("name","nunique"))
                           .reset_index()
                           .sort_values("weeks", ascending=False))
                vcolors = {"Motorbike":"#378ADD","EDV":"#1D9E75","Both":"#7F77DD","Unknown":"#888780"}
                vt_df["color"] = vt_df["vehicle_type"].map(vcolors).fillna("#888780")
                vt_df["hover"] = vt_df.apply(
                    lambda r: f"<b>{r['vehicle_type']}</b><br>{r['weeks']} leave weeks<br>{r['staff']} unique staff", axis=1)
                fig_v = go.Figure(go.Bar(
                    x=vt_df["vehicle_type"], y=vt_df["weeks"],
                    marker_color=vt_df["color"],
                    text=vt_df["weeks"], textposition="outside",
                    hovertemplate="%{customdata}<extra></extra>",
                    customdata=vt_df["hover"],
                ))
                # Add minimum threshold lines
                if min_motorbike > 0:
                    fig_v.add_hline(y=min_motorbike * 4, line_dash="dot",
                                    line_color="#378ADD", line_width=1.5,
                                    annotation_text=f"Motorbike min threshold",
                                    annotation_font_color="#378ADD")
                if min_edv > 0:
                    fig_v.add_hline(y=min_edv * 4, line_dash="dot",
                                    line_color="#1D9E75", line_width=1.5,
                                    annotation_text=f"EDV min threshold",
                                    annotation_font_color="#1D9E75")
                fig_v.update_layout(showlegend=False, margin=dict(l=0,r=0,t=10,b=10),
                                    plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_v, use_container_width=True)

    st.markdown("#### Concurrent leave over time — by vehicle type")
    if not conc_df.empty and not df.empty:
        # Per week, count how many motorbike/edv/relief ON LEAVE
        wk_breakdown = []
        for wk in filtered_weeks:
            wk_df_b = df[df["week_start"] == wk]
            mb = wk_df_b[wk_df_b["vehicle_type"] == "Motorbike"]["name"].nunique()
            edv= wk_df_b[wk_df_b["vehicle_type"] == "EDV"]["name"].nunique()
            oth= wk_df_b[~wk_df_b["vehicle_type"].isin(["Motorbike","EDV"])]["name"].nunique()
            wk_breakdown.append({"week_start": wk,
                                  "iso_week": f"W{wk.isocalendar()[1]:02d}",
                                  "Motorbike": mb, "EDV": edv, "Other/Both": oth})
        bkdn_df = pd.DataFrame(wk_breakdown)

        fig_conc = go.Figure()
        bkdn_df["x_label"] = bkdn_df["week_start"].apply(
            lambda w: w.strftime("%b %Y") if period_type == "Monthly" else w.strftime("%d %b"))
        fig_conc.add_trace(go.Bar(x=bkdn_df["x_label"], y=bkdn_df["Motorbike"],
                                   name="Motorbike", marker_color="#378ADD"))
        fig_conc.add_trace(go.Bar(x=bkdn_df["x_label"], y=bkdn_df["EDV"],
                                   name="EDV", marker_color="#1D9E75"))
        fig_conc.add_trace(go.Bar(x=bkdn_df["x_label"], y=bkdn_df["Other/Both"],
                                   name="Other/Both", marker_color="#888780"))

        # threshold line
        fig_conc.add_hline(y=threshold, line_dash="dash", line_color="#E24B4A",
                            line_width=1.5,
                            annotation_text=f"Max concurrent ({threshold})",
                            annotation_position="top right",
                            annotation_font_color="#E24B4A")
        # minimum lines
        if min_motorbike > 0:
            fig_conc.add_hline(y=min_motorbike, line_dash="dot", line_color="#378ADD",
                                line_width=1.5,
                                annotation_text=f"Min motorbike on leave to breach ({min_motorbike})",
                                annotation_position="bottom left",
                                annotation_font_color="#378ADD")
        if min_edv > 0:
            fig_conc.add_hline(y=min_edv, line_dash="dot", line_color="#1D9E75",
                                line_width=1.5,
                                annotation_text=f"Min EDV on leave to breach ({min_edv})",
                                annotation_position="bottom left",
                                annotation_font_color="#1D9E75")

        fig_conc.update_layout(
            barmode="stack", height=300,
            margin=dict(l=0,r=0,t=10,b=10),
            plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(tickangle=-60, tickfont=dict(size=10)),
            yaxis_title="Staff on leave",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_conc, use_container_width=True)

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

        st.markdown("#### Individual timeline")
        selected_person = st.selectbox("Select staff member", sorted(df["name"].unique()))
        person_df = df[df["name"] == selected_person].sort_values("week_start")
        if not person_df.empty:
            tl_data = [{"Task": r["leave_type"], "Start": r["week_start"],
                        "Finish": r["week_start"] + timedelta(days=4), "Leave type": r["leave_type"]}
                       for _, r in person_df.iterrows()]
            tl_df = pd.DataFrame(tl_data)
            fig_tl = px.timeline(tl_df, x_start="Start", x_end="Finish", y="Task",
                                 color="Leave type", color_discrete_map=LEAVE_COLORS)
            fig_tl.update_yaxes(autorange="reversed")
            fig_tl.update_layout(margin=dict(l=0,r=0,t=10,b=10),
                                 plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)")
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
    if not df.empty:
        show_cols = ["name","depot","designation","route_team","vehicle_type",
                     "iso_week","week_start","leave_type","month"]
        show_cols = [c for c in show_cols if c in df.columns]
        display_df = df[show_cols].copy()
        display_df["week_start"] = display_df["week_start"].dt.strftime("%d %b %Y")
        display_df = display_df.rename(columns={
            "name":"Name","depot":"Depot","designation":"Designation",
            "route_team":"Route team","vehicle_type":"Vehicle",
            "iso_week":"Week","week_start":"Week of",
            "leave_type":"Leave type","month":"Month"
        })
        st.dataframe(display_df.sort_values(["Week","Name"]), use_container_width=True, hide_index=True)
        csv = display_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download as CSV", data=csv,
                           file_name="leave_register.csv", mime="text/csv")
    else:
        st.info("No data matches current filters.")

st.divider()
st.caption("Built for Brisbane Central Stafford DC · Australia Post · Annual Leave Dashboard")
