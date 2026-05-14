import streamlit as st
import json
import csv
import io
import uuid
import base64
import pandas as pd
from datetime import date
from pathlib import Path
from st_aggrid import AgGrid, GridUpdateMode
from st_aggrid.grid_options_builder import GridOptionsBuilder

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Internal Process Meeting",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_FILE = Path("todos.json")
LOGO_PATH = Path("assets/logo.png")

PEOPLE = {
    "AM": {"color": "#ffffff", "bg": "#692730"},
    "DV": {"color": "#ffffff", "bg": "#2d4875"},
    "MC": {"color": "#ffffff", "bg": "#1d6b52"},
    "PA": {"color": "#ffffff", "bg": "#7a4a1e"},
}

STATUS_META = {
    "Open":            {"color": "#1d4a8a", "bg": "#edf2fc", "border": "#c5d5f0"},
    "In Progress":     {"color": "#7a5a08", "bg": "#fef8e3", "border": "#e8cc70"},
    "Waiting on Them": {"color": "#8a3a0a", "bg": "#fef0e3", "border": "#f0b880"},
    "Done":            {"color": "#1a5a38", "bg": "#edf7f0", "border": "#a0d8b8"},
}

CATEGORIES = ["Operational", "Pipeline Co-Investments / FoF", "Pipeline Consignado"]

GRID_CSS = {
    ".ag-root-wrapper": {
        "border": "1px solid #ddd8d0 !important",
        "border-radius": "8px !important",
        "overflow": "hidden !important",
        "font-family": "'DM Sans', sans-serif !important",
    },
    ".ag-header": {
        "background-color": "#f7f5f0 !important",
        "border-bottom": "1px solid #ddd8d0 !important",
    },
    ".ag-header-cell-text": {
        "color": "#a09080 !important",
        "font-size": "0.62rem !important",
        "text-transform": "uppercase !important",
        "letter-spacing": "0.09em !important",
        "font-weight": "600 !important",
        "font-family": "'JetBrains Mono', monospace !important",
    },
    ".ag-row": {"background-color": "#ffffff !important"},
    ".ag-row-odd": {"background-color": "#faf8f4 !important"},
    ".ag-row-hover": {"background-color": "#f8f0ee !important"},
    ".ag-row-selected": {"background-color": "#f5e8e8 !important"},
    ".ag-cell": {
        "font-size": "0.81rem !important",
        "color": "#2a2018 !important",
        "border-right-color": "#f0ece5 !important",
        "line-height": "1.4 !important",
        "padding-top": "6px !important",
        "padding-bottom": "6px !important",
    },
    ".ag-cell-focus": {
        "border": "1px solid #692730 !important",
        "outline": "none !important",
    },
    ".ag-cell-inline-editing": {
        "border": "2px solid #692730 !important",
        "box-shadow": "0 2px 12px rgba(105,39,48,0.18) !important",
        "background": "#ffffff !important",
        "padding": "0 !important",
    },
    ".ag-input-field-input": {
        "font-size": "0.82rem !important",
        "color": "#1a1512 !important",
        "padding": "4px 8px !important",
    },
    ".ag-popup-editor": {
        "border": "1.5px solid #692730 !important",
        "box-shadow": "0 4px 16px rgba(105,39,48,0.15) !important",
        "border-radius": "6px !important",
    },
    ".ag-select-list-item": {
        "font-size": "0.80rem !important",
        "color": "#2a2018 !important",
    },
    ".ag-select-list-item:hover": {
        "background-color": "#f8f0ee !important",
    },
}

# ── Persistence ───────────────────────────────────────────────────────────────

