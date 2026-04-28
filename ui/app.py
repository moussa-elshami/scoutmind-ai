import re
import streamlit as st
import os
import time as _time

from dotenv import load_dotenv
load_dotenv()

def _parse_duration_minutes(value) -> int | None:
    """Convert LLM-returned custom_duration to int minutes or None.
    Handles: integers, plain numeric strings ("180"), hour strings ("3 hours ...").
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    # Plain integer string
    if s.isdigit():
        return int(s)
    # "N hours" anywhere in the string
    m = re.search(r'(\d+(?:\.\d+)?)\s*hour', s, re.IGNORECASE)
    if m:
        return int(float(m.group(1)) * 60)
    # "N minutes" or "N min"
    m = re.search(r'(\d+)\s*min', s, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Leading integer before any non-digit
    m = re.match(r'(\d+)', s)
    if m:
        return int(m.group(1))
    return None


from database.models import init_db
from auth.auth import register_user, login_user, update_profile, DISTRICTS, UNITS
from memory.session_store import (
    get_user_sessions, create_session, get_session_messages,
    add_message, delete_session, update_session_title,
)
from agents.orchestrator import run_pipeline, run_conversation_agent
from tools.pdf_exporter import export_plan_to_pdf

# ── Initialize DB ─────────────────────────────────────────────────────────────
init_db()


def _parse_thinking_msg(msg: dict) -> tuple:
    """Returns (elapsed_str, html) from a thinking message, handling both
    in-memory format (has 'elapsed' key) and DB-loaded format ('[elapsed:...]<html>')."""
    content = msg.get("content", "")
    elapsed = msg.get("elapsed", "")
    if not elapsed and content.startswith("[elapsed:"):
        end = content.find("]")
        if end > 0:
            elapsed = content[9:end]
            content = content[end + 1:]
    return elapsed or "some time", content

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ScoutMind",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Browser Scripts ──────────────────────────────────────────────────────────
st.markdown("""
<script>
// Force sidebar to always stay open
(function() {
    function forceSidebarOpen() {
        var doc = window.parent.document;
        // Find the collapsed sidebar button and click it if sidebar is collapsed
        var collapsed = doc.querySelector('[data-testid="collapsedControl"]');
        if (collapsed) {
            collapsed.click();
        }
        // Also remove any collapsed class
        var sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (sidebar) {
            sidebar.style.display = 'block';
            sidebar.style.visibility = 'visible';
            sidebar.style.width = '';
            sidebar.style.minWidth = '';
        }
    }
    forceSidebarOpen();
    setTimeout(forceSidebarOpen, 100);
    setTimeout(forceSidebarOpen, 500);
})();

