# 📅 Annual Leave Dashboard — Stafford DC

**Brisbane Central — Australia Post**  
Built by Samet & Mark · Powered by Streamlit + Python

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Or visit: **stafford-leave.streamlit.app**

---

## 📁 File Structure

```
leave_dashboard/
├── app.py                          # Main Streamlit dashboard
├── data_parser.py                  # Excel leave data parser
├── single_day_leave.py             # Google Sheets integration
├── leave_data.xlsx                 # Annual leave data (Excel)
├── Australia_Post_logo_logotype.png
├── requirements.txt
└── README.md
```

---

## 📊 Data Sources

| Source | What it contains | How to update |
|--------|-----------------|---------------|
| `leave_data.xlsx` | Annual leave, LSL, parental leave etc. | Replace file on GitHub |
| Google Sheets | Single day / ad hoc leave | Dev enters via dashboard form |

### Excel Format
- Row 15: Headers (Staff Names, Depot, APS Number, Designation, Team, Vehicle Type, PT Hours)
- Row 16+: Staff data
- Columns 8+: Weekly leave grid (1 = Annual Leave, 2 = LSL, M = Parental, T = Training etc.)
- Each week = 6 columns (week marker + Mon–Fri)

### Leave Type Codes
| Code | Leave Type |
|------|-----------|
| 1 | Annual Leave |
| 2 | Long Service Leave |
| 3 | Purchased Leave (48/52) |
| 4 | Other Leave |
| M | Parental Leave |
| T | Training |
| TU | Time off in Lieu |
| W-F, TH-F, M-TU etc. | Partial week (Annual Leave) |

---

## 🎛️ Dashboard Features

### Time Period Filters
- **Monthly** — 13-month sliding window, default = current month
- **Weekly** — 52-week sliding window
- **Daily** — 20 working days sliding window, default = today

### Sidebar Filters
- Team / Area (depot)
- Route team (T1, T2, T3)
- Vehicle type (🏍️ Motorbike / 🚐 EDV / Both)
- Staff member (search + select all)
- Leave type

### Alert Thresholds
- **Max concurrent on leave** — weeks above this are flagged red/amber
- **Min motorbike on duty** — dotted line on graph
- **Min EDV on duty** — dotted line on graph
- **Min relief on duty** — dotted line on graph

### Charts & Views

#### ⚠️ Concurrent Leave — Staffing Load
- Monthly: 13 bars (one per month), future months shown as "📭 No data"
- Weekly: 52 bars with same no-data logic
- Daily: 20 working days, stacked by team/depot
- Threshold lines for max concurrent + vehicle minimums
- **🔍 Drill-down selector** — pick any period to see who's on leave

#### 📊 Analysis Tab
- Staff leave by team line chart (delivery teams over time)
- Leave type breakdown pie chart
- Staff on leave by month/week/day bar chart
- Concurrent leave over time by team

#### 📆 Calendar View
- Heatmap — each row = staff member, each column = week
- Colour-blind friendly palette
- Month labels top and bottom
- Alphabetical by SURNAME, Firstname

#### 👥 By Staff
- Leave summary per person
- Individual timeline (line chart, monthly x-axis)

#### 📋 Raw Data
- Full leave register with APS number, designation
- CSV export

#### 📝 Single Day Leave
- Entry form → saves directly to Google Sheets
- Next 2 weeks table
- Full register + CSV export

---

## 🔧 Configuration

### Google Sheets (Single Day Leave)
Sheet ID: `1cU7k5qS1NJdgWKawxqTvnBy8WxR_V3rVKcyzUaPHsgY`

Required columns in Sheet:
```
Name | Date | Leave_type | Notes
```

Streamlit Secrets required:
```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key = "..."
client_email = "..."
...
```

### Updating Leave Data
1. Replace `leave_data.xlsx` on GitHub
2. Dashboard auto-refreshes (cache TTL = 5 minutes)
3. Or use sidebar "Upload Excel file" button

---

## 🛠️ Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.14 | Core language |
| Streamlit | Web dashboard framework |
| Plotly | Interactive charts |
| Pandas | Data processing |
| openpyxl | Excel file reading |
| gspread | Google Sheets API |
| Google Auth | Service account auth |

---

## 📝 Single Day Leave — How to Add Entries

1. Open dashboard → **📝 Single Day Leave** tab
2. Select staff member from dropdown
3. Pick date
4. Select leave type (Sick Leave, Rostered Leave, Training etc.)
5. Add notes (optional)
6. Click **💾 Save** → instantly appears in Google Sheets

---

## 🚀 Deployment (Streamlit Cloud)

1. Push changes to GitHub: `SamcoAu88/leave-dashboard`
2. Streamlit auto-deploys within ~2 minutes
3. URL: **stafford-leave.streamlit.app**

---

*Built with ❤️ for Brisbane Central Stafford DC · Australia Post*