def load_data() -> list[dict]:
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(todos: list[dict]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(todos, f, indent=2, ensure_ascii=False)

def init_state() -> None:
    if "todos" not in st.session_state:
        st.session_state.todos = load_data()
    if "inline_add_owner" not in st.session_state:
        st.session_state.inline_add_owner = None
    if "show_done" not in st.session_state:
        st.session_state.show_done = True
    if "show_new_form" not in st.session_state:
        st.session_state.show_new_form = False

def flush() -> None:
    save_data(st.session_state.todos)

def get_todo(todo_id: str) -> dict | None:
    return next((t for t in st.session_state.todos if t["id"] == todo_id), None)

def upsert_todo(data: dict) -> None:
    todos = st.session_state.todos
    idx = next((i for i, t in enumerate(todos) if t["id"] == data["id"]), None)
    if idx is None:
        todos.append(data)
    else:
        todos[idx] = data
    flush()

def delete_todo(todo_id: str) -> None:
    st.session_state.todos = [t for t in st.session_state.todos if t["id"] != todo_id]
    flush()

def open_count(todos: list[dict]) -> int:
    return sum(1 for t in todos if t["status"] != "Done")

# ── AG Grid helpers ───────────────────────────────────────────────────────────

def todos_to_df(todos: list[dict], include_owner: bool = True) -> pd.DataFrame:
    rows = []
    for t in todos:
        row = {
            "id":          t["id"],
            "company":     t.get("company", ""),
            "description": t.get("description", ""),
            "status":      t.get("status", "Open"),
            "waiting":     "Yes" if t.get("waiting_on_them") else "No",
            "notes":       t.get("notes", ""),
            "updated":     t.get("updated", ""),
            "category":    t.get("category", CATEGORIES[0]),
        }
        if include_owner:
            row["owner"] = t.get("owner", "")
        rows.append(row)
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["id", "company", "description", "status", "waiting",
                 "notes", "updated", "category"] + (["owner"] if include_owner else [])
    )

def build_grid_options(df: pd.DataFrame, include_owner: bool = True) -> dict:
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        editable=False, resizable=True, sortable=False,
        filter=False, suppressMenu=True, suppressMovable=True,
    )

    gb.configure_column("id",       hide=True)
    gb.configure_column("category", hide=True)
    gb.configure_column("updated",  headerName="Updated", width=95, editable=False,
                        cellStyle={"color": "#b0a898", "fontSize": "0.65rem",
                                   "fontFamily": "'JetBrains Mono', monospace"})

    if include_owner:
        gb.configure_column(
            "owner", headerName="Owner", width=80, editable=True,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": list(PEOPLE.keys())},
            cellStyle={"fontFamily": "'JetBrains Mono', monospace",
                       "fontWeight": "600", "fontSize": "0.72rem"},
        )

    gb.configure_column(
        "company", headerName="Company", width=105, editable=True,
        cellStyle={"fontFamily": "'JetBrains Mono', monospace",
                   "fontSize": "0.70rem", "color": "#7a6e60",
                   "textTransform": "uppercase", "letterSpacing": "0.06em"},
    )
    gb.configure_column(
        "description", headerName="To-Do", flex=3, editable=True,
        wrapText=True, autoHeight=True,
    )
    gb.configure_column(
        "status", headerName="Status", width=145, editable=True,
        cellEditor="agSelectCellEditor",
        cellEditorParams={"values": list(STATUS_META.keys())},
        cellStyle={"fontSize": "0.72rem"},
    )
    gb.configure_column(
        "waiting", headerName="⏳ Waiting", width=95, editable=True,
        cellEditor="agSelectCellEditor",
        cellEditorParams={"values": ["No", "Yes"]},
        cellStyle={"fontSize": "0.72rem", "color": "#8a3a0a"},
    )
    gb.configure_column(
        "notes", headerName="Notes", flex=2, editable=True,
        wrapText=True, autoHeight=True,
        cellStyle={"fontStyle": "italic", "color": "#8a7e78", "fontSize": "0.75rem"},
    )

    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_grid_options(
        domLayout="autoHeight",
        rowHeight=48,
        headerHeight=34,
        stopEditingWhenCellsLoseFocus=True,
        enableCellTextSelection=True,
        ensureDomOrder=True,
    )
    return gb.build()

def render_aggrid(todos_subset: list[dict], include_owner: bool = True,
                  grid_key: str = "grid") -> tuple[pd.DataFrame | None, str | None]:
    if not todos_subset:
        st.markdown('<div style="font-size:0.78rem;color:#a09080;padding:0.5rem 0">'
                    'No items.</div>', unsafe_allow_html=True)
        return None, None

    df = todos_to_df(todos_subset, include_owner=include_owner)
    go = build_grid_options(df, include_owner=include_owner)

    response = AgGrid(
        df,
        gridOptions=go,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        theme="alpine",
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=False,
        custom_css=GRID_CSS,
        key=grid_key,
    )

    # Extract selected row ID
    selected_id = None
    sel = response.get("selected_rows")
    if sel is not None:
        if isinstance(sel, pd.DataFrame) and not sel.empty:
            selected_id = str(sel.iloc[0].get("id", ""))
        elif isinstance(sel, list) and len(sel) > 0:
            selected_id = str(sel[0].get("id", ""))

    return response.get("data"), selected_id

