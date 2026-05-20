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
try:
    from st_aggrid.shared import JsCode
except ImportError:
    try:
        from st_aggrid import JsCode
    except ImportError:
        JsCode = None

st.set_page_config(
    page_title="Internal Process Meeting",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_FILE = Path(__file__).parent / "todos.json"
LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"

PEOPLE = {
    "AM": {"color": "#ffffff", "bg": "#692730"},
    "DV": {"color": "#ffffff", "bg": "#4a1f28"},
    "MC": {"color": "#ffffff", "bg": "#3a1820"},
    "PA": {"color": "#ffffff", "bg": "#2a1218"},
}

STATUS_META = {
    "Open":            {"color": "#1d4a8a", "bg": "#edf2fc", "border": "#c5d5f0"},
    "In Progress":     {"color": "#7a5a08", "bg": "#fef8e3", "border": "#e8cc70"},
    "Waiting on Them": {"color": "#8a3a0a", "bg": "#fef0e3", "border": "#f0b880"},
    "Done":            {"color": "#1a5a38", "bg": "#edf7f0", "border": "#a0d8b8"},
}

CATEGORIES = ["Operacional", "Investidas (Resultados)", "Pipeline", "Consignado"]

# ── AG Grid custom CSS ─────────────────────────────────────────────────────────
GRID_CSS = {
    ".ag-root-wrapper": {
        "border": "1px solid #ddd8d0 !important",
        "border-radius": "0 0 8px 8px !important",
        "overflow": "hidden !important",
    },
    ".ag-header": {
        "background-color": "#f0ece5 !important",
        "border-bottom": "2px solid #ddd8d0 !important",
    },
    ".ag-header-cell-text": {
        "color": "#692730 !important",
        "font-size": "0.66rem !important",
        "text-transform": "uppercase !important",
        "letter-spacing": "0.09em !important",
        "font-weight": "700 !important",
        "font-family": "'JetBrains Mono', monospace !important",
    },
    ".ag-row": {"background-color": "#ffffff !important", "border-bottom": "1px solid #f0ece5 !important"},
    ".ag-row-odd": {"background-color": "#faf8f5 !important"},
    ".ag-row-hover": {"background-color": "#f8f0ee !important"},
    ".ag-row-selected": {"background-color": "#f3e8e8 !important"},
    # Waiting rows: dashed amber outline + warm tint
    ".ag-row.sg-row-waiting": {
        "background-color": "#fffaf4 !important",
        "outline": "1.5px dashed #c8823a !important",
        "outline-offset": "-2px !important",
    },
    ".ag-row.sg-row-waiting .ag-cell": {"color": "#4a2808 !important"},
    ".ag-cell": {
        "font-size": "0.82rem !important",
        "color": "#2a2018 !important",
        "border-right": "1px solid #f0ece5 !important",
        "padding-top": "8px !important",
        "padding-bottom": "8px !important",
        "line-height": "1.45 !important",
    },
    ".ag-cell-focus": {"border": "2px solid #692730 !important", "outline": "none !important"},
    ".ag-cell-inline-editing": {
        "border": "2px solid #692730 !important",
        "box-shadow": "0 2px 14px rgba(105,39,48,0.18) !important",
        "background": "#ffffff !important",
    },
    ".ag-input-field-input": {"font-size": "0.82rem !important", "color": "#1a1512 !important"},
    ".ag-popup-editor": {
        "border": "1.5px solid #692730 !important",
        "border-radius": "6px !important",
        "box-shadow": "0 4px 16px rgba(105,39,48,0.15) !important",
    },
    ".ag-checkbox-input-wrapper input": {
        "width": "15px !important",
        "height": "15px !important",
        "accent-color": "#692730 !important",
        "cursor": "pointer !important",
    },
}

# Row class rule: adds CSS class to waiting rows (requires JsCode + allow_unsafe_jscode)
_ROW_CLASS_RULES = {}
if JsCode is not None:
    _ROW_CLASS_RULES = {
        "sg-row-waiting": JsCode("function(params) { return params.data && params.data.waiting === true; }")
    }

# Delete-column cell renderer: renders a ✕ icon; clicking sets the cell value to true
_DELETE_RENDERER = None
if JsCode is not None:
    _DELETE_RENDERER = JsCode("""
function(params) {
    if (!params.data) return '';
    var span = document.createElement('span');
    span.innerHTML = '✕';
    span.title = 'Excluir';
    span.style.cssText = 'display:block;text-align:center;cursor:pointer;color:#d4b8b8;'
        + 'font-size:13px;line-height:52px;user-select:none;transition:color 0.1s;';
    span.addEventListener('mouseenter', function() {
        span.style.color = '#a03030'; span.style.fontWeight = '700';
    });
    span.addEventListener('mouseleave', function() {
        span.style.color = '#d4b8b8'; span.style.fontWeight = '400';
    });
    span.addEventListener('click', function(e) {
        e.stopPropagation();
        params.setValue(true);
    });
    return span;
}
""")

# ── Persistence ────────────────────────────────────────────────────────────────

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
    if "add_owner" not in st.session_state:
        st.session_state.add_owner = None
    if "show_done" not in st.session_state:
        st.session_state.show_done = True
    if "show_add_form" not in st.session_state:
        st.session_state.show_add_form = False
    if "at_last_sel" not in st.session_state:
        st.session_state["at_last_sel"] = None

def flush() -> None:
    save_data(st.session_state.todos)

def get_todo(tid: str) -> dict | None:
    return next((t for t in st.session_state.todos if t["id"] == tid), None)

def upsert_todo(data: dict) -> None:
    idx = next((i for i, t in enumerate(st.session_state.todos) if t["id"] == data["id"]), None)
    if idx is None:
        st.session_state.todos.append(data)
    else:
        st.session_state.todos[idx] = data
    flush()

def delete_todo(tid: str) -> None:
    st.session_state.todos = [t for t in st.session_state.todos if t["id"] != tid]
    flush()

def open_count(todos: list[dict]) -> int:
    return sum(1 for t in todos if t["status"] != "Done")

def sort_by_company(todos: list[dict]) -> list[dict]:
    return sorted(todos, key=lambda t: t.get("company", "").lower())

# ── AG Grid core ───────────────────────────────────────────────────────────────

def todos_to_df(todos: list[dict], with_owner: bool = False, with_delete: bool = False) -> pd.DataFrame:
    rows = [{
        "_del":        False,
        "id":          t.get("id", ""),
        "owner":       t.get("owner", ""),
        "company":     t.get("company", ""),
        "notes":       t.get("notes", ""),
        "description": t.get("description", ""),
        "waiting":     bool(t.get("waiting_on_them", False)),
        "status":      t.get("status", "Open"),
        "category":    t.get("category", CATEGORIES[0]),
        "updated":     t.get("updated", ""),
    } for t in todos]
    # Column order = display order in AgGrid.
    # _del pinned-left delete icon; owner first when shown; waiting always before status.
    if with_delete and with_owner:
        cols = ["_del", "owner", "company", "notes", "description", "waiting", "status", "updated", "id", "category"]
    elif with_owner:
        cols = ["owner", "company", "notes", "description", "waiting", "status", "updated", "id", "category", "_del"]
    else:
        cols = ["company", "notes", "description", "waiting", "status", "updated", "id", "category", "owner", "_del"]
    df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
    df["waiting"] = df["waiting"].astype(bool)
    df["_del"]    = df["_del"].astype(bool)
    return df

def make_grid(todos: list[dict], with_owner: bool = False, with_delete: bool = False, key: str = "g") -> tuple:
    """Render AG Grid. Returns (response_df | None, selected_id | None)."""
    if not todos:
        st.markdown('<p style="font-size:0.8rem;color:#a09080;padding:0.4rem 0">Sem itens.</p>',
                    unsafe_allow_html=True)
        return None, None

    df = todos_to_df(sort_by_company(todos), with_owner=with_owner, with_delete=with_delete)
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        editable=False, resizable=True, sortable=False,
        filter=False, suppressMenu=True, suppressMovable=True,
        cellStyle={"fontFamily": "'DM Sans', sans-serif"},
    )

    # Delete column: pinned left, ✕ icon renderer (only in tab_all_todos)
    if with_delete and _DELETE_RENDERER:
        gb.configure_column(
            "_del", headerName="", width=42, editable=True,
            pinned="left",
            cellRenderer=_DELETE_RENDERER,
            cellStyle={"padding": "0", "borderRight": "1px solid #e8e2d8"},
            suppressSizeToFit=True,
        )
    else:
        gb.configure_column("_del", hide=True)

    # Hidden columns
    gb.configure_column("id",       hide=True)
    gb.configure_column("category", hide=True)
    if not with_owner:
        gb.configure_column("owner", hide=True)

    if with_owner:
        gb.configure_column(
            "owner", headerName="Resp.", width=80, editable=True,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": list(PEOPLE.keys())},
            cellStyle={"fontFamily": "'JetBrains Mono',monospace",
                       "fontWeight": "700", "fontSize": "0.78rem", "color": "#692730"},
        )

    gb.configure_column(
        "company", headerName="Companhia", width=115, editable=True,
        cellStyle={"fontFamily": "'JetBrains Mono',monospace",
                   "fontSize": "0.74rem", "fontWeight": "600", "color": "#4a3e38"},
    )
    gb.configure_column(
        "notes", headerName="Anotações", flex=2, editable=True,
        wrapText=True, autoHeight=True,
        cellStyle={"color": "#5a5048", "fontSize": "0.80rem", "lineHeight": "1.4"},
    )
    gb.configure_column(
        "description", headerName="To Do", flex=2, editable=True,
        wrapText=True, autoHeight=True,
        cellStyle={"fontWeight": "500", "color": "#1a1512", "fontSize": "0.82rem"},
    )
    # ⏳ Waiting — single-click checkbox, appears before Status
    gb.configure_column(
        "waiting", headerName="⏳", width=60, editable=True,
        cellRenderer="agCheckboxCellRenderer",
        cellEditor="agCheckboxCellEditor",
        cellStyle={"display": "flex", "alignItems": "center", "justifyContent": "center"},
    )
    gb.configure_column(
        "status", headerName="Status", width=148, editable=True,
        cellEditor="agSelectCellEditor",
        cellEditorParams={"values": list(STATUS_META.keys())},
        cellStyle={"fontSize": "0.74rem"},
    )
    gb.configure_column(
        "updated", headerName="Atualizado", width=95, editable=False,
        cellStyle={"color": "#b0a898", "fontSize": "0.64rem",
                   "fontFamily": "'JetBrains Mono',monospace"},
    )

    gb.configure_selection(selection_mode="single", use_checkbox=False)

    grid_opts = dict(
        domLayout="autoHeight",
        headerHeight=36,
        rowHeight=52,
        stopEditingWhenCellsLoseFocus=True,
        enableCellTextSelection=True,
        suppressRowClickSelection=False,
    )
    if _ROW_CLASS_RULES:
        grid_opts["rowClassRules"] = _ROW_CLASS_RULES

    gb.configure_grid_options(**grid_opts)

    use_jscode = JsCode is not None and (bool(_ROW_CLASS_RULES) or (with_delete and _DELETE_RENDERER is not None))
    resp = AgGrid(
        df,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.VALUE_CHANGED,
        theme="alpine",
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=use_jscode,
        custom_css=GRID_CSS,
        key=key,
    )

    sel_id = None
    sel = resp.get("selected_rows")
    if sel is not None:
        if isinstance(sel, pd.DataFrame) and not sel.empty:
            sel_id = str(sel.iloc[0].get("id", ""))
        elif isinstance(sel, list) and len(sel) > 0 and isinstance(sel[0], dict):
            sel_id = str(sel[0].get("id", ""))

    return resp.get("data"), sel_id