if (!window._popstateAdded) {
    window._popstateAdded = true;
    window.addEventListener('popstate', function() { window.location.reload(); });
}
if (!window._pwRevealObserver) {
    function blockPasswordReveal() {
        document.querySelectorAll('input[type="password"]').forEach(function(el) {
            if (el.dataset.revealBlocked) return;
            el.dataset.revealBlocked = 'true';
            var wrap = el.parentElement;
            if (!wrap) return;
            if (getComputedStyle(wrap).position === 'static') wrap.style.position = 'relative';
            var blocker = document.createElement('div');
            blocker.style.cssText = [
                'position:absolute','top:2px','right:2px','bottom:2px',
                'width:30px','z-index:9999',
                'background:#ffffff','border-radius:4px',
                'cursor:text','pointer-events:auto'
            ].join(';');
            blocker.addEventListener('mousedown', function(e) {
                e.preventDefault(); e.stopPropagation(); el.focus();
            });
            wrap.appendChild(blocker);
        });
    }
    blockPasswordReveal();
    window._pwRevealObserver = new MutationObserver(blockPasswordReveal);
    window._pwRevealObserver.observe(document.body, { childList: true, subtree: true });
}
</script>
""", unsafe_allow_html=True)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600;700&family=Crimson+Pro:wght@300;400;500;600&display=swap');

:root {
    --purple-deep:    #4C1D95;
    --purple-primary: #7C3AED;
    --purple-light:   #EDE9FE;
    --purple-faint:   #F5F3FF;
    --white:          #FFFFFF;
    --text-primary:   #1A1A2E;
    --text-secondary: #4B5563;
    --text-muted:     #9CA3AF;
    --border:         #E5E7EB;
    --border-purple:  #DDD6FE;
    --shadow:         0 4px 24px rgba(124,58,237,0.08);
    --shadow-hover:   0 8px 32px rgba(124,58,237,0.16);
}

html, body, [class*="css"] {
    font-family: 'Crimson Pro', Georgia, serif !important;
    color: var(--text-primary);
}
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
.stApp { background-color: var(--white); }
input[type="password"]::-ms-reveal,
input[type="password"]::-ms-clear { display: none !important; }

/* Hide only the sidebar collapse/expand arrow button */
[data-testid="collapsedControl"] { display: none !important; }
section[data-testid="stSidebar"] > div:first-child > div > div > button { display: none !important; }

/* Force sidebar always visible */
[data-testid="stSidebar"] {
    transform: none !important;
    min-width: 240px !important;
    visibility: visible !important;
}

[data-testid="stSidebar"] {
    background: #2D1155 !important;
    border-right: none !important;
}
[data-testid="stSidebar"] * { color: #E9D5FF !important; }

/* All sidebar buttons — clean borderless like ChatGPT */
[data-testid="stSidebar"] .stButton button {
    background: transparent !important;
    border: none !important;
    color: #E9D5FF !important;
    width: 100%;
    text-align: left;
    padding: 8px 10px !important;
    border-radius: 6px !important;
    font-family: 'Crimson Pro', serif !important;
    font-size: 14px !important;
    font-weight: 400 !important;
    transition: background 0.15s ease;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(255,255,255,0.08) !important;
    border: none !important;
    box-shadow: none !important;
}

.stButton button {
    background: var(--purple-primary) !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'Crimson Pro', serif !important;
    font-size: 16px !important;
    font-weight: 500 !important;
    padding: 10px 24px !important;
    transition: all 0.2s ease !important;
}
.stButton button:hover {
    background: var(--purple-deep) !important;
    box-shadow: var(--shadow-hover) !important;
    transform: translateY(-1px) !important;
}

.stTextInput input, .stSelectbox select, .stDateInput input {
    border: 1px solid var(--border-purple) !important;
    border-radius: 6px !important;
    font-family: 'Crimson Pro', serif !important;
    font-size: 15px !important;
    color: var(--text-primary) !important;
    background: var(--white) !important;
    padding: 10px 14px !important;
}
.stTextInput label, .stSelectbox label, .stDateInput label {
    font-family: 'Crimson Pro', serif !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: var(--text-secondary) !important;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

.chat-user {
    background: var(--purple-faint);
    border: 1px solid var(--border-purple);
    border-radius: 12px 12px 4px 12px;
    padding: 14px 18px;
    margin: 8px 0 8px 60px;
    font-family: 'Crimson Pro', serif;
    font-size: 16px;
}
.chat-assistant {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: 12px 12px 12px 4px;
    padding: 14px 18px;
    margin: 8px 60px 8px 0;
    font-family: 'Crimson Pro', serif;
    font-size: 16px;
    line-height: 1.7;
}
.chat-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 6px;
}
.chat-plan {
    background: var(--white);
    border: 1px solid var(--border-purple);
    border-left: 4px solid var(--purple-primary);
    border-radius: 0 8px 8px 0;
    padding: 16px 20px;
    margin: 8px 0;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    white-space: pre-wrap;
    line-height: 1.6;
    max-height: 500px;
    overflow-y: auto;
}

.agent-block {
    border-left: 3px solid var(--purple-primary);
    background: var(--purple-faint);
    border-radius: 0 6px 6px 0;
    padding: 8px 14px;
    margin: 3px 0;
    font-size: 13px;
    font-style: italic;
    color: var(--text-secondary);
}
.agent-block.done {
    border-left-color: #10B981;
    background: #F0FDF4;
    color: #065F46;
    font-style: normal;
}
.agent-block.error {
    border-left-color: #EF4444;
    background: #FFF1F2;
    color: #991B1B;
    font-style: normal;
}
.agent-name {
    font-weight: 700;
    font-style: normal;
    font-size: 11px;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    margin-bottom: 3px;
    color: var(--purple-primary);
}
.agent-name.done  { color: #10B981; }
.agent-name.error { color: #EF4444; }

.profile-card {
    background: rgba(124,58,237,0.15);
    border: 1px solid rgba(167,139,250,0.3);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 20px;
}
.profile-name {
    font-family: 'Cormorant Garamond', serif;
    font-size: 18px;
    font-weight: 600;
    color: #F3E8FF !important;
    margin-bottom: 4px;
}
.profile-detail { font-size: 13px; color: #C4B5FD !important; line-height: 1.6; }

.landing-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 64px;
    font-weight: 700;
    color: var(--purple-deep);
    letter-spacing: -1px;
    line-height: 1.1;
}
.landing-accent  { color: var(--purple-primary); }
.landing-subtitle { font-size: 20px; color: var(--text-secondary); line-height: 1.6; }
.scout-card {
    background: var(--white);
    border: 1px solid var(--border-purple);
    border-radius: 10px;
    padding: 24px;
    box-shadow: var(--shadow);
    margin-bottom: 16px;
}
.section-header {
    font-family: 'Cormorant Garamond', serif;
    font-size: 28px;
    font-weight: 600;
    color: var(--purple-deep);
    margin-bottom: 6px;
}
.section-subheader { font-size: 16px; color: var(--text-secondary); margin-bottom: 24px; }
hr { border: none; border-top: 1px solid var(--border-purple); margin: 24px 0; }

/* ── Success / Error ── */
.stSuccess {
    background: #F0FDF4 !important;
    border: 1px solid #86EFAC !important;
    border-radius: 6px !important;
}
.stError {
    background: #FFF1F2 !important;
    border: 1px solid #FECDD3 !important;
    border-radius: 6px !important;
}

/* ── Session History Items ── */
.session-item {
    padding: 10px 14px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.15s ease;
    border: 1px solid transparent;
}
.session-item:hover {
    background: rgba(124,58,237,0.1);
    border-color: rgba(167,139,250,0.3);
}
.session-title {
    font-size: 14px;
    color: #E9D5FF !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.session-date {
    font-size: 11px;
    color: #A78BFA !important;
    margin-top: 2px;
}

/* ── New Chat Button ── */
.new-chat-btn button {
    background: var(--purple-primary) !important;
    color: white !important;
    width: 100%;
    border-radius: 8px !important;
    font-size: 15px !important;
    padding: 12px !important;
    margin-bottom: 16px;
}

/* ── Tab Styling ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--purple-faint);
    border-radius: 8px;
    padding: 4px;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Crimson Pro', serif !important;
    font-size: 15px !important;
    border-radius: 6px !important;
    color: var(--text-secondary) !important;
}
.stTabs [aria-selected="true"] {
    background: var(--purple-primary) !important;
    color: white !important;
}

/* ── Thinking Box ── */
.thinking-box {
    background: var(--purple-faint);
    border-left: 3px solid var(--purple-primary);
    border-radius: 0 8px 8px 0;
    padding: 12px 16px;
    margin: 8px 0;
    font-family: 'Crimson Pro', serif;
    font-size: 14px;
    color: var(--text-secondary);
    font-style: italic;
}
</style>
""", unsafe_allow_html=True)