def sync_grid(grid_data: pd.DataFrame | None, scope_ids: list[str]) -> bool:
    """Compare grid_data with session_state, persist any edits. Returns True if changed."""
    if grid_data is None or grid_data.empty:
        return False

    changed = False
    for _, row in grid_data.iterrows():
        tid = str(row.get("id", ""))
        if tid not in scope_ids:
            continue
        t = get_todo(tid)
        if t is None:
            continue

        for grid_col, todo_field in [
            ("company",     "company"),
            ("description", "description"),
            ("status",      "status"),
            ("notes",       "notes"),
        ]:
            nv = str(row.get(grid_col, "") or "").strip()
            ov = str(t.get(todo_field, "") or "").strip()
            if nv and nv != ov:
                t[todo_field] = nv
                t["updated"] = str(date.today())
                changed = True

        if "owner" in grid_data.columns:
            nv = str(row.get("owner", "") or "").strip()
            if nv in PEOPLE and nv != t.get("owner", ""):
                t["owner"] = nv
                t["updated"] = str(date.today())
                changed = True

        nv_wait = str(row.get("waiting", "No")).strip() == "Yes"
        ov_wait = bool(t.get("waiting_on_them", False))
        if nv_wait != ov_wait:
            t["waiting_on_them"] = nv_wait
            t["updated"] = str(date.today())
            changed = True

        # Keep waiting_on_them consistent with status
        if t.get("status") == "Waiting on Them" and not t.get("waiting_on_them"):
            t["waiting_on_them"] = True
            changed = True

    if changed:
        flush()
    return changed

# ── Logo ──────────────────────────────────────────────────────────────────────

def get_logo_html() -> str:
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" style="height:38px">'
    return '<span class="sg-logo-text">SIGULER GUFF</span>'

# ── CSS ───────────────────────────────────────────────────────────────────────

def inject_css() -> None:
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500&family=Cinzel:wght@400;600&display=swap');

html, body, [class*="css"], .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #f7f5f0 !important;
    color: #1a1512 !important;
}
.stApp { background-color: #f7f5f0 !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 2.5rem 4rem 2.5rem !important; max-width: 1600px; }
section[data-testid="stSidebar"] { display: none; }

.sg-logo-text {
    font-family: 'Cinzel', serif;
    font-size: 1.5rem; font-weight: 600;
    color: #692730; letter-spacing: 0.05em;
}

/* ── Header ── */
.sg-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.8rem 0 1.4rem 0;
    border-bottom: 1.5px solid #ddd8d0; margin-bottom: 1.6rem;
}
.sg-header-left h1 {
    font-size: 1.2rem; font-weight: 600; color: #1a1512; margin: 0 0 3px 0;
}
.sg-header-left p {
    font-size: 0.7rem; color: #a09080;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.08em; text-transform: uppercase; margin: 0;
}