def sync_grid(grid_df, scope_ids: list[str], with_delete: bool = False) -> bool:
    """Apply edits from the grid back to session_state. Returns True if anything changed."""
    if grid_df is None:
        return False
    try:
        rows = grid_df.to_dict("records")
    except Exception:
        return False

    # Process in-grid deletions (✕ icon clicked)
    changed = False
    if with_delete and "_del" in grid_df.columns:
        to_delete = {
            str(row.get("id", "")).strip()
            for row in rows
            if bool(row.get("_del", False)) and str(row.get("id", "")).strip() in scope_ids
        }
        if to_delete:
            st.session_state.todos = [t for t in st.session_state.todos if t["id"] not in to_delete]
            # Clear stale selection if deleted
            if st.session_state.get("at_last_sel") in to_delete:
                st.session_state["at_last_sel"] = None
            flush()
            changed = True

    for row in rows:
        tid = str(row.get("id", "")).strip()
        if tid not in scope_ids:
            continue
        t = get_todo(tid)
        if t is None:
            continue

        for grid_col, todo_field in [
            ("company",     "company"),
            ("notes",       "notes"),
            ("description", "description"),
            ("status",      "status"),
        ]:
            nv = str(row.get(grid_col) or "").strip()
            ov = str(t.get(todo_field) or "").strip()
            if nv and nv != ov:
                t[todo_field] = nv
                t["updated"] = str(date.today())
                changed = True

        if "owner" in grid_df.columns:
            nv = str(row.get("owner") or "").strip()
            if nv in PEOPLE and nv != str(t.get("owner", "")).strip():
                t["owner"] = nv
                t["updated"] = str(date.today())
                changed = True

        # Boolean waiting (checkbox)
        raw_w = row.get("waiting", False)
        if isinstance(raw_w, str):
            nv_w = raw_w.lower() in ("true", "sim", "1")
        else:
            nv_w = bool(raw_w)
        ov_w = bool(t.get("waiting_on_them", False))
        if nv_w != ov_w:
            t["waiting_on_them"] = nv_w
            t["updated"] = str(date.today())
            changed = True

        if t.get("status") == "Waiting on Them" and not t.get("waiting_on_them"):
            t["waiting_on_them"] = True
            changed = True

    if changed:
        flush()
    return changed

