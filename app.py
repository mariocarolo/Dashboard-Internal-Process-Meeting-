import streamlit as st
import json
import csv
import io
import uuid
from datetime import date, datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Internal Process Meeting — Siguler Guff",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_FILE = Path("todos.json")

PEOPLE = {
    "AM": {"name": "AM", "color": "#4f8ef7", "bg": "rgba(79,142,247,0.15)"},
    "DV": {"name": "DV", "color": "#7c5cbf", "bg": "rgba(124,92,191,0.15)"},
    "MC": {"name": "MC", "color": "#2ab5a0", "bg": "rgba(42,181,160,0.15)"},
    "PA": {"name": "PA", "color": "#d4875a", "bg": "rgba(212,135,90,0.15)"},
}

STATUS_META = {
    "Open":            {"color": "#4f8ef7", "bg": "rgba(79,142,247,0.18)"},
    "In Progress":     {"color": "#e8c44a", "bg": "rgba(232,196,74,0.18)"},
    "Waiting on Them": {"color": "#d4875a", "bg": "rgba(212,135,90,0.18)"},
    "Done":            {"color": "#2ab5a0", "bg": "rgba(42,181,160,0.18)"},
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
    if "show_modal" not in st.session_state:
        st.session_state.show_modal = False
    if "edit_id" not in st.session_state:
        st.session_state.edit_id = None
    if "show_done" not in st.session_state:
        st.session_state.show_done = True

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

# ── CSS ───────────────────────────────────────────────────────────────────────

def inject_css() -> None:
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #0a0a0c;
    color: #e2e2e6;
}

/* Hide streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 2rem 3rem 2rem; max-width: 1600px; }
section[data-testid="stSidebar"] { display: none; }

/* ── Header ── */
.sg-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.6rem 0 1.2rem 0;
    border-bottom: 1px solid #1e1e24;
    margin-bottom: 1.6rem;
}
.sg-header-left h1 {
    font-size: 1.35rem; font-weight: 600; letter-spacing: 0.02em;
    color: #f0f0f4; margin: 0 0 2px 0;
}
.sg-header-left p {
    font-size: 0.75rem; font-weight: 400; color: #6b6b7a;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.06em; text-transform: uppercase; margin: 0;
}
.sg-logo {
    font-family: 'DM Sans', sans-serif; font-size: 0.78rem;
    font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
    color: #4f8ef7; opacity: 0.85; text-align: right; line-height: 1.5;
}
.sg-logo span { display: block; font-weight: 300; color: #6b6b7a;
    font-size: 0.65rem; letter-spacing: 0.12em; }

/* ── Stat cards ── */
.sg-stats { display: flex; gap: 1rem; margin-bottom: 1.6rem; flex-wrap: wrap; }
.sg-stat {
    flex: 1; min-width: 130px;
    background: #111116; border: 1px solid #1e1e24;
    border-radius: 10px; padding: 1rem 1.2rem;
}
.sg-stat-value {
    font-size: 1.8rem; font-weight: 700; color: #f0f0f4;
    font-family: 'JetBrains Mono', monospace; line-height: 1;
}
.sg-stat-label {
    font-size: 0.65rem; font-weight: 500; color: #6b6b7a;
    text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px;
}