/* ── Stat cards ── */
.sg-stats { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.sg-stat {
    flex: 1; min-width: 120px;
    background: #ffffff; border: 1px solid #ddd8d0;
    border-radius: 10px; padding: 1rem 1.2rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.sg-stat-value {
    font-size: 1.85rem; font-weight: 700; color: #1a1512;
    font-family: 'JetBrains Mono', monospace; line-height: 1;
}
.sg-stat-label {
    font-size: 0.62rem; font-weight: 500; color: #a09080;
    text-transform: uppercase; letter-spacing: 0.1em; margin-top: 5px;
}

/* ── Person card ── */
.sg-person-card {
    background: #ffffff; border: 1px solid #ddd8d0;
    border-radius: 12px; padding: 1.1rem 1.3rem; margin-bottom: 1.2rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.sg-person-header {
    display: flex; align-items: center; gap: 0.75rem;
    margin-bottom: 0.9rem; padding-bottom: 0.8rem;
    border-bottom: 1px solid #f0ece5;
}
.sg-badge {
    width: 34px; height: 34px; border-radius: 7px;
    display: inline-flex; align-items: center; justify-content: center;
    font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
    font-weight: 700; letter-spacing: 0.03em; flex-shrink: 0;
}
.sg-person-name  { font-size: 0.85rem; font-weight: 600; color: #1a1512; }
.sg-person-count { font-size: 0.67rem; color: #a09080;
    font-family: 'JetBrains Mono', monospace; margin-top: 1px; }

/* ── Category header ── */
.sg-category-header {
    font-size: 0.67rem; font-weight: 700; color: #692730;
    text-transform: uppercase; letter-spacing: 0.12em;
    padding: 0.4rem 0; border-bottom: 1.5px solid #ddd8d0;
    margin: 1.2rem 0 0.5rem 0; font-family: 'JetBrains Mono', monospace;
}

/* ── Tabs ── */
div[data-testid="stTabs"] [role="tab"] {
    font-size: 0.73rem !important; font-weight: 600 !important;
    letter-spacing: 0.07em !important; text-transform: uppercase !important;
    color: #a09080 !important; padding: 0.5rem 1.2rem !important;
}
div[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #692730 !important; border-bottom: 2px solid #692730 !important;
}
div[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid #ddd8d0 !important; background: transparent !important;
}

/* ── Buttons ── */
.stButton > button {
    background: #ffffff !important; border: 1px solid #ddd8d0 !important;
    color: #7a6e66 !important; font-size: 0.70rem !important;
    font-family: 'DM Sans', sans-serif !important;
    border-radius: 6px !important; padding: 3px 10px !important;
    box-shadow: none !important; transition: all 0.14s !important;
}
.stButton > button:hover {
    border-color: #692730 !important; color: #692730 !important;
    background: #f8f0ee !important;
}
.stButton > button[kind="primary"] {
    background: #692730 !important; border-color: #692730 !important;
    color: #ffffff !important; font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover {
    background: #7d3038 !important; border-color: #7d3038 !important;
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: #faf8f4 !important; color: #1a1512 !important;
    border-color: #ddd8d0 !important; border-radius: 6px !important;
    font-size: 0.82rem !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #692730 !important;
    box-shadow: 0 0 0 2px rgba(105,39,48,0.10) !important;
}
.stSelectbox > div > div {
    background: #faf8f4 !important; color: #1a1512 !important;
    border-color: #ddd8d0 !important; border-radius: 6px !important;
}
label {
    font-size: 0.67rem !important; color: #a09080 !important;
    text-transform: uppercase !important; letter-spacing: 0.08em !important;
}
.stCheckbox label {
    font-size: 0.78rem !important; color: #5a4e48 !important;
    text-transform: none !important; letter-spacing: 0 !important;
}
.stMultiSelect > div { border-color: #ddd8d0 !important; background: #faf8f4 !important; }
.stMultiSelect [data-baseweb="tag"] { background: #f8eeec !important; color: #692730 !important; }

/* ── Expander ── */
details > summary {
    background: #ffffff !important; border: 1px solid #ddd8d0 !important;
    border-radius: 8px !important; font-size: 0.8rem !important;
    color: #4a3e38 !important; font-weight: 500 !important;
}

/* ── Company stats ── */
.sg-company-stats { display: flex; gap: 1.2rem; flex-wrap: wrap; margin-top: 0.4rem; }
.sg-company-stat { font-size: 0.67rem; color: #a09080; font-family: 'JetBrains Mono', monospace; }
.sg-company-stat b { color: #4a3e38; }

/* ── Weekly summary ── */
.sg-summary-block {
    background: #ffffff; border: 1px solid #ddd8d0; border-radius: 10px;
    padding: 1.4rem 1.6rem; font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem; color: #4a3e38; line-height: 1.8;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}

/* ── Hint text under grid ── */
.sg-grid-hint {
    font-size: 0.63rem; color: #c0b8b0;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 4px; letter-spacing: 0.04em;
}

hr { border-color: #e8e2d8 !important; }
</style>
""", unsafe_allow_html=True)

# ── Small HTML builders ───────────────────────────────────────────────────────

def badge_html(owner: str, size: int = 34) -> str:
    p = PEOPLE.get(owner, {"color": "#fff", "bg": "#888"})
    return (f'<span class="sg-badge" style="background:{p["bg"]};color:{p["color"]};'
            f'width:{size}px;height:{size}px">{owner}</span>')

def status_html(status: str) -> str:
    m = STATUS_META.get(status, STATUS_META["Open"])
    return (f'<span style="display:inline-block;font-size:0.6rem;font-weight:600;'
            f'letter-spacing:0.08em;text-transform:uppercase;padding:2px 7px;'
            f'border-radius:4px;border:1px solid {m["border"]};'
            f'background:{m["bg"]};color:{m["color"]};'
            f'font-family:\'JetBrains Mono\',monospace">{status}</span>')

# ── Header / stats ────────────────────────────────────────────────────────────

def render_header() -> None:
    st.markdown(f"""
<div class="sg-header">
  <div class="sg-header-left">
    <h1>Internal Process Meeting</h1>
    <p>Weekly Review &nbsp;·&nbsp; Monday, May 19, 2026</p>
  </div>
  <div>{get_logo_html()}</div>
</div>
""", unsafe_allow_html=True)

def render_stats(todos: list[dict]) -> None:
    total   = len(todos)
    open_   = sum(1 for t in todos if t["status"] == "Open")
    inp     = sum(1 for t in todos if t["status"] == "In Progress")
    waiting = sum(1 for t in todos if t.get("waiting_on_them"))
    done    = sum(1 for t in todos if t["status"] == "Done")
    st.markdown(f"""
<div class="sg-stats">
  <div class="sg-stat">
    <div class="sg-stat-value">{total}</div>
    <div class="sg-stat-label">Total Items</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#1d4a8a">{open_}</div>
    <div class="sg-stat-label">Open</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#7a5a08">{inp}</div>
    <div class="sg-stat-label">In Progress</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#b87820">{waiting}</div>
    <div class="sg-stat-label">Ball in Their Court</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#1a5a38">{done}</div>
    <div class="sg-stat-label">Done</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── New todo form ─────────────────────────────────────────────────────────────

def render_new_form(default_owner: str = "AM", kp: str = "") -> None:
    ca, cb = st.columns([2, 3])
    with ca:
        company  = st.text_input("Company",  key=f"{kp}nco")
        owner    = st.selectbox("Owner", list(PEOPLE.keys()),
                                index=list(PEOPLE.keys()).index(default_owner),
                                key=f"{kp}nown")
        category = st.selectbox("Category", CATEGORIES, key=f"{kp}ncat")
        status   = st.selectbox("Status",   list(STATUS_META.keys()), key=f"{kp}nst")
    with cb:
        description = st.text_area("Description", height=72, key=f"{kp}ndesc")
        notes       = st.text_area("Notes",       height=72, key=f"{kp}nnotes")
    waiting = st.checkbox("Ball in Their Court", key=f"{kp}nw")
    bs, bc, _ = st.columns([1.3, 1.3, 6])
    with bs:
        if st.button("Add", key=f"{kp}nsave", type="primary"):
            if description.strip() and company.strip():
                upsert_todo({
                    "id":              str(uuid.uuid4()),
                    "owner":           owner,
                    "company":         company.strip().upper(),
                    "description":     description.strip(),
                    "status":          status,
                    "category":        category,
                    "waiting_on_them": waiting or status == "Waiting on Them",
                    "notes":           notes.strip(),
                    "created":         str(date.today()),
                    "updated":         str(date.today()),
                })
                st.session_state.inline_add_owner = None
                st.session_state.show_new_form    = False
                st.rerun()
            else:
                st.warning("Description and Company are required.")
    with bc:
        if st.button("Cancel", key=f"{kp}ncancel"):
            st.session_state.inline_add_owner = None
            st.session_state.show_new_form    = False
            st.rerun()

# ── Tab: By Person ────────────────────────────────────────────────────────────

def render_by_person(todos: list[dict]) -> None:
    show_done = st.session_state.show_done

    ct, cn, _ = st.columns([2, 2, 8])
    with ct:
        if st.button("Hide Done" if show_done else "Show Done", key="tog_done"):
            st.session_state.show_done = not show_done
            st.rerun()
    with cn:
        if st.button("＋ New To-Do", key="bp_new"):
            st.session_state.show_new_form = not st.session_state.show_new_form
            st.rerun()

    if st.session_state.show_new_form:
        st.markdown('<div style="background:#fff;border:1px solid #ddd8d0;border-radius:10px;'
                    'padding:1rem 1.2rem;margin:0.7rem 0 1rem 0">'
                    '<div style="font-size:0.67rem;font-weight:700;color:#692730;'
                    'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.6rem;'
                    'font-family:\'JetBrains Mono\',monospace">New To-Do</div>',
                    unsafe_allow_html=True)
        render_new_form(kp="top_")
        st.markdown("</div>", unsafe_allow_html=True)

    cols = st.columns(2)
    for col_idx, (owner, meta) in enumerate(PEOPLE.items()):
        person_todos = [t for t in todos if t["owner"] == owner]
        visible      = [t for t in person_todos if t["status"] != "Done" or show_done]
        open_c       = open_count(person_todos)

        with cols[col_idx % 2]:
            st.markdown(f"""
<div class="sg-person-card">
  <div class="sg-person-header">
    {badge_html(owner)}
    <div>
      <div class="sg-person-name">{owner}</div>
      <div class="sg-person-count">{open_c} open &nbsp;·&nbsp; {len(person_todos)} total</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            scope_ids = [t["id"] for t in visible]
            grid_data, selected_id = render_aggrid(
                visible,
                include_owner=False,
                grid_key=f"grid_{owner}",
            )

            if grid_data is not None and sync_grid(grid_data, scope_ids):
                st.rerun()

            # Row actions (operate on selected row)
            action_cols = st.columns([2.5, 2.5, 2, 6])
            with action_cols[0]:
                if selected_id:
                    t = get_todo(selected_id)
                    if t:
                        lbl = "↩ Reopen" if t["status"] == "Done" else "✓ Mark Done"
                        if st.button(lbl, key=f"bp_toggle_{owner}"):
                            new_s = "Open" if t["status"] == "Done" else "Done"
                            t["status"] = new_s
                            t["waiting_on_them"] = False
                            t["updated"] = str(date.today())
                            flush()
                            st.rerun()
            with action_cols[1]:
                if selected_id:
                    if st.button("✕ Delete", key=f"bp_del_{owner}"):
                        delete_todo(selected_id)
                        st.rerun()

            st.markdown('<div class="sg-grid-hint">↑ Click to select row &nbsp;·&nbsp; '
                        'Double-click a cell to edit &nbsp;·&nbsp; Enter or Tab to save</div>',
                        unsafe_allow_html=True)

            # Per-person quick-add
            st.markdown("<div style='margin-top:0.5rem'>", unsafe_allow_html=True)
            if st.session_state.inline_add_owner == owner:
                st.markdown('<div style="background:#fff;border:1px solid #ddd8d0;'
                            'border-radius:8px;padding:0.9rem 1rem">'
                            f'<div style="font-size:0.64rem;font-weight:700;color:#692730;'
                            f'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;'
                            f'font-family:\'JetBrains Mono\',monospace">Add for {owner}</div>',
                            unsafe_allow_html=True)
                render_new_form(default_owner=owner, kp=f"per_{owner}_")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                if st.button(f"＋ Add for {owner}", key=f"add_{owner}"):
                    st.session_state.inline_add_owner = owner
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# ── Tab: All To-Dos ───────────────────────────────────────────────────────────

def render_all_todos(todos: list[dict]) -> None:
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 2, 2, 3])
    with fc1:
        f_owner   = st.multiselect("Owner",   list(PEOPLE.keys()),      key="f_owner")
    with fc2:
        companies = sorted({t["company"] for t in todos})
        f_company = st.multiselect("Company", companies,                 key="f_company")
    with fc3:
        f_status  = st.multiselect("Status",  list(STATUS_META.keys()), key="f_status")
    with fc4:
        f_waiting = st.checkbox("Waiting on Them only",                  key="f_waiting")
    with fc5:
        f_search  = st.text_input("Search", placeholder="keyword…",      key="f_search")

    filtered = todos
    if f_owner:   filtered = [t for t in filtered if t["owner"]   in f_owner]
    if f_company: filtered = [t for t in filtered if t["company"] in f_company]
    if f_status:  filtered = [t for t in filtered if t["status"]  in f_status]
    if f_waiting: filtered = [t for t in filtered if t.get("waiting_on_them")]
    if f_search:
        kw = f_search.lower()
        filtered = [t for t in filtered
                    if kw in t["description"].lower()
                    or kw in t["company"].lower()
                    or kw in t.get("notes", "").lower()]

    if not filtered:
        st.info("No items match the current filters.")
        return

    for category in CATEGORIES:
        cat_items = [t for t in filtered
                     if t.get("category", CATEGORIES[0]) == category]
        if not cat_items:
            continue

        st.markdown(
            f'<div class="sg-category-header">{category}'
            f'&nbsp;·&nbsp;{len(cat_items)} items</div>',
            unsafe_allow_html=True,
        )

        scope_ids = [t["id"] for t in cat_items]
        grid_data, selected_id = render_aggrid(
            cat_items,
            include_owner=True,
            grid_key=f"grid_at_{category[:6]}",
        )

        if grid_data is not None and sync_grid(grid_data, scope_ids):
            st.rerun()

        action_cols = st.columns([2.5, 2.5, 7])
        with action_cols[0]:
            if selected_id:
                t = get_todo(selected_id)
                if t:
                    lbl = "↩ Reopen" if t["status"] == "Done" else "✓ Mark Done"
                    if st.button(lbl, key=f"at_toggle_{category[:4]}"):
                        new_s = "Open" if t["status"] == "Done" else "Done"
                        t["status"] = new_s
                        t["waiting_on_them"] = False
                        t["updated"] = str(date.today())
                        flush()
                        st.rerun()
        with action_cols[1]:
            if selected_id:
                if st.button("✕ Delete", key=f"at_del_{category[:4]}"):
                    delete_todo(selected_id)
                    st.rerun()

        st.markdown('<div class="sg-grid-hint">Double-click any cell to edit inline</div>',
                    unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

# ── Tab: By Company ───────────────────────────────────────────────────────────

def render_by_company(todos: list[dict]) -> None:
    companies = sorted({t["company"] for t in todos})
    co_open   = {c: sum(1 for t in todos if t["company"] == c and t["status"] != "Done")
                 for c in companies}
    top       = max(co_open, key=co_open.get) if co_open else "—"

    st.markdown(f"""
<div class="sg-stats">
  <div class="sg-stat">
    <div class="sg-stat-value">{len(companies)}</div>
    <div class="sg-stat-label">Companies</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#1d4a8a">{open_count(todos)}</div>
    <div class="sg-stat-label">Open Items</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#b87820">
      {sum(1 for t in todos if t.get('waiting_on_them'))}</div>
    <div class="sg-stat-label">Waiting on Them</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#692730;font-size:1rem">{top}</div>
    <div class="sg-stat-label">Most Pending</div>
  </div>
</div>
""", unsafe_allow_html=True)

    for company in companies:
        ctodos    = [t for t in todos if t["company"] == company]
        c_open    = sum(1 for t in ctodos if t["status"] == "Open")
        c_inp     = sum(1 for t in ctodos if t["status"] == "In Progress")
        c_waiting = sum(1 for t in ctodos if t.get("waiting_on_them"))
        c_done    = sum(1 for t in ctodos if t["status"] == "Done")
        owners    = ", ".join(sorted({t["owner"] for t in ctodos}))

        with st.expander(f"{company}  ·  {len(ctodos)} items  ({c_open} open)", expanded=False):
            st.markdown(f"""
<div class="sg-company-stats" style="margin-bottom:0.7rem">
  <div class="sg-company-stat">Open: <b>{c_open}</b></div>
  <div class="sg-company-stat">In Progress: <b>{c_inp}</b></div>
  <div class="sg-company-stat">Waiting: <b>{c_waiting}</b></div>
  <div class="sg-company-stat">Done: <b>{c_done}</b></div>
  <div class="sg-company-stat">Owners: <b>{owners}</b></div>
</div>
""", unsafe_allow_html=True)
            for t in ctodos:
                is_w   = t.get("waiting_on_them", False)
                p      = PEOPLE.get(t["owner"], {"color": "#fff", "bg": "#888"})
                wb_lbl = (' &nbsp;<span style="font-size:0.6rem;font-weight:700;'
                          'color:#8a3a0a;background:#fef0e0;border:1px solid #d8a868;'
                          'border-radius:4px;padding:1px 5px;font-family:\'JetBrains Mono\',monospace">'
                          '⏳ Waiting</span>') if is_w else ""
                done_s = ("text-decoration:line-through;color:#b0a898"
                          if t["status"] == "Done" else "")
                st.markdown(f"""
<div style="background:#faf8f4;border:1px solid {'#d8a868' if is_w else '#e8e2d8'};
    border-left:{'4px solid #b87820' if is_w else '1px solid #e8e2d8'};
    border-radius:7px;padding:0.65rem 0.9rem;margin-bottom:0.4rem">
  <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:3px">
    <span class="sg-badge" style="background:{p['bg']};color:{p['color']};
      width:22px;height:22px;font-size:0.57rem">{t['owner']}</span>
    <span style="font-size:0.81rem;color:#2a2018;{done_s}">{t['description']}</span>
  </div>
  <div style="margin-top:3px">{status_html(t['status'])} {wb_lbl}</div>
  <div style="font-size:0.64rem;color:#c0b8b0;font-family:'JetBrains Mono',monospace;margin-top:4px">
    Updated {t.get('updated','—')}</div>
</div>
""", unsafe_allow_html=True)

# ── Tab: Weekly Summary ───────────────────────────────────────────────────────

def render_weekly_summary(todos: list[dict]) -> None:
    today = date.today().strftime("%B %d, %Y")
    lines = ["INTERNAL PROCESS MEETING — WEEKLY SUMMARY", f"Generated: {today}", ""]

    lines += ["═" * 55, "BY PERSON", "═" * 55]
    for owner in PEOPLE:
        pt = [t for t in todos if t["owner"] == owner]
        lines.append(f"\n{owner}  ({open_count(pt)} open / {len(pt)} total)")
        lines.append("─" * 40)
        for t in pt:
            if t["status"] == "Done":
                lines.append(f"  [DONE] {t['company']} — {t['description']}")
            else:
                wt = " [BALL IN THEIR COURT]" if t.get("waiting_on_them") else ""
                lines.append(f"  [{t['status'][:4].upper()}] {t['company']} — {t['description']}{wt}")
                if t.get("notes"):
                    lines.append(f"         ↳ {t['notes']}")

    lines += ["\n\n" + "═" * 55, "BY COMPANY", "═" * 55]
    for company in sorted({t["company"] for t in todos}):
        ct = [t for t in todos if t["company"] == company]
        lines.append(f"\n{company}")
        for t in ct:
            wt = " [BALL IN THEIR COURT]" if t.get("waiting_on_them") else ""
            lines.append(f"  {t['owner']}  [{t['status'][:4].upper()}]  {t['description']}{wt}")

    lines += ["\n\n" + "═" * 55, "BY CATEGORY", "═" * 55]
    for cat in CATEGORIES:
        ct = [t for t in todos if t.get("category", CATEGORIES[0]) == cat and t["status"] != "Done"]
        if not ct:
            continue
        lines.append(f"\n{cat}  ({len(ct)} open)")
        lines.append("─" * 40)
        for t in ct:
            wt = " [BALL IN THEIR COURT]" if t.get("waiting_on_them") else ""
            lines.append(f"  {t['owner']}  {t['company']} — {t['description']}{wt}")

    summary_text = "\n".join(lines)
    st.markdown(
        '<div class="sg-summary-block">' + summary_text.replace("\n", "<br>") + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, _ = st.columns([2, 2, 7])
    with c1:
        st.download_button("⬇ Download (.txt)", data=summary_text,
                           file_name=f"weekly_summary_{date.today()}.txt",
                           mime="text/plain", key="dl_txt")
    with c2:
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["id","owner","company","description","status",
                        "category","waiting_on_them","notes","created","updated"],
            extrasaction="ignore",
        )
        writer.writeheader(); writer.writerows(todos)
        st.download_button("⬇ Export CSV", data=buf.getvalue(),
                           file_name=f"todos_{date.today()}.csv",
                           mime="text/csv", key="dl_csv")

# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    init_state()
    inject_css()
    render_header()
    render_stats(st.session_state.todos)

    ca, cb, _ = st.columns([2, 2, 9])
    with ca:
        if st.button("＋ New To-Do", key="top_new"):
            st.session_state.show_new_form = not st.session_state.show_new_form
            st.rerun()
    with cb:
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["id","owner","company","description","status",
                        "category","waiting_on_them","notes","created","updated"],
            extrasaction="ignore",
        )
        writer.writeheader(); writer.writerows(st.session_state.todos)
        st.download_button("⬇ Export CSV", data=buf.getvalue(),
                           file_name=f"todos_{date.today()}.csv",
                           mime="text/csv", key="top_csv")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["By Person", "All To-Dos", "By Company", "Weekly Summary"]
    )
    with tab1: render_by_person(st.session_state.todos)
    with tab2: render_all_todos(st.session_state.todos)
    with tab3: render_by_company(st.session_state.todos)
    with tab4: render_weekly_summary(st.session_state.todos)


if __name__ == "__main__":
    main()
