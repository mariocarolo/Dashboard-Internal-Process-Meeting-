import streamlit as st
import json
import csv
import io
import uuid
import base64
from datetime import date
from pathlib import Path

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
    if "inline_edit_id" not in st.session_state:
        st.session_state.inline_edit_id = None
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

def set_status(todo_id: str, status: str) -> None:
    t = get_todo(todo_id)
    if t:
        t["status"] = status
        t["waiting_on_them"] = status == "Waiting on Them"
        t["updated"] = str(date.today())
        flush()

def open_count(todos: list[dict]) -> int:
    return sum(1 for t in todos if t["status"] != "Done")

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

/* ── Base ── */
html, body, [class*="css"], .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="block-container"] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #f7f5f0 !important;
    color: #1a1512 !important;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 2.5rem 4rem 2.5rem !important; max-width: 1600px; }
section[data-testid="stSidebar"] { display: none; }

/* ── Logo fallback text ── */
.sg-logo-text {
    font-family: 'Cinzel', serif;
    font-size: 1.5rem; font-weight: 600;
    color: #692730; letter-spacing: 0.05em;
}

/* ── Header ── */
.sg-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.8rem 0 1.4rem 0;
    border-bottom: 1.5px solid #ddd8d0;
    margin-bottom: 1.6rem;
}
.sg-header-left h1 {
    font-size: 1.2rem; font-weight: 600; letter-spacing: 0.01em;
    color: #1a1512; margin: 0 0 3px 0;
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
    border-radius: 12px; padding: 1.2rem 1.4rem; margin-bottom: 1.2rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.sg-person-header {
    display: flex; align-items: center; gap: 0.75rem;
    margin-bottom: 1rem; padding-bottom: 0.85rem;
    border-bottom: 1px solid #f0ece5;
}
.sg-badge {
    width: 34px; height: 34px; border-radius: 7px;
    display: inline-flex; align-items: center; justify-content: center;
    font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
    font-weight: 700; letter-spacing: 0.03em; flex-shrink: 0;
}
.sg-person-name { font-size: 0.85rem; font-weight: 600; color: #1a1512; }
.sg-person-count { font-size: 0.67rem; color: #a09080;
    font-family: 'JetBrains Mono', monospace; margin-top: 1px; }

/* ── Todo item — base ── */
.sg-todo-item {
    background: #faf8f4; border: 1px solid #e8e2d8;
    border-radius: 8px; padding: 0.78rem 1rem; margin-bottom: 0.48rem;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.sg-todo-item:hover { border-color: #c8c0b4; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.sg-todo-item.done { opacity: 0.5; }

/* ── Waiting on Them card — prominent ── */
.sg-todo-waiting {
    background: #fffbf4 !important;
    border: 1px solid #d8a868 !important;
    border-left: 4px solid #b87820 !important;
    box-shadow: 0 1px 10px rgba(184,120,32,0.12) !important;
}

/* ── Inline edit card ── */
.sg-inline-edit {
    background: #ffffff; border: 1.5px solid #692730;
    border-radius: 8px; padding: 0.9rem 1rem; margin-bottom: 0.48rem;
    box-shadow: 0 2px 10px rgba(105,39,48,0.08);
}
.sg-inline-edit-label {
    font-size: 0.62rem; font-weight: 700; color: #692730;
    text-transform: uppercase; letter-spacing: 0.1em;
    margin-bottom: 0.5rem; font-family: 'JetBrains Mono', monospace;
}

.sg-todo-company {
    font-family: 'JetBrains Mono', monospace; font-size: 0.65rem;
    font-weight: 500; color: #a09080; text-transform: uppercase;
    letter-spacing: 0.09em; margin-bottom: 3px;
}
.sg-todo-desc { font-size: 0.82rem; color: #2a2018; line-height: 1.45; }
.sg-todo-desc.done-text { text-decoration: line-through; color: #b0a898; }
.sg-todo-meta { font-size: 0.64rem; color: #c0b8b0;
    font-family: 'JetBrains Mono', monospace; margin-top: 5px; }
.sg-todo-notes { font-size: 0.7rem; color: #8a7e78; font-style: italic;
    margin-top: 5px; padding-top: 5px; border-top: 1px solid #ede8e0; }

/* ── Status badge ── */
.sg-status {
    display: inline-block; font-size: 0.59rem; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase;
    padding: 2px 7px; border-radius: 4px; margin-top: 4px;
    font-family: 'JetBrains Mono', monospace; border: 1px solid transparent;
}

/* ── Waiting badge ── */
.sg-waiting-badge {
    display: inline-flex; align-items: center; gap: 3px;
    font-size: 0.59rem; font-weight: 700; letter-spacing: 0.07em;
    text-transform: uppercase; padding: 2px 7px; border-radius: 4px;
    margin-left: 5px; background: #fef0e0; color: #8a3a0a;
    border: 1px solid #d8a868; font-family: 'JetBrains Mono', monospace;
}

/* ── Category section header ── */
.sg-category-header {
    font-size: 0.67rem; font-weight: 700; color: #692730;
    text-transform: uppercase; letter-spacing: 0.12em;
    padding: 0.4rem 0; border-bottom: 1.5px solid #ddd8d0;
    margin: 1.2rem 0 0.7rem 0; font-family: 'JetBrains Mono', monospace;
}

/* ── Table column header ── */
.sg-col-header {
    font-size: 0.61rem; color: #a09080; text-transform: uppercase;
    letter-spacing: 0.09em; font-family: 'JetBrains Mono', monospace;
    padding-bottom: 4px; border-bottom: 1px solid #e8e2d8;
}

/* ── Tabs ── */
div[data-testid="stTabs"] [role="tab"] {
    font-size: 0.73rem !important; font-weight: 600 !important;
    letter-spacing: 0.07em !important; text-transform: uppercase !important;
    color: #a09080 !important; padding: 0.5rem 1.2rem !important;
}
div[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #692730 !important;
    border-bottom: 2px solid #692730 !important;
}
div[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid #ddd8d0 !important;
    background: transparent !important; gap: 0.2rem !important;
}

/* ── Buttons ── */
.stButton > button {
    background: #ffffff !important; border: 1px solid #ddd8d0 !important;
    color: #7a6e66 !important; font-size: 0.7rem !important;
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

/* ── Multiselect ── */
.stMultiSelect > div { border-color: #ddd8d0 !important; background: #faf8f4 !important; }
.stMultiSelect [data-baseweb="tag"] { background: #f8eeec !important; color: #692730 !important; }

/* ── Expander ── */
details > summary {
    background: #ffffff !important; border: 1px solid #ddd8d0 !important;
    border-radius: 8px !important; font-size: 0.8rem !important;
    color: #4a3e38 !important; font-weight: 500 !important;
}

/* ── Weekly summary ── */
.sg-summary-block {
    background: #ffffff; border: 1px solid #ddd8d0; border-radius: 10px;
    padding: 1.4rem 1.6rem; font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem; color: #4a3e38; line-height: 1.8;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}

hr { border-color: #e8e2d8 !important; }
.sg-company-stats { display: flex; gap: 1.2rem; flex-wrap: wrap; margin-top: 0.4rem; }
.sg-company-stat { font-size: 0.67rem; color: #a09080; font-family: 'JetBrains Mono', monospace; }
.sg-company-stat b { color: #4a3e38; }
</style>
""", unsafe_allow_html=True)

# ── HTML helpers ──────────────────────────────────────────────────────────────

def status_html(status: str) -> str:
    m = STATUS_META.get(status, STATUS_META["Open"])
    return (f'<span class="sg-status" style="background:{m["bg"]};'
            f'color:{m["color"]};border-color:{m["border"]}">{status}</span>')

def waiting_html() -> str:
    return '<span class="sg-waiting-badge">⏳ Ball in Their Court</span>'

def badge_html(owner: str, size: int = 34) -> str:
    p = PEOPLE.get(owner, {"color": "#fff", "bg": "#888"})
    return (f'<span class="sg-badge" style="background:{p["bg"]};color:{p["color"]};'
            f'width:{size}px;height:{size}px">{owner}</span>')

# ── Inline edit form ──────────────────────────────────────────────────────────

def render_inline_edit(t: dict, kp: str = "") -> None:
    st.markdown('<div class="sg-inline-edit"><div class="sg-inline-edit-label">Editing</div>',
                unsafe_allow_html=True)
    ca, cb = st.columns([2, 3])
    with ca:
        company = st.text_input("Company",  value=t["company"],  key=f"{kp}co_{t['id']}")
        owner   = st.selectbox("Owner", list(PEOPLE.keys()),
                               index=list(PEOPLE.keys()).index(t["owner"]), key=f"{kp}own_{t['id']}")
        category = st.selectbox("Category", CATEGORIES,
                                index=CATEGORIES.index(t.get("category", CATEGORIES[0])),
                                key=f"{kp}cat_{t['id']}")
    with cb:
        description = st.text_area("Description", value=t["description"],
                                   height=72, key=f"{kp}desc_{t['id']}")
        notes = st.text_area("Notes", value=t.get("notes", ""),
                             height=72, key=f"{kp}notes_{t['id']}")
    cc, cd = st.columns([2, 3])
    with cc:
        status  = st.selectbox("Status", list(STATUS_META.keys()),
                               index=list(STATUS_META.keys()).index(t["status"]),
                               key=f"{kp}st_{t['id']}")
    with cd:
        waiting = st.checkbox("Ball in Their Court", value=t.get("waiting_on_them", False),
                              key=f"{kp}w_{t['id']}")
    bs, bc, _ = st.columns([1.3, 1.3, 6])
    with bs:
        if st.button("Save", key=f"{kp}save_{t['id']}", type="primary"):
            if description.strip() and company.strip():
                t.update({
                    "company":         company.strip().upper(),
                    "owner":           owner,
                    "description":     description.strip(),
                    "status":          status,
                    "category":        category,
                    "waiting_on_them": waiting or status == "Waiting on Them",
                    "notes":           notes.strip(),
                    "updated":         str(date.today()),
                })
                upsert_todo(t)
                st.session_state.inline_edit_id = None
                st.rerun()
    with bc:
        if st.button("Cancel", key=f"{kp}cancel_{t['id']}"):
            st.session_state.inline_edit_id = None
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

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

# ── Header ────────────────────────────────────────────────────────────────────

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

# ── Stats strip ───────────────────────────────────────────────────────────────

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
                    '<div class="sg-inline-edit-label">New To-Do</div>',
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
""", unsafe_allow_html=True)

            for t in visible:
                tid = t["id"]

                # ── Inline edit mode ──
                if st.session_state.inline_edit_id == tid:
                    render_inline_edit(t, kp=f"bp_{owner}_")
                    continue

                # ── Normal display ──
                is_waiting = t.get("waiting_on_them", False)
                wait_cls   = "sg-todo-waiting" if is_waiting else ""
                done_cls   = "done" if t["status"] == "Done" else ""
                desc_cls   = "done-text" if t["status"] == "Done" else ""
                wb         = waiting_html() if is_waiting else ""
                notes_html = (f'<div class="sg-todo-notes">{t["notes"]}</div>'
                              if t.get("notes") else "")
                st.markdown(f"""
<div class="sg-todo-item {wait_cls} {done_cls}">
  <div class="sg-todo-company">{t['company']}</div>
  <div class="sg-todo-desc {desc_cls}">{t['description']}</div>
  <div style="margin-top:4px">{status_html(t['status'])} {wb}</div>
  {notes_html}
  <div class="sg-todo-meta">Updated {t.get('updated','—')}</div>
</div>
""", unsafe_allow_html=True)

                a1, a2, a3, a4, a5 = st.columns([2, 2, 1.8, 1.3, 1.3])
                with a1:
                    if t["status"] != "Done":
                        if st.button("✓ Done",   key=f"bp_done_{tid}"):
                            set_status(tid, "Done"); st.rerun()
                    else:
                        if st.button("↩ Reopen", key=f"bp_reopen_{tid}"):
                            set_status(tid, "Open"); st.rerun()
                with a2:
                    if not is_waiting:
                        if st.button("⏳ Wait",  key=f"bp_wait_{tid}"):
                            set_status(tid, "Waiting on Them"); st.rerun()
                with a3:
                    if st.button("✎ Edit",       key=f"bp_edit_{tid}"):
                        st.session_state.inline_edit_id = tid
                        st.rerun()
                with a4:
                    if st.button("✕",            key=f"bp_del_{tid}", help="Delete"):
                        delete_todo(tid); st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

            # Per-person quick-add
            if st.session_state.inline_add_owner == owner:
                st.markdown('<div style="background:#fff;border:1px solid #ddd8d0;'
                            'border-radius:8px;padding:0.9rem 1rem;margin-top:0.4rem">'
                            '<div class="sg-inline-edit-label">Add for ' + owner + '</div>',
                            unsafe_allow_html=True)
                render_new_form(default_owner=owner, kp=f"per_{owner}_")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                if st.button(f"＋ Add for {owner}", key=f"add_{owner}"):
                    st.session_state.inline_add_owner = owner
                    st.rerun()

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
                     if t.get("category", "Operational") == category]
        if not cat_items:
            continue

        st.markdown(
            f'<div class="sg-category-header">{category}'
            f'&nbsp;·&nbsp;{len(cat_items)} items</div>',
            unsafe_allow_html=True,
        )

        # Column headers
        h0, h1, h2, h3, h4, h5, h6 = st.columns([1, 1.2, 3.8, 2, 2.5, 1, 2])
        for lbl, col in zip(
            ["Own", "Company", "Description", "Status", "Notes", "Upd.", "Actions"],
            [h0, h1, h2, h3, h4, h5, h6],
        ):
            col.markdown(f'<div class="sg-col-header">{lbl}</div>', unsafe_allow_html=True)

        for t in cat_items:
            tid = t["id"]

            if st.session_state.inline_edit_id == tid:
                render_inline_edit(t, kp=f"at_{category[:3]}_")
                continue

            is_waiting = t.get("waiting_on_them", False)
            c0, c1, c2, c3, c4, c5, c6 = st.columns([1, 1.2, 3.8, 2, 2.5, 1, 2])
            p = PEOPLE.get(t["owner"], {"color": "#fff", "bg": "#888"})
            with c0:
                st.markdown(
                    f'<span class="sg-badge" style="background:{p["bg"]};color:{p["color"]};'
                    f'width:26px;height:26px;font-size:0.62rem">{t["owner"]}</span>',
                    unsafe_allow_html=True,
                )
            with c1:
                st.markdown(
                    f'<div class="sg-todo-company" style="padding-top:3px">{t["company"]}</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                sty = "text-decoration:line-through;color:#b0a898" if t["status"] == "Done" else ""
                wb  = " &nbsp;⏳" if is_waiting else ""
                st.markdown(
                    f'<div style="font-size:0.80rem;color:#2a2018;{sty}">'
                    f'{t["description"]}{wb}</div>',
                    unsafe_allow_html=True,
                )
            with c3:
                m = STATUS_META.get(t["status"], STATUS_META["Open"])
                st.markdown(
                    f'<span class="sg-status" style="background:{m["bg"]};color:{m["color"]};'
                    f'border-color:{m["border"]}">{t["status"]}</span>',
                    unsafe_allow_html=True,
                )
            with c4:
                st.markdown(
                    f'<div style="font-size:0.70rem;color:#8a7e78;font-style:italic">'
                    f'{t.get("notes","")}</div>',
                    unsafe_allow_html=True,
                )
            with c5:
                st.markdown(
                    f'<div class="sg-todo-meta">{t.get("updated","")}</div>',
                    unsafe_allow_html=True,
                )
            with c6:
                b1, b2, b3 = st.columns(3)
                with b1:
                    if st.button("✎", key=f"at_e_{tid}", help="Edit"):
                        st.session_state.inline_edit_id = tid; st.rerun()
                with b2:
                    lbl2 = "↩" if t["status"] == "Done" else "✓"
                    if st.button(lbl2, key=f"at_d_{tid}",
                                 help="Reopen" if t["status"] == "Done" else "Mark Done"):
                        set_status(tid, "Open" if t["status"] == "Done" else "Done"); st.rerun()
                with b3:
                    if st.button("✕", key=f"at_x_{tid}", help="Delete"):
                        delete_todo(tid); st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

# ── Tab: By Company ───────────────────────────────────────────────────────────

def render_by_company(todos: list[dict]) -> None:
    companies   = sorted({t["company"] for t in todos})
    co_open     = {c: sum(1 for t in todos if t["company"] == c and t["status"] != "Done")
                   for c in companies}
    top         = max(co_open, key=co_open.get) if co_open else "—"

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
<div class="sg-company-stats" style="margin-bottom:0.8rem">
  <div class="sg-company-stat">Open: <b>{c_open}</b></div>
  <div class="sg-company-stat">In Progress: <b>{c_inp}</b></div>
  <div class="sg-company-stat">Waiting: <b>{c_waiting}</b></div>
  <div class="sg-company-stat">Done: <b>{c_done}</b></div>
  <div class="sg-company-stat">Owners: <b>{owners}</b></div>
</div>
""", unsafe_allow_html=True)
            for t in ctodos:
                is_waiting = t.get("waiting_on_them", False)
                wait_cls   = "sg-todo-waiting" if is_waiting else ""
                done_cls   = "done" if t["status"] == "Done" else ""
                desc_cls   = "done-text" if t["status"] == "Done" else ""
                wb         = waiting_html() if is_waiting else ""
                p          = PEOPLE.get(t["owner"], {"color": "#fff", "bg": "#888"})
                st.markdown(f"""
<div class="sg-todo-item {wait_cls} {done_cls}">
  <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:3px">
    <span class="sg-badge" style="background:{p['bg']};color:{p['color']};
      width:22px;height:22px;font-size:0.57rem">{t['owner']}</span>
    <span class="sg-todo-desc {desc_cls}">{t['description']}</span>
  </div>
  <div style="margin-top:3px">{status_html(t['status'])} {wb}</div>
  <div class="sg-todo-meta">Updated {t.get('updated','—')}</div>
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
        ct = [t for t in todos if t.get("category", "Operational") == cat and t["status"] != "Done"]
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

    # Action bar
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