/* ── Person card ── */
.sg-person-card {
    background: #111116; border: 1px solid #1e1e24;
    border-radius: 12px; padding: 1.2rem 1.4rem; margin-bottom: 1.2rem;
}
.sg-person-header {
    display: flex; align-items: center; gap: 0.7rem;
    margin-bottom: 1rem;
    padding-bottom: 0.8rem; border-bottom: 1px solid #1a1a20;
}
.sg-badge {
    width: 36px; height: 36px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;
    font-weight: 700; letter-spacing: 0.04em; flex-shrink: 0;
}
.sg-person-name { font-size: 0.85rem; font-weight: 600; color: #e2e2e6; }
.sg-person-count {
    font-size: 0.7rem; color: #6b6b7a;
    font-family: 'JetBrains Mono', monospace; margin-top: 1px;
}

/* ── Todo item ── */
.sg-todo-item {
    background: #0d0d12; border: 1px solid #1a1a20;
    border-radius: 8px; padding: 0.75rem 1rem;
    margin-bottom: 0.55rem; transition: border-color 0.15s;
}
.sg-todo-item:hover { border-color: #2a2a35; }
.sg-todo-item.done { opacity: 0.48; }
.sg-todo-company {
    font-family: 'JetBrains Mono', monospace; font-size: 0.68rem;
    font-weight: 500; color: #6b6b7a; text-transform: uppercase;
    letter-spacing: 0.08em; margin-bottom: 3px;
}
.sg-todo-desc {
    font-size: 0.83rem; font-weight: 400; color: #d0d0da; line-height: 1.45;
}
.sg-todo-desc.done-text { text-decoration: line-through; color: #555560; }
.sg-todo-meta {
    font-size: 0.67rem; color: #555560;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 5px;
}
.sg-todo-notes {
    font-size: 0.72rem; color: #7a7a8a; font-style: italic;
    margin-top: 4px; padding-top: 4px; border-top: 1px solid #1a1a20;
}

/* ── Status badge ── */
.sg-status {
    display: inline-block; font-size: 0.62rem; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase;
    padding: 2px 7px; border-radius: 4px; margin-top: 5px;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Waiting badge ── */
.sg-waiting {
    display: inline-block; font-size: 0.6rem; font-weight: 600;
    letter-spacing: 0.07em; text-transform: uppercase;
    padding: 2px 6px; border-radius: 4px;
    background: rgba(212,135,90,0.15); color: #d4875a;
    font-family: 'JetBrains Mono', monospace; margin-left: 5px;
}

/* ── Company summary ── */
.sg-company-row {
    background: #111116; border: 1px solid #1e1e24;
    border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 0.7rem;
}
.sg-company-name {
    font-family: 'JetBrains Mono', monospace; font-size: 0.9rem;
    font-weight: 600; color: #e2e2e6; letter-spacing: 0.04em;
}
.sg-company-stats { display: flex; gap: 1rem; margin-top: 0.4rem; flex-wrap: wrap; }
.sg-company-stat { font-size: 0.7rem; color: #6b6b7a; font-family: 'JetBrains Mono', monospace; }
.sg-company-stat b { color: #c0c0ca; }

/* ── Tabs ── */
div[data-testid="stTabs"] [role="tab"] {
    font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: #6b6b7a; padding: 0.5rem 1rem;
}
div[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: #4f8ef7; }
div[data-testid="stTabs"] [role="tablist"] { border-bottom: 1px solid #1e1e24; gap: 0.5rem; }

/* ── Buttons ── */
.stButton > button {
    background: #111116 !important; border: 1px solid #1e1e24 !important;
    color: #9090a0 !important; font-size: 0.72rem !important;
    font-family: 'DM Sans', sans-serif !important;
    border-radius: 6px !important; padding: 4px 10px !important;
    transition: all 0.15s !important;
}
.stButton > button:hover {
    border-color: #4f8ef7 !important; color: #4f8ef7 !important;
}

/* ── Form / modal ── */
.sg-modal-title {
    font-size: 0.9rem; font-weight: 700; color: #f0f0f4;
    letter-spacing: 0.04em; text-transform: uppercase;
    padding-bottom: 0.6rem; border-bottom: 1px solid #1e1e24;
    margin-bottom: 0.8rem;
}

/* ── Selectbox / input dark ── */
.stSelectbox > div > div, .stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: #0d0d12 !important; color: #d0d0da !important;
    border-color: #1e1e24 !important;
}
label { font-size: 0.72rem !important; color: #6b6b7a !important;
    text-transform: uppercase !important; letter-spacing: 0.07em !important; }

/* ── Data editor ── */
.stDataFrame, .stDataEditor { border: 1px solid #1e1e24 !important; border-radius: 10px !important; }

/* ── Weekly summary ── */
.sg-summary-block {
    background: #111116; border: 1px solid #1e1e24; border-radius: 10px;
    padding: 1.2rem 1.4rem; font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem; color: #c0c0ca; white-space: pre-wrap;
    line-height: 1.7;
}

/* ── Divider ── */
hr { border-color: #1a1a20 !important; }

/* ── Expander ── */
details summary { font-size: 0.75rem !important; color: #6b6b7a !important; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def status_badge(status: str) -> str:
    m = STATUS_META.get(status, STATUS_META["Open"])
    return (f'<span class="sg-status" style="background:{m["bg"]};color:{m["color"]}">'
            f'{status}</span>')

def waiting_badge() -> str:
    return '<span class="sg-waiting">⏳ Ball in Their Court</span>'

def person_badge(owner: str, size: int = 36) -> str:
    p = PEOPLE.get(owner, {"color": "#888", "bg": "rgba(128,128,128,0.15)", "name": owner})
    return (f'<span class="sg-badge" style="background:{p["bg"]};color:{p["color"]};'
            f'width:{size}px;height:{size}px">{owner}</span>')

def count_by(todos: list[dict], key: str, val: str) -> int:
    return sum(1 for t in todos if t.get(key) == val)

def open_count(todos: list[dict]) -> int:
    return sum(1 for t in todos if t["status"] != "Done")

# ── Header ───────────────────────────────────────────────────────────────────

def render_header() -> None:
    next_monday = "Monday, May 19, 2026"
    st.markdown(f"""
<div class="sg-header">
  <div class="sg-header-left">
    <h1>Internal Process Meeting</h1>
    <p>Weekly Review &nbsp;·&nbsp; {next_monday}</p>
  </div>
  <div class="sg-logo">
    SIGULER GUFF
    <span>Specialized Private Markets Investors</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Global stats ─────────────────────────────────────────────────────────────

def render_stats(todos: list[dict]) -> None:
    total   = len(todos)
    open_   = count_by(todos, "status", "Open")
    inp     = count_by(todos, "status", "In Progress")
    waiting = sum(1 for t in todos if t.get("waiting_on_them"))
    done    = count_by(todos, "status", "Done")

    st.markdown(f"""
<div class="sg-stats">
  <div class="sg-stat">
    <div class="sg-stat-value">{total}</div>
    <div class="sg-stat-label">Total Items</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#4f8ef7">{open_}</div>
    <div class="sg-stat-label">Open</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#e8c44a">{inp}</div>
    <div class="sg-stat-label">In Progress</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#d4875a">{waiting}</div>
    <div class="sg-stat-label">Ball in Their Court</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#2ab5a0">{done}</div>
    <div class="sg-stat-label">Done</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Add/Edit Modal ────────────────────────────────────────────────────────────

def render_modal() -> None:
    editing = st.session_state.edit_id is not None
    existing = get_todo(st.session_state.edit_id) if editing else None

    with st.container():
        st.markdown('<div class="sg-modal-title">' +
                    ('Edit To-Do' if editing else 'New To-Do') + '</div>',
                    unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            owner = st.selectbox("Owner", list(PEOPLE.keys()),
                                 index=list(PEOPLE.keys()).index(existing["owner"])
                                 if existing else 0, key="m_owner")
            company = st.text_input("Company", value=existing["company"] if existing else "",
                                    key="m_company")
            status = st.selectbox("Status", list(STATUS_META.keys()),
                                  index=list(STATUS_META.keys()).index(existing["status"])
                                  if existing else 0, key="m_status")
        with c2:
            description = st.text_area("Description",
                                       value=existing["description"] if existing else "",
                                       height=90, key="m_desc")
            notes = st.text_area("Notes / Comments",
                                 value=existing["notes"] if existing else "",
                                 height=90, key="m_notes")

        waiting = st.checkbox("Ball in Their Court (Waiting on Them)",
                              value=existing.get("waiting_on_them", False) if existing else False,
                              key="m_waiting")

        col_save, col_cancel = st.columns([1, 4])
        with col_save:
            if st.button("Save", key="m_save", type="primary"):
                if description.strip() and company.strip():
                    todo = {
                        "id": existing["id"] if existing else str(uuid.uuid4()),
                        "owner": owner,
                        "company": company.strip().upper(),
                        "description": description.strip(),
                        "status": status,
                        "waiting_on_them": waiting or status == "Waiting on Them",
                        "notes": notes.strip(),
                        "created": existing["created"] if existing else str(date.today()),
                        "updated": str(date.today()),
                    }
                    upsert_todo(todo)
                    st.session_state.show_modal = False
                    st.session_state.edit_id = None
                    st.rerun()
                else:
                    st.warning("Description and Company are required.")
        with col_cancel:
            if st.button("Cancel", key="m_cancel"):
                st.session_state.show_modal = False
                st.session_state.edit_id = None
                st.rerun()
        st.markdown("---")

# ── Tab: By Person ────────────────────────────────────────────────────────────

def render_by_person(todos: list[dict]) -> None:
    show_done = st.session_state.show_done
    toggle_label = "Hide Done" if show_done else "Show Done"
    if st.button(toggle_label, key="toggle_done_person"):
        st.session_state.show_done = not show_done
        st.rerun()

    cols = st.columns(2)
    for col_idx, (owner, meta) in enumerate(PEOPLE.items()):
        person_todos = [t for t in todos if t["owner"] == owner]
        visible = [t for t in person_todos if t["status"] != "Done" or show_done]
        open_c = open_count(person_todos)

        with cols[col_idx % 2]:
            st.markdown(f"""
<div class="sg-person-card">
  <div class="sg-person-header">
    {person_badge(owner)}
    <div>
      <div class="sg-person-name">{owner}</div>
      <div class="sg-person-count">{open_c} open · {len(person_todos)} total</div>
    </div>
  </div>
""", unsafe_allow_html=True)

            for t in visible:
                done_cls = "done" if t["status"] == "Done" else ""
                desc_cls = "done-text" if t["status"] == "Done" else ""
                wb = waiting_badge() if t.get("waiting_on_them") else ""
                notes_html = (f'<div class="sg-todo-notes">{t["notes"]}</div>'
                              if t.get("notes") else "")

                st.markdown(f"""
<div class="sg-todo-item {done_cls}">
  <div class="sg-todo-company">{t['company']}</div>
  <div class="sg-todo-desc {desc_cls}">{t['description']}</div>
  {status_badge(t['status'])} {wb}
  {notes_html}
  <div class="sg-todo-meta">Updated {t.get('updated','—')}</div>
</div>
""", unsafe_allow_html=True)

                # Action row
                a1, a2, a3, a4, a5 = st.columns([2, 2, 2, 2, 3])
                with a1:
                    if t["status"] != "Done":
                        if st.button("✓ Done", key=f"done_{t['id']}"):
                            set_status(t["id"], "Done")
                            st.rerun()
                with a2:
                    if t["status"] == "Done":
                        if st.button("↩ Reopen", key=f"reopen_{t['id']}"):
                            set_status(t["id"], "Open")
                            st.rerun()
                with a3:
                    if not t.get("waiting_on_them"):
                        if st.button("⏳ Wait", key=f"wait_{t['id']}"):
                            set_status(t["id"], "Waiting on Them")
                            st.rerun()
                with a4:
                    if st.button("✎ Edit", key=f"edit_{t['id']}"):
                        st.session_state.edit_id = t["id"]
                        st.session_state.show_modal = True
                        st.rerun()
                with a5:
                    if st.button("✕ Delete", key=f"del_{t['id']}"):
                        delete_todo(t["id"])
                        st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

            if st.button(f"+ Add To-Do for {owner}", key=f"add_{owner}"):
                st.session_state.show_modal = True
                st.session_state.edit_id = None
                st.session_state["m_owner_default"] = owner
                st.rerun()

# ── Tab: All To-Dos ───────────────────────────────────────────────────────────

def render_all_todos(todos: list[dict]) -> None:
    # Filters
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 2, 2, 3])
    with fc1:
        f_owner = st.multiselect("Owner", list(PEOPLE.keys()), key="f_owner")
    with fc2:
        companies = sorted({t["company"] for t in todos})
        f_company = st.multiselect("Company", companies, key="f_company")
    with fc3:
        f_status = st.multiselect("Status", list(STATUS_META.keys()), key="f_status")
    with fc4:
        f_waiting = st.checkbox("Waiting on Them only", key="f_waiting")
    with fc5:
        f_search = st.text_input("Search", placeholder="keyword…", key="f_search")

    filtered = todos
    if f_owner:    filtered = [t for t in filtered if t["owner"] in f_owner]
    if f_company:  filtered = [t for t in filtered if t["company"] in f_company]
    if f_status:   filtered = [t for t in filtered if t["status"] in f_status]
    if f_waiting:  filtered = [t for t in filtered if t.get("waiting_on_them")]
    if f_search:
        kw = f_search.lower()
        filtered = [t for t in filtered
                    if kw in t["description"].lower()
                    or kw in t["company"].lower()
                    or kw in t.get("notes", "").lower()]

    # Render each as a row
    if not filtered:
        st.info("No items match the current filters.")
        return

    # Header row
    h1, h2, h3, h4, h5, h6, h7 = st.columns([1, 1, 4, 2, 2, 1, 2])
    for lbl, col in zip(["Owner", "Company", "Description", "Status", "Notes", "Updated", "Actions"],
                        [h1, h2, h3, h4, h5, h6, h7]):
        col.markdown(f"<div style='font-size:0.65rem;color:#6b6b7a;text-transform:uppercase;"
                     f"letter-spacing:0.08em;font-family:JetBrains Mono,monospace;'>{lbl}</div>",
                     unsafe_allow_html=True)

    st.markdown("<hr style='margin:4px 0 8px 0'>", unsafe_allow_html=True)

    for t in filtered:
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 1, 4, 2, 2, 1, 2])
        with c1:
            p = PEOPLE.get(t["owner"], {"color": "#888", "bg": "#222"})
            st.markdown(f'<span class="sg-badge" style="background:{p["bg"]};color:{p["color"]};'
                        f'width:28px;height:28px;font-size:0.65rem">{t["owner"]}</span>',
                        unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="sg-todo-company" style="padding-top:5px">{t["company"]}</div>',
                        unsafe_allow_html=True)
        with c3:
            desc_style = "text-decoration:line-through;color:#555560" if t["status"] == "Done" else ""
            wb = " · ⏳" if t.get("waiting_on_them") else ""
            st.markdown(f'<div style="font-size:0.82rem;color:#d0d0da;{desc_style}">'
                        f'{t["description"]}{wb}</div>', unsafe_allow_html=True)
        with c4:
            m = STATUS_META.get(t["status"], STATUS_META["Open"])
            st.markdown(f'<span class="sg-status" style="background:{m["bg"]};color:{m["color"]}">'
                        f'{t["status"]}</span>', unsafe_allow_html=True)
        with c5:
            st.markdown(f'<div style="font-size:0.72rem;color:#7a7a8a;font-style:italic">'
                        f'{t.get("notes","")}</div>', unsafe_allow_html=True)
        with c6:
            st.markdown(f'<div class="sg-todo-meta">{t.get("updated","")}</div>',
                        unsafe_allow_html=True)
        with c7:
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("✎", key=f"ae_{t['id']}", help="Edit"):
                    st.session_state.edit_id = t["id"]
                    st.session_state.show_modal = True
                    st.rerun()
            with b2:
                lbl2 = "↩" if t["status"] == "Done" else "✓"
                help2 = "Reopen" if t["status"] == "Done" else "Mark Done"
                if st.button(lbl2, key=f"ad_{t['id']}", help=help2):
                    set_status(t["id"], "Open" if t["status"] == "Done" else "Done")
                    st.rerun()
            with b3:
                if st.button("✕", key=f"ax_{t['id']}", help="Delete"):
                    delete_todo(t["id"])
                    st.rerun()

# ── Tab: By Company ───────────────────────────────────────────────────────────

def render_by_company(todos: list[dict]) -> None:
    companies = sorted({t["company"] for t in todos})

    # Top worst offenders
    company_open = {c: sum(1 for t in todos if t["company"] == c and t["status"] != "Done")
                    for c in companies}
    top = max(company_open, key=company_open.get) if company_open else "—"

    st.markdown(f"""
<div class="sg-stats">
  <div class="sg-stat">
    <div class="sg-stat-value">{len(companies)}</div>
    <div class="sg-stat-label">Companies</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#4f8ef7">{open_count(todos)}</div>
    <div class="sg-stat-label">Open Items</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#d4875a">{sum(1 for t in todos if t.get('waiting_on_them'))}</div>
    <div class="sg-stat-label">Waiting on Them</div>
  </div>
  <div class="sg-stat">
    <div class="sg-stat-value" style="color:#e8c44a;font-size:1.1rem">{top}</div>
    <div class="sg-stat-label">Most Pending</div>
  </div>
</div>
""", unsafe_allow_html=True)

    for company in companies:
        ctodos = [t for t in todos if t["company"] == company]
        c_open    = sum(1 for t in ctodos if t["status"] == "Open")
        c_inp     = sum(1 for t in ctodos if t["status"] == "In Progress")
        c_waiting = sum(1 for t in ctodos if t.get("waiting_on_them"))
        c_done    = sum(1 for t in ctodos if t["status"] == "Done")
        owners    = ", ".join(sorted({t["owner"] for t in ctodos}))

        with st.expander(f"{company}  ·  {len(ctodos)} items", expanded=False):
            st.markdown(f"""
<div class="sg-company-stats" style="margin-bottom:0.8rem">
  <div class="sg-company-stat">Open: <b>{c_open}</b></div>
  <div class="sg-company-stat">In Progress: <b>{c_inp}</b></div>
  <div class="sg-company-stat">Waiting on Them: <b>{c_waiting}</b></div>
  <div class="sg-company-stat">Done: <b>{c_done}</b></div>
  <div class="sg-company-stat">Owners: <b>{owners}</b></div>
</div>
""", unsafe_allow_html=True)

            for t in ctodos:
                done_cls = "done" if t["status"] == "Done" else ""
                desc_cls = "done-text" if t["status"] == "Done" else ""
                wb = waiting_badge() if t.get("waiting_on_them") else ""
                p = PEOPLE.get(t["owner"], {"color": "#888", "bg": "#222"})

                st.markdown(f"""
<div class="sg-todo-item {done_cls}">
  <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:3px">
    <span class="sg-badge" style="background:{p['bg']};color:{p['color']};
      width:22px;height:22px;font-size:0.6rem">{t['owner']}</span>
    <span class="sg-todo-desc {desc_cls}">{t['description']}</span>
  </div>
  {status_badge(t['status'])} {wb}
  <div class="sg-todo-meta">Updated {t.get('updated','—')}</div>
</div>
""", unsafe_allow_html=True)

# ── Tab: Weekly Summary ───────────────────────────────────────────────────────

def render_weekly_summary(todos: list[dict]) -> None:
    today = date.today().strftime("%B %d, %Y")
    lines = [f"INTERNAL PROCESS MEETING — WEEKLY SUMMARY", f"Generated: {today}", ""]

    # By person
    lines.append("═" * 55)
    lines.append("BY PERSON")
    lines.append("═" * 55)
    for owner in PEOPLE:
        ptodos = [t for t in todos if t["owner"] == owner]
        open_items   = [t for t in ptodos if t["status"] == "Open"]
        inp_items    = [t for t in ptodos if t["status"] == "In Progress"]
        wait_items   = [t for t in ptodos if t.get("waiting_on_them")]
        done_items   = [t for t in ptodos if t["status"] == "Done"]

        lines.append(f"\n{owner}  ({open_count(ptodos)} open / {len(ptodos)} total)")
        lines.append("─" * 40)
        for t in open_items + inp_items:
            wt = " [BALL IN THEIR COURT]" if t.get("waiting_on_them") else ""
            lines.append(f"  [{t['status'].upper()[:4]}] {t['company']} — {t['description']}{wt}")
            if t.get("notes"):
                lines.append(f"         ↳ {t['notes']}")
        for t in done_items:
            lines.append(f"  [DONE] {t['company']} — {t['description']}")

    # By company
    lines.append("\n\n" + "═" * 55)
    lines.append("BY COMPANY")
    lines.append("═" * 55)
    companies = sorted({t["company"] for t in todos})
    for company in companies:
        ctodos = [t for t in todos if t["company"] == company]
        lines.append(f"\n{company}")
        for t in ctodos:
            wt = " [BALL IN THEIR COURT]" if t.get("waiting_on_them") else ""
            lines.append(f"  {t['owner']}  [{t['status'].upper()[:4]}]  {t['description']}{wt}")

    summary_text = "\n".join(lines)

    st.markdown('<div class="sg-summary-block">' + summary_text.replace("\n", "<br>") + "</div>",
                unsafe_allow_html=True)

    # Export buttons
    st.markdown("<br>", unsafe_allow_html=True)
    col_txt, col_csv, _ = st.columns([2, 2, 6])
    with col_txt:
        st.download_button(
            "⬇ Download Summary (.txt)",
            data=summary_text,
            file_name=f"weekly_summary_{date.today()}.txt",
            mime="text/plain",
            key="dl_txt",
        )
    with col_csv:
        # CSV export of all todos
        buf = io.StringIO()
        fieldnames = ["id", "owner", "company", "description", "status",
                      "waiting_on_them", "notes", "created", "updated"]
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(todos)
        st.download_button(
            "⬇ Export All To-Dos (.csv)",
            data=buf.getvalue(),
            file_name=f"todos_{date.today()}.csv",
            mime="text/csv",
            key="dl_csv",
        )

# ── Top action bar ────────────────────────────────────────────────────────────

def render_action_bar() -> None:
    col_add, col_export, _ = st.columns([2, 2, 8])
    with col_add:
        if st.button("＋ Add To-Do", key="global_add"):
            st.session_state.show_modal = True
            st.session_state.edit_id = None
            st.rerun()
    with col_export:
        # quick CSV download shortcut
        buf = io.StringIO()
        fieldnames = ["id", "owner", "company", "description", "status",
                      "waiting_on_them", "notes", "created", "updated"]
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(st.session_state.todos)
        st.download_button(
            "⬇ Export CSV",
            data=buf.getvalue(),
            file_name=f"todos_{date.today()}.csv",
            mime="text/csv",
            key="header_csv",
        )

# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    init_state()
    inject_css()
    render_header()
    render_stats(st.session_state.todos)

    if st.session_state.show_modal:
        render_modal()

    render_action_bar()
    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "By Person", "All To-Dos", "By Company", "Weekly Summary"
    ])

    with tab1:
        render_by_person(st.session_state.todos)
    with tab2:
        render_all_todos(st.session_state.todos)
    with tab3:
        render_by_company(st.session_state.todos)
    with tab4:
        render_weekly_summary(st.session_state.todos)


if __name__ == "__main__":
    main()