# ── Logo ───────────────────────────────────────────────────────────────────────

def logo_html() -> str:
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" style="height:36px">'
    return '<span style="font-family:\'Cinzel\',serif;font-size:1.45rem;font-weight:600;color:#692730;letter-spacing:0.05em">SIGULER GUFF</span>'

# ── CSS ────────────────────────────────────────────────────────────────────────

def inject_css() -> None:
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500;600&family=Cinzel:wght@400;600&display=swap');

html, body, [class*="css"], .stApp,
[data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #f5f3ee !important;
    color: #1a1512 !important;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 2rem 4rem 2rem !important; max-width: 1500px; }
section[data-testid="stSidebar"] { display: none; }

/* ── Header ── */
.sg-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.6rem 0 1.2rem 0;
    border-bottom: 2px solid #ddd8d0; margin-bottom: 1.4rem;
}
.sg-header h1 { font-size: 1.2rem; font-weight: 600; color: #1a1512; margin: 0 0 3px 0; }
.sg-header p  { font-size: 0.7rem; color: #a09080; font-family:'JetBrains Mono',monospace;
    letter-spacing: 0.08em; text-transform: uppercase; margin: 0; }

/* ── Stat strip ── */
.sg-stats { display: flex; gap: 0.9rem; margin-bottom: 1.3rem; flex-wrap: wrap; }
.sg-stat {
    flex: 1; min-width: 110px; background: #ffffff;
    border: 1px solid #ddd8d0; border-radius: 9px; padding: 0.85rem 1.1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.sg-stat-value { font-size: 1.75rem; font-weight: 700; font-family:'JetBrains Mono',monospace; line-height: 1; }
.sg-stat-label { font-size: 0.61rem; font-weight: 500; color: #a09080;
    text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px; }

/* ── Section headers (person & company share same style) ── */
.sg-section-header {
    display: flex; align-items: center; gap: 0.8rem;
    padding: 0.65rem 1.1rem;
    border-radius: 8px 8px 0 0;
    margin-top: 1.2rem; margin-bottom: 0;
}
.sg-section-title {
    font-family: 'JetBrains Mono', monospace; font-size: 0.92rem;
    font-weight: 700; color: #ffffff; letter-spacing: 0.05em;
}
.sg-section-meta { font-size: 0.7rem; color: rgba(255,255,255,0.75);
    font-family:'JetBrains Mono',monospace; letter-spacing: 0.06em; }

/* ── Hint ── */
.sg-hint { font-size: 0.62rem; color: #c0b8b0; font-family:'JetBrains Mono',monospace;
    margin-top: 3px; letter-spacing: 0.04em; }

/* ── Category header ── */
.sg-cat-header {
    font-size: 0.66rem; font-weight: 700; color: #692730;
    text-transform: uppercase; letter-spacing: 0.12em;
    padding: 0.35rem 0; border-bottom: 1.5px solid #ddd8d0;
    margin: 1.1rem 0 0.4rem 0; font-family:'JetBrains Mono',monospace;
}

/* ── Tabs ── */
div[data-testid="stTabs"] [role="tab"] {
    font-size: 0.72rem !important; font-weight: 600 !important;
    letter-spacing: 0.07em !important; text-transform: uppercase !important;
    color: #a09080 !important; padding: 0.45rem 1.1rem !important;
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
    box-shadow: none !important; transition: all 0.13s !important;
}
.stButton > button:hover {
    border-color: #692730 !important; color: #692730 !important; background: #f8f0ee !important;
}
.stButton > button[kind="primary"] {
    background: #692730 !important; border-color: #692730 !important;
    color: #ffffff !important; font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover { background: #7d3038 !important; }

/* ── Inputs ── */
.stTextInput > div > div > input, .stTextArea > div > div > textarea {
    background: #faf8f4 !important; color: #1a1512 !important;
    border-color: #ddd8d0 !important; border-radius: 6px !important; font-size: 0.82rem !important;
}
.stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus {
    border-color: #692730 !important; box-shadow: 0 0 0 2px rgba(105,39,48,0.10) !important;
}
.stSelectbox > div > div {
    background: #faf8f4 !important; color: #1a1512 !important;
    border-color: #ddd8d0 !important; border-radius: 6px !important;
}
label { font-size: 0.67rem !important; color: #a09080 !important;
    text-transform: uppercase !important; letter-spacing: 0.08em !important; }
.stCheckbox label { font-size: 0.78rem !important; color: #5a4e48 !important;
    text-transform: none !important; letter-spacing: 0 !important; }
.stMultiSelect > div { border-color: #ddd8d0 !important; background: #faf8f4 !important; }
.stMultiSelect [data-baseweb="tag"] { background: #f8eeec !important; color: #692730 !important; }

/* ── Add form card ── */
.sg-add-card {
    background: #ffffff; border: 1.5px solid #692730;
    border-radius: 9px; padding: 1rem 1.2rem; margin: 0.6rem 0 1rem 0;
}
.sg-add-title { font-size: 0.65rem; font-weight: 700; color: #692730;
    text-transform: uppercase; letter-spacing: 0.1em;
    margin-bottom: 0.6rem; font-family:'JetBrains Mono',monospace; }

/* ── Summary ── */
.sg-summary {
    background: #ffffff; border: 1px solid #ddd8d0; border-radius: 10px;
    padding: 1.4rem 1.6rem; font-family:'JetBrains Mono',monospace;
    font-size: 0.75rem; color: #4a3e38; line-height: 1.8;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
hr { border-color: #e8e2d8 !important; }
</style>
""", unsafe_allow_html=True)

# ── Shared widgets ─────────────────────────────────────────────────────────────

def render_header() -> None:
    st.markdown(f"""
<div class="sg-header">
  <div>
    <h1>Internal Process Meeting</h1>
    <p>Weekly Review &nbsp;·&nbsp; Monday, May 19, 2026</p>
  </div>
  <div>{logo_html()}</div>
</div>""", unsafe_allow_html=True)

def render_stats(todos: list[dict]) -> None:
    t, o = len(todos), sum(1 for x in todos if x["status"] == "Open")
    ip   = sum(1 for x in todos if x["status"] == "In Progress")
    w    = sum(1 for x in todos if x.get("waiting_on_them"))
    d    = sum(1 for x in todos if x["status"] == "Done")
    st.markdown(f"""
<div class="sg-stats">
  <div class="sg-stat"><div class="sg-stat-value">{t}</div><div class="sg-stat-label">Total</div></div>
  <div class="sg-stat"><div class="sg-stat-value" style="color:#1d4a8a">{o}</div><div class="sg-stat-label">Open</div></div>
  <div class="sg-stat"><div class="sg-stat-value" style="color:#7a5a08">{ip}</div><div class="sg-stat-label">In Progress</div></div>
  <div class="sg-stat"><div class="sg-stat-value" style="color:#b87820">{w}</div><div class="sg-stat-label">Aguardando</div></div>
  <div class="sg-stat"><div class="sg-stat-value" style="color:#1a5a38">{d}</div><div class="sg-stat-label">Done</div></div>
</div>""", unsafe_allow_html=True)

def section_header(title: str, meta: str, bg: str = "#692730") -> None:
    st.markdown(f"""
<div class="sg-section-header" style="background:{bg}">
  <div class="sg-section-title">{title}</div>
  <div class="sg-section-meta">{meta}</div>
</div>""", unsafe_allow_html=True)

def render_add_form(default_owner: str = "AM", kp: str = "") -> None:
    st.markdown('<div class="sg-add-card"><div class="sg-add-title">Novo To-Do</div>',
                unsafe_allow_html=True)
    c1, c2 = st.columns([2, 3])
    with c1:
        company  = st.text_input("Companhia",  key=f"{kp}co")
        owner    = st.selectbox("Responsável", list(PEOPLE.keys()),
                                index=list(PEOPLE.keys()).index(default_owner), key=f"{kp}own")
        category = st.selectbox("Categoria",   CATEGORIES, key=f"{kp}cat")
        status   = st.selectbox("Status",      list(STATUS_META.keys()), key=f"{kp}st")
    with c2:
        notes       = st.text_area("Anotações", height=72, key=f"{kp}notes")
        description = st.text_area("To Do",     height=72, key=f"{kp}desc")
    waiting = st.checkbox("⏳ Aguardando resposta de terceiros", key=f"{kp}w")

    bs, bc, _ = st.columns([1.4, 1.4, 6])
    with bs:
        if st.button("Adicionar", key=f"{kp}save", type="primary"):
            if description.strip() and company.strip():
                upsert_todo({
                    "id":              str(uuid.uuid4()),
                    "owner":           owner,
                    "company":         company.strip().upper(),
                    "notes":           notes.strip(),
                    "description":     description.strip(),
                    "status":          status,
                    "category":        category,
                    "waiting_on_them": waiting or status == "Waiting on Them",
                    "created":         str(date.today()),
                    "updated":         str(date.today()),
                })
                st.session_state.add_owner    = None
                st.session_state.show_add_form = False
                st.rerun()
            else:
                st.warning("Companhia e To Do são obrigatórios.")
    with bc:
        if st.button("Cancelar", key=f"{kp}cancel"):
            st.session_state.add_owner    = None
            st.session_state.show_add_form = False
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

def grid_action_row(selected_id: str | None, owner_key: str) -> None:
    c1, c2, _ = st.columns([2.2, 2.2, 8])
    with c1:
        if selected_id:
            t = get_todo(selected_id)
            if t:
                lbl = "↩ Reabrir" if t["status"] == "Done" else "✓ Concluído"
                if st.button(lbl, key=f"done_{owner_key}_{selected_id[:6]}"):
                    t["status"] = "Open" if t["status"] == "Done" else "Done"
                    t["waiting_on_them"] = False
                    t["updated"] = str(date.today())
                    flush(); st.rerun()
    with c2:
        if selected_id:
            if st.button("✕ Excluir", key=f"del_{owner_key}_{selected_id[:6]}"):
                delete_todo(selected_id); st.rerun()

# ── Tab: By Person ─────────────────────────────────────────────────────────────

def tab_by_person(todos: list[dict]) -> None:
    show_done = st.session_state.show_done

    ca, cb, _ = st.columns([2.2, 2.2, 8])
    with ca:
        if st.button("Ocultar Done" if show_done else "Mostrar Done", key="tog_done"):
            st.session_state.show_done = not show_done; st.rerun()
    with cb:
        if st.button("＋ Novo To-Do", key="bp_new"):
            st.session_state.show_add_form = not st.session_state.show_add_form; st.rerun()

    if st.session_state.show_add_form:
        render_add_form(kp="top_")

    for owner, meta in PEOPLE.items():
        person_todos = sort_by_company([t for t in todos if t["owner"] == owner])
        visible      = [t for t in person_todos if t["status"] != "Done" or show_done]
        open_c       = open_count(person_todos)

        section_header(owner, f"{open_c} open · {len(person_todos)} total", bg=meta["bg"])

        scope_ids = [t["id"] for t in visible]
        gdata, sel_id = make_grid(visible, with_owner=False, key=f"g_bp_{owner}")

        if gdata is not None and sync_grid(gdata, scope_ids):
            st.rerun()

        grid_action_row(sel_id, f"bp_{owner}")
        st.markdown('<div class="sg-hint">Clique para selecionar &nbsp;·&nbsp; '
                    'Duplo clique na célula para editar &nbsp;·&nbsp; Checkbox ⏳ com um clique</div>',
                    unsafe_allow_html=True)

        if st.session_state.add_owner == owner:
            render_add_form(default_owner=owner, kp=f"pa_{owner}_")
        else:
            if st.button(f"＋ Add para {owner}", key=f"add_{owner}"):
                st.session_state.add_owner = owner; st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

# ── Tab: All To-Dos ────────────────────────────────────────────────────────────

def tab_all_todos(todos: list[dict]) -> None:
    # ── Filters ──
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 2, 2, 3])
    with fc1: f_owner   = st.multiselect("Responsável", list(PEOPLE.keys()), key="f_own")
    with fc2:
        companies = sorted({t["company"] for t in todos})
        f_company = st.multiselect("Companhia", companies, key="f_co")
    with fc3: f_status  = st.multiselect("Status", list(STATUS_META.keys()), key="f_st")
    with fc4: f_waiting = st.checkbox("Só aguardando", key="f_w")
    with fc5: f_search  = st.text_input("Busca", placeholder="palavra-chave…", key="f_q")

    fil = todos
    if f_owner:   fil = [t for t in fil if t["owner"]   in f_owner]
    if f_company: fil = [t for t in fil if t["company"] in f_company]
    if f_status:  fil = [t for t in fil if t["status"]  in f_status]
    if f_waiting: fil = [t for t in fil if t.get("waiting_on_them")]
    if f_search:
        kw = f_search.lower()
        fil = [t for t in fil if kw in t.get("description","").lower()
               or kw in t.get("company","").lower()
               or kw in t.get("notes","").lower()]

    if not fil:
        st.info("Nenhum item encontrado."); return

    # ── Action bar (add-above + delete selected) ──
    at_sel = st.session_state.get("at_last_sel")
    at_ref  = get_todo(at_sel) if at_sel else None
    sel_label = f"  ·  {at_ref['company']} — {at_ref['description'][:40]}…" if at_ref else ""

    ba1, ba2, _ = st.columns([3.2, 2.8, 7])
    with ba1:
        if st.button(f"＋ Nova linha acima{sel_label}", key="at_add_above",
                     disabled=not at_ref, type="primary" if at_ref else "secondary"):
            new_todo = {
                "id":              str(uuid.uuid4()),
                "owner":           at_ref["owner"],
                "company":         at_ref["company"],
                "notes":           "",
                "description":     "",
                "status":          "Open",
                "category":        at_ref.get("category", CATEGORIES[0]),
                "waiting_on_them": False,
                "created":         str(date.today()),
                "updated":         str(date.today()),
            }
            # Insert immediately before the reference row (stable sort keeps it above)
            idx = next((i for i, t in enumerate(st.session_state.todos) if t["id"] == at_sel),
                       len(st.session_state.todos))
            st.session_state.todos.insert(idx, new_todo)
            flush()
            st.session_state["at_last_sel"] = None
            st.rerun()
    with ba2:
        if at_ref and st.button("✕ Excluir selecionada", key="at_del_sel"):
            delete_todo(at_sel)
            st.session_state["at_last_sel"] = None
            st.rerun()

    # ── Grids by category ──
    for cat in CATEGORIES:
        cat_items = sort_by_company([t for t in fil if t.get("category", CATEGORIES[0]) == cat])
        if not cat_items: continue

        st.markdown(f'<div class="sg-cat-header">{cat} &nbsp;·&nbsp; {len(cat_items)} itens</div>',
                    unsafe_allow_html=True)

        scope_ids = [t["id"] for t in cat_items]
        gdata, sel_id = make_grid(cat_items, with_owner=True, with_delete=True, key=f"g_at_{cat[:5]}")

        # Persist the last row selected (any category) for the action bar
        if sel_id:
            st.session_state["at_last_sel"] = sel_id

        if gdata is not None and sync_grid(gdata, scope_ids, with_delete=True):
            st.rerun()

        st.markdown('<div class="sg-hint">✕ na primeira coluna para excluir &nbsp;·&nbsp; '
                    'Clique para selecionar &nbsp;·&nbsp; Duplo clique para editar</div>',
                    unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

# ── Tab: By Company ────────────────────────────────────────────────────────────

def tab_by_company(todos: list[dict]) -> None:
    companies = sorted({t["company"] for t in todos})
    co_open   = {c: sum(1 for t in todos if t["company"] == c and t["status"] != "Done")
                 for c in companies}
    top = max(co_open, key=co_open.get) if co_open else "—"

    st.markdown(f"""
<div class="sg-stats">
  <div class="sg-stat"><div class="sg-stat-value">{len(companies)}</div><div class="sg-stat-label">Companhias</div></div>
  <div class="sg-stat"><div class="sg-stat-value" style="color:#1d4a8a">{open_count(todos)}</div><div class="sg-stat-label">Open</div></div>
  <div class="sg-stat"><div class="sg-stat-value" style="color:#b87820">{sum(1 for t in todos if t.get("waiting_on_them"))}</div><div class="sg-stat-label">Aguardando</div></div>
  <div class="sg-stat"><div class="sg-stat-value" style="color:#692730;font-size:0.95rem">{top}</div><div class="sg-stat-label">Mais Pendências</div></div>
</div>""", unsafe_allow_html=True)

    show_done = st.session_state.show_done
    # Cycle brand shades so adjacent companies look distinct
    shades = ["#692730", "#4a1f28", "#3a1820", "#5a2030", "#692730", "#4a1f28"]

    for i, company in enumerate(companies):
        ct      = [t for t in todos if t["company"] == company]
        visible = [t for t in ct if t["status"] != "Done" or show_done]
        c_open  = open_count(ct)
        owners  = " · ".join(sorted({t["owner"] for t in ct}))

        section_header(
            company,
            f"{c_open} open · {len(ct)} total · {owners}",
            bg=shades[i % len(shades)],
        )

        scope_ids = [t["id"] for t in visible]
        gdata, sel_id = make_grid(visible, with_owner=True, key=f"g_co_{company[:10]}")
        if gdata is not None and sync_grid(gdata, scope_ids):
            st.rerun()

        grid_action_row(sel_id, f"co_{company[:8]}")
        st.markdown('<div class="sg-hint">Duplo clique para editar</div>',
                    unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

# ── Tab: Weekly Summary ────────────────────────────────────────────────────────

def tab_summary(todos: list[dict]) -> None:
    today = date.today().strftime("%d/%m/%Y")
    lines = ["INTERNAL PROCESS MEETING — WEEKLY SUMMARY", f"Gerado em: {today}", ""]

    lines += ["═"*55, "POR PESSOA", "═"*55]
    for owner in PEOPLE:
        pt = sort_by_company([t for t in todos if t["owner"] == owner])
        lines += [f"\n{owner}  ({open_count(pt)} open / {len(pt)} total)", "─"*40]
        for t in pt:
            wt  = " [AGUARDANDO]" if t.get("waiting_on_them") else ""
            pfx = "[DONE]" if t["status"] == "Done" else f"[{t['status'][:4].upper()}]"
            lines.append(f"  {pfx} {t['company']} — {t['description']}{wt}")
            if t.get("notes") and t["status"] != "Done":
                lines.append(f"        ↳ {t['notes']}")

    lines += ["\n\n"+"═"*55, "POR COMPANHIA", "═"*55]
    for co in sorted({t["company"] for t in todos}):
        ct = [t for t in todos if t["company"] == co]
        lines.append(f"\n{co}")
        for t in ct:
            wt = " [AGUARDANDO]" if t.get("waiting_on_them") else ""
            lines.append(f"  {t['owner']}  [{t['status'][:4].upper()}]  {t['description']}{wt}")

    lines += ["\n\n"+"═"*55, "POR CATEGORIA", "═"*55]
    for cat in CATEGORIES:
        ct = sort_by_company([t for t in todos
                               if t.get("category", CATEGORIES[0]) == cat and t["status"] != "Done"])
        if not ct: continue
        lines += [f"\n{cat}  ({len(ct)} open)", "─"*40]
        for t in ct:
            wt = " [AGUARDANDO]" if t.get("waiting_on_them") else ""
            lines.append(f"  {t['owner']}  {t['company']} — {t['description']}{wt}")

    summary = "\n".join(lines)
    st.markdown('<div class="sg-summary">' + summary.replace("\n","<br>") + "</div>",
                unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, _ = st.columns([2, 2, 7])
    with c1:
        st.download_button("⬇ Baixar (.txt)", data=summary,
                           file_name=f"weekly_{date.today()}.txt",
                           mime="text/plain", key="dl_txt")
    with c2:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["id","owner","company","notes","description",
                                             "status","category","waiting_on_them","created","updated"],
                           extrasaction="ignore")
        w.writeheader(); w.writerows(todos)
        st.download_button("⬇ Exportar CSV", data=buf.getvalue(),
                           file_name=f"todos_{date.today()}.csv",
                           mime="text/csv", key="dl_csv")

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    init_state()
    inject_css()
    render_header()
    render_stats(st.session_state.todos)

    ca, cb, _ = st.columns([2.2, 2.2, 8])
    with ca:
        if st.button("＋ Novo To-Do", key="top_new"):
            st.session_state.show_add_form = not st.session_state.show_add_form; st.rerun()
    with cb:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["id","owner","company","notes","description",
                                             "status","category","waiting_on_them","created","updated"],
                           extrasaction="ignore")
        w.writeheader(); w.writerows(st.session_state.todos)
        st.download_button("⬇ Exportar CSV", data=buf.getvalue(),
                           file_name=f"todos_{date.today()}.csv",
                           mime="text/csv", key="top_csv")

    t1, t2, t3, t4 = st.tabs(["Por Pessoa", "Todos os To-Dos", "Por Companhia", "Resumo Semanal"])
    with t1: tab_by_person(st.session_state.todos)
    with t2: tab_all_todos(st.session_state.todos)
    with t3: tab_by_company(st.session_state.todos)
    with t4: tab_summary(st.session_state.todos)


if __name__ == "__main__":
    main()