# ── Session State ─────────────────────────────────────────────────────────────
VALID_PAGES = {"landing", "login", "register", "app", "profile"}

def init_session_state():
    defaults = {
        "page":             "landing",
        "user":             None,
        "current_session":  None,
        "messages":         [],
        "form_error":       "",
        "form_success":     "",
        "confirm_delete":   None,
        "generating":       None,
        "last_plan_state":  None,
        "cached_pdf":       None,
        "cached_pdf_key":   None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
    url_page = st.query_params.get("page", None)
    if url_page in VALID_PAGES:
        st.session_state.page = url_page

init_session_state()


# ── Navigation ────────────────────────────────────────────────────────────────
def go_to(page: str):
    st.session_state.page         = page
    st.session_state.form_error   = ""
    st.session_state.form_success = ""
    st.query_params["page"] = page
    st.rerun()

def logout():
    for key in ["user", "current_session", "messages", "last_plan_state", "generating"]:
        st.session_state[key] = None if key != "messages" else []
    go_to("landing")


# ── PDF Download Helper ───────────────────────────────────────────────────────
def get_pdf_bytes(plan_state: dict):
    try:
        os.makedirs("outputs", exist_ok=True)
        import time
        user  = st.session_state.user
        fname = f"outputs/plan_{user['id']}_{int(time.time())}.pdf"
        plan  = plan_state.get("plan")
        if not plan:
            return None
        export_plan_to_pdf(plan, fname)
        with open(fname, "rb") as f:
            return f.read()
    except Exception as e:
        st.error(f"PDF generation failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 1 — LANDING
# ══════════════════════════════════════════════════════════════════════════════
def render_landing():
    col_left, col_right = st.columns([1.2, 1], gap="large")
    with col_left:
        st.markdown("<div style='padding-top:80px;'>", unsafe_allow_html=True)
        st.markdown("""
        <div class='landing-title'>Scout<span class='landing-accent'>Mind</span></div>
        <div style='margin-top:16px;margin-bottom:32px;'>
            <p class='landing-subtitle'>
                An intelligent meeting planning system for the Lebanese Scouts Association.
                Generate professional, age-appropriate weekly meeting plans in seconds.
            </p>
        </div>
        """, unsafe_allow_html=True)
        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            if st.button("Login",    key="landing_login",    use_container_width=True): go_to("login")
        with c2:
            if st.button("Register", key="landing_register", use_container_width=True): go_to("register")
        st.markdown("""
        <div style='margin-top:48px;display:flex;gap:32px;'>
            <div><div style='font-family:Cormorant Garamond,serif;font-size:32px;font-weight:700;color:#7C3AED;'>6</div>
                 <div style='font-size:13px;color:#6B7280;letter-spacing:0.5px;text-transform:uppercase;'>Scout Units</div></div>
            <div><div style='font-family:Cormorant Garamond,serif;font-size:32px;font-weight:700;color:#7C3AED;'>4</div>
                 <div style='font-size:13px;color:#6B7280;letter-spacing:0.5px;text-transform:uppercase;'>Districts</div></div>
            <div><div style='font-family:Cormorant Garamond,serif;font-size:32px;font-weight:700;color:#7C3AED;'>AI</div>
                 <div style='font-size:13px;color:#6B7280;letter-spacing:0.5px;text-transform:uppercase;'>Powered</div></div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with col_right:
        st.markdown("<div style='padding-top:60px;'>", unsafe_allow_html=True)
        for title, body in [
            ("Multi-Agent Intelligence", "Six specialized AI agents collaborate to design every meeting — from educational sequencing to scouting values alignment."),
            ("Age-Appropriate Design",   "Tailored plans for Beavers through Rovers, incorporating evidence-based educational therapy techniques."),
            ("Print-Ready Output",       "Every plan includes full activity descriptions, timing, materials lists, and exports directly to PDF."),
        ]:
            st.markdown(f"""
            <div class='scout-card'>
                <div style='font-family:Cormorant Garamond,serif;font-size:13px;text-transform:uppercase;
                            letter-spacing:1px;color:#7C3AED;margin-bottom:10px;font-weight:600;'>{title}</div>
                <div style='font-size:16px;color:#374151;line-height:1.6;'>{body}</div>
            </div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("""
    <div style='position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
                font-size:13px;color:#9CA3AF;'>
        Lebanese Scouts Association &mdash; ScoutMind v1.0
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 2 — REGISTER
# ══════════════════════════════════════════════════════════════════════════════
def render_register():
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("<div style='padding-top:40px;'>", unsafe_allow_html=True)
        st.markdown("""
        <div style='text-align:center;margin-bottom:32px;'>
            <div style='font-family:Cormorant Garamond,serif;font-size:40px;font-weight:700;color:#4C1D95;'>Create Account</div>
            <div style='font-size:16px;color:#6B7280;margin-top:6px;'>Join ScoutMind — Lebanese Scouts Association</div>
        </div>""", unsafe_allow_html=True)

        if st.session_state.form_error:   st.error(st.session_state.form_error)
        if st.session_state.form_success: st.success(st.session_state.form_success)

        full_name = st.text_input("Full Name",        placeholder="Enter your full name",   key="reg_full_name")
        email     = st.text_input("Email Address",    placeholder="your@email.com",         key="reg_email")
        password  = st.text_input("Password",         type="password", placeholder="Minimum 8 characters", key="reg_password")

        # Password strength bar — updates on each keystroke via on_change
        if password:
            has_upper = any(c.isupper() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_spec  = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
            score     = sum([len(password) >= 8, len(password) >= 12, has_upper, has_digit, has_spec])
            if score <= 2:
                label, color, pct = "Weak",   "#EF4444", 33
            elif score == 3:
                label, color, pct = "Medium", "#F59E0B", 66
            else:
                label, color, pct = "Strong", "#10B981", 100
            st.markdown(
                f"<div style='margin:-4px 0 10px 0;'>"
                f"<div style='display:flex;justify-content:space-between;margin-bottom:4px;'>"
                f"<span style='font-size:12px;color:#6B7280;'>Password strength</span>"
                f"<span style='font-size:12px;font-weight:600;color:{color};'>{label}</span></div>"
                f"<div style='background:#E5E7EB;border-radius:4px;height:6px;'>"
                f"<div style='background:{color};width:{pct}%;height:6px;border-radius:4px;transition:width 0.3s;'></div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )

        confirm  = st.text_input("Confirm Password", type="password", placeholder="Repeat your password",  key="reg_confirm")
        district = st.selectbox("District", options=list(DISTRICTS.keys()), key="reg_district")
        group    = st.selectbox("Group",    options=DISTRICTS[district],    key="reg_group")
        unit     = st.selectbox("Unit",     options=UNITS,                  key="reg_unit")

        st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
        if st.button("Create Account", use_container_width=True, key="reg_submit"):
            if not all([full_name, email, password, confirm]):
                st.session_state.form_error = "Please fill in all fields."
            elif len(password) < 8:
                st.session_state.form_error = "Password must be at least 8 characters."
            elif password != confirm:
                st.session_state.form_error = "Passwords do not match."
            elif "@" not in email or "." not in email:
                st.session_state.form_error = "Please enter a valid email address."
            else:
                result = register_user(full_name, email, password, district, group, unit)
                if result["success"]:
                    st.session_state.form_success = (
                        "Account created. Please verify your email before signing in."
                        if result["email_sent"]
                        else "Account created successfully. You can now sign in."
                    )
                    go_to("login")
                else:
                    st.session_state.form_error = result["error"]
            st.rerun()

        st.markdown("<div style='text-align:center;margin-top:20px;font-size:15px;color:#6B7280;'>Already have an account?</div>", unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            if st.button("Back to Login", key="reg_to_login",   use_container_width=True): go_to("login")
        with cb:
            if st.button("← Home",        key="reg_to_landing", use_container_width=True): go_to("landing")
        st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 3 — LOGIN
# ══════════════════════════════════════════════════════════════════════════════
def render_login():
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<div style='padding-top:60px;'>", unsafe_allow_html=True)
        st.markdown("""
        <div style='text-align:center;margin-bottom:32px;'>
            <div style='font-family:Cormorant Garamond,serif;font-size:48px;font-weight:700;
                        color:#4C1D95;letter-spacing:-1px;'>ScoutMind</div>
            <div style='font-size:16px;color:#6B7280;margin-top:6px;'>Sign in to your account</div>
        </div>""", unsafe_allow_html=True)

        if st.session_state.form_error:   st.error(st.session_state.form_error)
        if st.session_state.form_success: st.success(st.session_state.form_success)

        with st.form("login_form", clear_on_submit=False):
            email    = st.text_input("Email Address", placeholder="your@email.com")
            password = st.text_input("Password", type="password", placeholder="Your password")
            st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            if not email or not password:
                st.session_state.form_error = "Please enter your email and password."
                st.rerun()
            else:
                result = login_user(email, password)
                if result["success"]:
                    st.session_state.user            = result["user"]
                    st.session_state.form_error      = ""
                    st.session_state.form_success    = ""
                    st.session_state.current_session = None
                    st.session_state.messages        = []
                    go_to("app")
                else:
                    st.session_state.form_error = result["error"]
                    st.rerun()

        st.markdown("<div style='text-align:center;margin-top:20px;font-size:15px;color:#6B7280;'>Don't have an account?</div>", unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            if st.button("Create Account", key="login_to_reg",     use_container_width=True): go_to("register")
        with cb:
            if st.button("← Home",          key="login_to_landing", use_container_width=True): go_to("landing")
        st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def render_sidebar():
    user = st.session_state.user
    with st.sidebar:
        st.markdown(f"""
        <div class='profile-card'>
            <div class='profile-name'>{user['full_name']}</div>
            <div class='profile-detail'>{user['unit']} Leader<br>{user['group_name']} &mdash; {user['district']}</div>
        </div>""", unsafe_allow_html=True)

        if st.button("+ New Meeting Plan", key="new_chat", use_container_width=True):
            st.session_state.current_session = None
            st.session_state.messages        = []
            st.session_state.last_plan_state = None
            st.session_state.generating      = None
            go_to("app")

        st.markdown("<hr style='border-color:rgba(167,139,250,0.2);margin:8px 0;'>", unsafe_allow_html=True)
        if st.button("Edit Profile", key="nav_profile", use_container_width=True): go_to("profile")
        st.markdown("<hr style='border-color:rgba(167,139,250,0.2);margin:8px 0;'>", unsafe_allow_html=True)

        st.markdown("""
        <div style='font-size:11px;letter-spacing:1px;text-transform:uppercase;
                    color:#A78BFA;font-weight:600;padding:4px 0 8px 0;'>Recent Plans</div>
        """, unsafe_allow_html=True)

        sessions = get_user_sessions(user["id"])
        if not sessions:
            st.markdown("<div style='font-size:14px;color:#7C6A9E;padding:8px 0;font-style:italic;'>No plans generated yet.</div>", unsafe_allow_html=True)
        else:
            for session in sessions[:20]:
                cs, cd = st.columns([5, 1])
                with cs:
                    label = session["title"][:32] + "..." if len(session["title"]) > 32 else session["title"]
                    if st.button(label, key=f"sess_{session['id']}", use_container_width=True):
                        st.session_state.current_session = session["id"]
                        st.session_state.confirm_delete  = None
                        st.session_state.last_plan_state = None
                        st.session_state.generating      = None
                        st.session_state.messages = get_session_messages(session["id"], user["id"])
                        go_to("app")
                with cd:
                    if st.button("x", key=f"del_{session['id']}"):
                        st.session_state.confirm_delete = session["id"]
                        st.rerun()

                if st.session_state.confirm_delete == session["id"]:
                    st.markdown("<div style='font-size:12px;color:#F87171;padding:4px 0;'>Delete this plan?</div>", unsafe_allow_html=True)
                    cy, cn = st.columns(2)
                    with cy:
                        if st.button("Yes", key=f"yes_{session['id']}", use_container_width=True):
                            delete_session(session["id"], user["id"])
                            st.session_state.confirm_delete = None
                            if st.session_state.current_session == session["id"]:
                                st.session_state.current_session = None
                                st.session_state.messages        = []
                                st.session_state.last_plan_state = None
                            st.rerun()
                    with cn:
                        if st.button("No", key=f"no_{session['id']}", use_container_width=True):
                            st.session_state.confirm_delete = None
                            st.rerun()

        st.markdown("<hr style='border-color:rgba(167,139,250,0.2);'>", unsafe_allow_html=True)
        if st.button("Sign Out", key="logout", use_container_width=True):
            logout()


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 4 — MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
def render_app():
    render_sidebar()
    user = st.session_state.user

    st.markdown(f"""
    <div style='padding:8px 0 24px 0;border-bottom:1px solid #EDE9FE;margin-bottom:24px;'>
        <div style='font-family:Cormorant Garamond,serif;font-size:32px;font-weight:700;color:#4C1D95;'>ScoutMind</div>
        <div style='font-size:15px;color:#6B7280;'>{user['unit']} Unit &mdash; {user['group_name']}, {user['district']} District</div>
    </div>""", unsafe_allow_html=True)

    messages = st.session_state.messages

    if not messages:
        st.markdown(f"""
        <div class='chat-assistant'>
            <div class='chat-label'>ScoutMind</div>
            Hello, <strong>{user['full_name']}</strong>. I am ScoutMind, your dedicated
            meeting planning assistant for the Lebanese Scouts Association.<br><br>
            I specialise exclusively in generating professional weekly meeting plans for scout units.
            Tell me which unit you are planning for and the theme of your meeting — or just
            describe what you need and I will guide you.<br><br>
            <em>Example: "I want to plan a Cubs meeting about friendship."</em>
        </div>""", unsafe_allow_html=True)
    else:
        for i, msg in enumerate(messages):
            if msg["role"] == "user":
                st.markdown(f"""
                <div class='chat-user'>
                    <div class='chat-label'>You</div>
                    {msg['content']}
                </div>""", unsafe_allow_html=True)
            elif msg["role"] == "thinking":
                elapsed, inner = _parse_thinking_msg(msg)
                with st.expander(f"Thought for {elapsed}"):
                    st.markdown(inner, unsafe_allow_html=True)
            elif msg["role"] == "plan":
                st.markdown(f"""
                <div class='chat-assistant'>
                    <div class='chat-label'>ScoutMind - Meeting Plan</div>
                </div>""", unsafe_allow_html=True)
                # Render plan as proper markdown
                st.markdown(msg['content'])
                # Quality score badge (only for the current session's plan)
                if st.session_state.last_plan_state:
                    qs = st.session_state.last_plan_state.get("plan", {}).get("quality_score")
                    if qs:
                        c1, c2, c3, c4, c5 = st.columns(5)
                        c1.metric("Overall Score", f"{qs['total']}/100", f"Grade {qs['grade']}")
                        c2.metric("Timing",         f"{qs['scores']['timing']}/25")
                        c3.metric("Structure",      f"{qs['scores']['structure']}/25")
                        c4.metric("Variety",        f"{qs['scores']['variety']}/25")
                        c5.metric("Context",        f"{qs['scores']['context_awareness']}/25")
                # PDF download button
                if st.session_state.last_plan_state:
                    h     = st.session_state.last_plan_state.get("plan", {}).get("header", {})
                    fname = f"ScoutMind_{h.get('unit','Plan')}_{h.get('theme','Meeting')}_{h.get('date','')}.pdf".replace(" ", "_")
                    if "cached_pdf" not in st.session_state or st.session_state.get("cached_pdf_key") != fname:
                        pdf_bytes = get_pdf_bytes(st.session_state.last_plan_state)
                        st.session_state.cached_pdf     = pdf_bytes
                        st.session_state.cached_pdf_key = fname
                    else:
                        pdf_bytes = st.session_state.cached_pdf
                    if pdf_bytes:
                        st.download_button(
                            label="Download as PDF",
                            data=pdf_bytes,
                            file_name=fname,
                            mime="application/pdf",
                            key=f"pdf_{i}",
                        )
            else:
                st.markdown(f"""
                <div class='chat-assistant'>
                    <div class='chat-label'>ScoutMind</div>
                    {msg['content']}
                </div>""", unsafe_allow_html=True)

    # Input
    st.markdown("<div style='margin-top:24px;'>", unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        ci, cb = st.columns([6, 1])
        with ci:
            user_input = st.text_input(
                "Message",
                placeholder="Describe what you need — unit, theme, or any question about meeting planning...",
                label_visibility="collapsed",
            )
        with cb:
            send = st.form_submit_button("Send", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if send and user_input.strip():
        user_msg = user_input.strip()
        st.session_state.messages.append({"role": "user", "content": user_msg})

        # Create session if needed
        if not st.session_state.current_session:
            sess = create_session(user["id"], title=user_msg[:60], unit=user["unit"])
            if sess["success"]:
                st.session_state.current_session = sess["session_id"]
        if st.session_state.current_session:
            add_message(st.session_state.current_session, user["id"], "user", user_msg)

        # Run conversation agent
        with st.spinner("ScoutMind is thinking..."):
            conv = run_conversation_agent(
                user_message=user_msg,
                conversation_history=st.session_state.messages[:-1],
                user_unit=user["unit"],
            )

        if conv.get("ready_to_generate"):
            ack = conv.get("response", f"Generating your {conv.get('unit', user['unit'])} meeting plan on the theme of {conv.get('theme', 'the requested topic')}. Please wait while the agents work...")
            st.session_state.messages.append({"role": "assistant", "content": ack})
            if st.session_state.current_session:
                add_message(st.session_state.current_session, user["id"], "assistant", ack)

            # Store generation params and trigger generation page
            st.session_state.generating = {
                "unit":               conv.get("unit", user["unit"]),
                "theme":              conv.get("theme", "General"),
                "meeting_date":       conv.get("meeting_date"),
                "custom_duration":    _parse_duration_minutes(conv.get("custom_duration")),
                "meeting_start_time": conv.get("meeting_start_time"),
            }
        else:
            reply = conv.get("response", "I am here to help with scout meeting planning.")
            st.session_state.messages.append({"role": "assistant", "content": reply})
            if st.session_state.current_session:
                add_message(st.session_state.current_session, user["id"], "assistant", reply)

        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# GENERATION VIEW — Live agent thinking
# ══════════════════════════════════════════════════════════════════════════════
def render_generating():
    render_sidebar()
    user = st.session_state.user
    gen  = st.session_state.generating

    st.markdown(f"""
    <div style='padding:8px 0 24px 0;border-bottom:1px solid #EDE9FE;margin-bottom:24px;'>
        <div style='font-family:Cormorant Garamond,serif;font-size:32px;font-weight:700;color:#4C1D95;'>ScoutMind</div>
        <div style='font-size:15px;color:#6B7280;'>Generating your {gen['unit']} meeting plan on <em>{gen['theme']}</em>...</div>
    </div>""", unsafe_allow_html=True)

    # Show previous chat messages
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"<div class='chat-user'><div class='chat-label'>You</div>{msg['content']}</div>", unsafe_allow_html=True)
        elif msg["role"] == "thinking":
            elapsed, inner = _parse_thinking_msg(msg)
            with st.expander(f"Thought for {elapsed}"):
                st.markdown(inner, unsafe_allow_html=True)
        elif msg["role"] == "assistant":
            st.markdown(f"<div class='chat-assistant'><div class='chat-label'>ScoutMind</div>{msg['content']}</div>", unsafe_allow_html=True)

    # ── Live thinking panel using st.status() ────────────────────────────────
    thoughts = []

    def _build_md():
        if not thoughts:
            return "*Starting agents...*"
        lines = []
        for t in thoughts:
            icon = "✓" if t["status"] == "done" else "✗" if t["status"] == "error" else "▸"
            lines.append(f"**{icon} {t['agent']}**  \n{t['thought'][:250]}")
        return "\n\n".join(lines)

    _start_time = _time.time()

    with st.status("Thinking...", expanded=True) as thinking_status:
        content_placeholder = st.empty()
        content_placeholder.markdown("*Starting agents...*")

        def progress_callback(agent, thought, status):
            found = False
            for t in thoughts:
                if t["agent"] == agent:
                    t.update({"thought": thought, "status": status})
                    found = True
                    break
            if not found:
                thoughts.append({"agent": agent, "thought": thought, "status": status})
            content_placeholder.markdown(_build_md())

        result = run_pipeline(
            unit=gen["unit"],
            theme=gen["theme"],
            meeting_date=gen.get("meeting_date"),
            custom_duration=gen.get("custom_duration"),
            meeting_start_time=gen.get("meeting_start_time"),
            conversation_history=st.session_state.messages,
            progress_callback=progress_callback,
        )

        elapsed = round(_time.time() - _start_time)
        elapsed_str = (
            f"{elapsed} second{'s' if elapsed != 1 else ''}"
            if elapsed < 60
            else f"{elapsed // 60} minute{'s' if elapsed // 60 != 1 else ''}"
        )

        thinking_status.update(
            label=f"Thought for {elapsed_str}",
            state="complete",
            expanded=False,
        )

    st.session_state.generating = None

    # Build plain-text thinking summary for history storage
    thinking_lines = []
    for t in thoughts:
        icon = "✓" if t["status"] == "done" else "✗" if t["status"] == "error" else "▸"
        thinking_lines.append(f"**{icon} {t['agent']}**  \n{t['thought'][:200]}")
    thinking_text = "\n\n".join(thinking_lines)

    db_content = f"[elapsed:{elapsed_str}]" + thinking_text
    st.session_state.messages.append({
        "role":    "thinking",
        "content": thinking_text,
        "elapsed": elapsed_str,
    })
    if st.session_state.current_session:
        add_message(st.session_state.current_session, user["id"], "thinking", db_content)

    if result.get("error"):
        error_msg = f"I encountered an issue generating the plan: {result['error']}. Please try again or rephrase your request."
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        if st.session_state.current_session:
            add_message(st.session_state.current_session, user["id"], "assistant", error_msg)
    else:
        plan_text = result.get("plan_text", "")
        st.session_state.messages.append({"role": "plan", "content": plan_text})
        st.session_state.last_plan_state = result

        if st.session_state.current_session:
            add_message(st.session_state.current_session, user["id"], "plan", plan_text)
            update_session_title(
                st.session_state.current_session,
                user["id"],
                f"{gen['unit']} - {gen['theme']} - {gen.get('meeting_date') or 'No date'}",
            )

    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 5 — EDIT PROFILE
# ══════════════════════════════════════════════════════════════════════════════
def render_profile():
    render_sidebar()
    user = st.session_state.user

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div class='section-header'>Edit Profile</div>
        <div class='section-subheader'>Update your details. Your email address cannot be changed.</div>
        """, unsafe_allow_html=True)

        if st.session_state.form_error:   st.error(st.session_state.form_error)
        if st.session_state.form_success: st.success(st.session_state.form_success)

        full_name = st.text_input("Full Name", value=user["full_name"])
        st.text_input("Email Address (cannot be changed)", value=user["email"], disabled=True)

        district_idx  = list(DISTRICTS.keys()).index(user["district"]) if user["district"] in DISTRICTS else 0
        district      = st.selectbox("District", options=list(DISTRICTS.keys()), index=district_idx)
        group_options = DISTRICTS[district]
        group_idx     = group_options.index(user["group_name"]) if user["group_name"] in group_options else 0
        group         = st.selectbox("Group", options=group_options, index=group_idx)
        unit_idx      = UNITS.index(user["unit"]) if user["unit"] in UNITS else 0
        unit          = st.selectbox("Unit", options=UNITS, index=unit_idx)

        st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
        if st.button("Save Changes", use_container_width=True):
            if not full_name.strip():
                st.session_state.form_error = "Full name cannot be empty."
                st.rerun()
            else:
                result = update_profile(user["id"], full_name, district, group, unit)
                if result["success"]:
                    st.session_state.user         = result["user"]
                    st.session_state.form_success = "Profile updated successfully."
                    st.session_state.form_error   = ""
                    st.rerun()
                else:
                    st.session_state.form_error = result["error"]
                    st.rerun()

        if st.button("Back to Chat", key="profile_back"):
            go_to("app")


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
def main():
    page = st.session_state.page

    if page in ("app", "profile") and not st.session_state.user:
        go_to("landing")
        return

    if   page == "landing":  render_landing()
    elif page == "register": render_register()
    elif page == "login":    render_login()
    elif page == "profile":  render_profile()
    elif page == "app":
        if st.session_state.generating:
            render_generating()
        else:
            render_app()
    else:
        go_to("landing")


if __name__ == "__main__":
    main()