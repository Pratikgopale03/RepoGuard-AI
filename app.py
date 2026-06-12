import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import textwrap
import os
from datetime import datetime

from analyzer import AnalysisError, analyze_repository
from charts import build_all_charts
from pdf_generator import generate_pdf_bytes

# ── Auth & Billing ─────────────────────────────────────────────────────────
try:
    from auth import register_user, login_user, decode_jwt
    from plans import PLANS, get_plan
    from token_tracker import record_usage, get_usage_today, analyses_remaining, tokens_remaining, estimate_tokens, can_run_analysis
    _AUTH_AVAILABLE = True
except ImportError:
    _AUTH_AVAILABLE = False


st.set_page_config(
    page_title="RepoGuard AI - Repository Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def inject_styles() -> None:
    with open("styles.css", encoding="utf-8", errors="ignore") as f:
        styles = f.read()
    
    is_pro = False
    try:
        is_pro = _is_pro_variant() or st.session_state.get("user_plan") == "pro"
    except Exception:
        pass

    if is_pro:
        # Premium Gold & Purple PRO theme styling overrides
        pro_styles = """
        :root {
          --mint: #eab308; /* Gold */
          --sky: #c084fc;  /* Purple */
        }
        body, .stApp {
          background:
            radial-gradient(circle at 10% 8%, rgba(192, 132, 252, 0.18), transparent 45%),
            radial-gradient(circle at 92% 14%, rgba(234, 179, 8, 0.18), transparent 45%),
            linear-gradient(170deg, #120a1c 0%, #06020c 62%, #020105 100%) !important;
        }
        .top-nav {
          border-color: rgba(192, 132, 252, 0.25) !important;
          background: linear-gradient(96deg, rgba(18, 9, 29, 0.88), rgba(10, 4, 18, 0.74)) !important;
          box-shadow: 0 14px 34px rgba(124, 58, 237, 0.15) !important;
        }
        .hero-wrap {
          border-color: rgba(192, 132, 252, 0.25) !important;
          background:
            radial-gradient(circle at 90% 10%, rgba(192, 132, 252, 0.15), transparent 40%),
            linear-gradient(120deg, rgba(10, 4, 18, 0.95), rgba(18, 9, 29, 0.78)) !important;
          box-shadow: 0 16px 34px rgba(124, 58, 237, 0.12) !important;
        }
        .input-panel {
          border-color: rgba(192, 132, 252, 0.25) !important;
          background: linear-gradient(140deg, rgba(18, 9, 29, 0.86), rgba(10, 4, 18, 0.74)) !important;
        }
        .mcard {
          border-color: rgba(192, 132, 252, 0.25) !important;
          background: linear-gradient(160deg, rgba(18, 9, 29, 0.86), rgba(10, 4, 18, 0.82)) !important;
        }
        .pro-badge {
          display: inline-flex;
          align-items: center;
          font-size: 10px;
          font-weight: 900;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          padding: 3px 10px;
          background: linear-gradient(90deg, #eab308, #c084fc);
          color: #120a1c !important;
          border-radius: 99px;
          box-shadow: 0 0 12px rgba(192, 132, 252, 0.4);
          margin-left: 8px;
          vertical-align: middle;
        }
        """
        styles += pro_styles
        
    st.markdown(f"<style>{styles}</style>", unsafe_allow_html=True)


def placeholder_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.5,
        text=f"<b>{title}</b><br><sup style='color:#5a8aaa'>Run analysis to populate this chart</sup>",
        showarrow=False,
        font={"size": 14, "color": "#5a8aaa"},
        xref="paper", yref="paper", align="center",
    )
    fig.update_layout(
        height=300,
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        paper_bgcolor="rgba(5,18,30,0.9)",
        plot_bgcolor="rgba(5,18,30,0.9)",
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return fig


def section_header(icon: str, title: str) -> None:
    html = f'<div class="sec-header"><span class="sec-icon">{icon}</span><span class="sec-title">{title}</span><div class="sec-line"></div></div>'
    st.markdown(html, unsafe_allow_html=True)


def risk_badge_html(risk: str) -> str:
    cls = f"risk-{risk.lower()}" if risk.lower() in ("low", "medium", "high", "critical") else "risk-medium"
    return f'<span class="risk-badge {cls}">{risk.upper()}</span>'


def _is_pro_variant() -> bool:
    return str(os.environ.get("PLANS_VARIANT", "")).strip() == "30"


def show_metric_cards(summary: dict, subtext: str) -> None:
    h = summary.get("health_score", "--")
    b = summary.get("bus_factor_percent", "--")
    d = summary.get("technical_debt_hours", "--")
    s = summary.get("security_score", "--")

    health_val  = f"{h}%" if h != "--" else "--"
    bus_val     = f"{b}%" if b != "--" else "--"
    debt_val    = f"{d} hrs" if d != "--" else "--"
    sec_val     = f"{s}%" if s != "--" else "--"

    st.markdown(
        f"""
        <div class="metric-grid">
            <div class="mcard health">
                <div class="mcard-label">Health Score</div>
                <div class="mcard-value">{health_val}</div>
                <div class="mcard-sub">{subtext}</div>
            </div>
            <div class="mcard bus">
                <div class="mcard-label">Bus Factor</div>
                <div class="mcard-value">{bus_val}</div>
                <div class="mcard-sub">{subtext}</div>
            </div>
            <div class="mcard debt">
                <div class="mcard-label">Technical Debt</div>
                <div class="mcard-value">{debt_val}</div>
                <div class="mcard-sub">{subtext}</div>
            </div>
            <div class="mcard security">
                <div class="mcard-label">Security Score</div>
                <div class="mcard-value">{sec_val}</div>
                <div class="mcard-sub">{subtext}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_insight_boxes(analysis_result: dict) -> None:
    ai = analysis_result.get("ai_analysis", {})
    repo = analysis_result.get("repository_data", {})

    health_rationale   = ai.get("repository_health_score", {}).get("rationale", "N/A")[:260]
    security_rationale = ai.get("security_risk", {}).get("rationale", "N/A")[:260]
    bus_rationale      = ai.get("bus_factor", {}).get("rationale", "N/A")[:260]
    debt_rationale     = ai.get("technical_debt", {}).get("rationale", "N/A")[:260]

    st.markdown(
        f"""
        <div class="insight-grid">
            <div class="insight-box">
                <div class="ib-title">Health Insight</div>
                {health_rationale}
            </div>
            <div class="insight-box">
                <div class="ib-title">Security Insight</div>
                {security_rationale}
            </div>
            <div class="insight-box">
                <div class="ib-title">Bus Factor Insight</div>
                {bus_rationale}
            </div>
            <div class="insight-box">
                <div class="ib-title">Technical Debt Insight</div>
                {debt_rationale}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_priorities_table(priorities: list) -> None:
    if not priorities:
        st.info("No refactoring priorities available yet.")
        return

    rows_html = ""
    for idx, item in enumerate(priorities[:5], start=1):
        risk = item.get("risk", "medium")
        rows_html += f"""
        <tr>
            <td><b style="color:#e8f8ff">#{idx}</b></td>
            <td><b style="color:#e8f8ff">{item.get('title', 'N/A')}</b></td>
            <td style="color:#94c4de">{item.get('area', 'N/A')}</td>
            <td style="text-align:center"><b style="color:#fbbf24">{item.get('effort_hours', 0)}h</b></td>
            <td>{risk_badge_html(risk)}</td>
            <td style="color:#5a8aaa;font-size:0.79rem">{item.get('recommendation', '')[:140]}</td>
        </tr>"""

    st.markdown(
        f"""
        <div style="border:1px solid rgba(100,180,230,0.15);border-radius:16px;overflow:hidden;background:rgba(5,18,30,0.8)">
            <table class="priority-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Title</th>
                        <th>Area</th>
                        <th style="text-align:center">Effort</th>
                        <th>Risk</th>
                        <th>Recommendation</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _repo_tree_html(tree: dict, root_label: str) -> str:
    if not isinstance(tree, dict):
        return ""

    def render_node(node: dict, depth: int = 0) -> str:
        name = node.get("name", "")
        node_type = node.get("type", "file")
        children = node.get("children", {}) if isinstance(node.get("children"), dict) else {}

        if depth == 0:
            label = root_label or "root"
        else:
            label = name

        if node_type == "dir":
            inner = "".join(
                render_node(child, depth + 1)
                for child in sorted(children.values(), key=lambda c: (c.get("type") != "dir", c.get("name", "")))
            )
            return (
                f"<details class=\"tree-node\" {'open' if depth < 2 else ''}>"
                f"<summary>📁 {label}</summary>"
                f"<div class=\"tree-children\">{inner}</div>"
                f"</details>"
            )

        return f"<div class=\"tree-file\">📄 {label}</div>"

    return render_node(tree)


def _branches_html(branches: list) -> str:
    if not isinstance(branches, list) or not branches:
        return ""
    items = []
    for branch in branches:
        name = branch.get("name", "unknown")
        sha = branch.get("commit_sha")
        short_sha = sha[:7] if isinstance(sha, str) else ""
        protected = branch.get("protected", False)
        badge = "<span class=\"branch-badge\">protected</span>" if protected else ""
        sha_html = f"<span class=\"branch-sha\">{short_sha}</span>" if short_sha else ""
        items.append(f"<div class=\"branch-item\"><span class=\"branch-name\">{name}</span>{badge}{sha_html}</div>")

    return "".join(items)


# ── Auth session bootstrap ─────────────────────────────────────────────────
def auth_session_bootstrap() -> None:
    """On every page load: decode the stored JWT and restore user session."""
    if not _AUTH_AVAILABLE:
        return
    for key in ["jwt", "user_email", "user_plan", "show_auth_modal", "auth_tab", "show_pricing"]:
        if key not in st.session_state:
            st.session_state[key] = None if key in ("jwt", "user_email", "user_plan") else False
    
    jwt_token = st.session_state.get("jwt")
    if jwt_token:
        payload = decode_jwt(jwt_token)
        if payload:
            email = payload.get("sub")
            st.session_state["user_email"] = email
            # Fetch latest plan from DB (to catch upgrades without waiting for JWT expiry)
            from auth import get_user
            user = get_user(email)
            st.session_state["user_plan"] = user.get("plan", "free") if user else "free"
        else:
            # Expired or invalid — clear session
            st.session_state["jwt"] = None
            st.session_state["user_email"] = None
            st.session_state["user_plan"] = None


def handle_query_token() -> None:
    """If the page was opened with ?token=..., decode it and bootstrap the Streamlit session."""
    if not _AUTH_AVAILABLE:
        return
    try:
        params = st.query_params
    except Exception:
        return
    
    token = params.get("token", [None])[0] if isinstance(params.get("token"), list) else params.get("token")
    repo = params.get("repo", [None])[0] if isinstance(params.get("repo"), list) else params.get("repo")
    
    def _apply_local_token(tok: str) -> bool:
        payload = decode_jwt(tok)
        if not payload:
            return False
        email = payload.get("sub")
        st.session_state["jwt"] = tok
        st.session_state["user_email"] = email
        from auth import get_user
        user = get_user(email)
        st.session_state["user_plan"] = user.get("plan", "free") if user else "free"
        if repo:
            st.session_state["prefill_repo"] = repo
        try:
            st.query_params.clear()
        except Exception:
            pass
        st.rerun()
        return True

    # ALWAYS process url token if present (even if logged in, to allow plan update redirects)
    if token:
        # Prefer validating token with the Node API to avoid JWT library incompatibilities
        api_base = os.environ.get('REACT_API_BASE', 'http://localhost:5174')
        try:
            import requests
            me = requests.get(f"{api_base}/api/me", headers={"Authorization": f"Bearer {token}"}, timeout=4)
            if me.status_code == 200:
                data = me.json()
                email = data.get('user')
                plan = data.get('plan', 'free')
                st.session_state['jwt'] = token
                st.session_state['user_email'] = email
                st.session_state['user_plan'] = plan
                if repo:
                    st.session_state['prefill_repo'] = repo
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.rerun()
            # Important: if API call succeeds but token is rejected (401/403),
            # still try local decode to avoid dropping users to landing/login.
            _apply_local_token(token)
        except Exception:
            # Fall back to local decode attempt if API check fails
            _apply_local_token(token)


# ── Auth modal (Login / Register) ──────────────────────────────────────────
def show_auth_modal() -> None:
    """Render login/register form inside a Streamlit container."""
    if not _AUTH_AVAILABLE:
        st.warning("Auth module not available — install PyJWT and bcrypt.")
        return
    with st.container():
        st.markdown('<div class="auth-modal-wrap">', unsafe_allow_html=True)
        tab_login, tab_reg = st.tabs(["🔐 Log In", "✨ Register"])

        with tab_login:
            st.markdown("### Welcome back")
            # Use a form so submit behavior is atomic and reliable across reruns
            with st.form(key="login_form"):
                email_l = st.text_input("Email", key="login_email", placeholder="you@example.com")
                pw_l = st.text_input("Password", key="login_pw", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Log In")
                if submitted:
                    if not email_l or not pw_l:
                        st.error("Please fill in both fields.")
                    else:
                        try:
                            token = login_user(email_l, pw_l)
                            st.session_state["jwt"] = token
                            payload = decode_jwt(token)
                            st.session_state["user_email"] = payload["sub"]
                            st.session_state["user_plan"] = payload["plan"]
                            st.session_state["show_auth_modal"] = False
                            st.success(f"Welcome back, {payload['sub']}!")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

        with tab_reg:
            st.markdown("### Create your account")
            with st.form(key="register_form"):
                email_r = st.text_input("Email", key="reg_email", placeholder="you@example.com")
                pw_r = st.text_input("Password", key="reg_pw", type="password", placeholder="Min 6 characters")
                pw_r2 = st.text_input("Confirm Password", key="reg_pw2", type="password", placeholder="••••••••")
                submitted_r = st.form_submit_button("Create Account")
                if submitted_r:
                    if not email_r or not pw_r:
                        st.error("Please fill in all fields.")
                    elif pw_r != pw_r2:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            token = register_user(email_r, pw_r)
                            st.session_state["jwt"] = token
                            payload = decode_jwt(token)
                            st.session_state["user_email"] = payload["sub"]
                            st.session_state["user_plan"] = payload["plan"]
                            st.session_state["show_auth_modal"] = False
                            st.success(f"Account created! Welcome, {payload['sub']} 🎉")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

        st.markdown('</div>', unsafe_allow_html=True)


# ── Pricing section ─────────────────────────────────────────────────────────
def show_pricing_section() -> None:
    """Show two pricing plan cards side by side."""
    st.markdown("<br>", unsafe_allow_html=True)
    free_plan = PLANS["free"]
    pro_plan  = PLANS["pro"]

    def _feature_list(features, not_included):
        rows = "".join(
            f'<li class="plan-feat"><span class="feat-icon">✓</span>{f}</li>'
            for f in features
        )
        rows += "".join(
            f'<li class="plan-feat disabled"><span class="feat-icon">✗</span>{f}</li>'
            for f in not_included
        )
        return rows

    st.markdown(
        f"""
        <div class="pricing-grid">
          <div class="plan-card">
            <div class="plan-name">{free_plan['name']}</div>
            <div class="plan-price">{free_plan['price']} <span class="plan-period">{free_plan['period']}</span></div>
            <ul class="plan-features">{_feature_list(free_plan['features'], free_plan['not_included'])}</ul>
          </div>
          <div class="plan-card plan-card--highlight">
            <div class="plan-badge">Most Popular</div>
            <div class="plan-name">{pro_plan['name']}</div>
            <div class="plan-price">{pro_plan['price']} <span class="plan-period">{pro_plan['period']}</span></div>
            <ul class="plan-features">{_feature_list(pro_plan['features'], pro_plan['not_included'])}</ul>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col_free, col_pro = st.columns(2)
    with col_free:
        if st.button("Get Started Free", key="pricing_free_cta", use_container_width=True):
            st.session_state["show_auth_modal"] = True
            st.session_state["show_pricing"] = False
            st.rerun()
    with col_pro:
        if st.button("Upgrade to Pro ↗", key="pricing_pro_cta", use_container_width=True, type="primary"):
            jwt_token = st.session_state.get("jwt") or ""
            react_pricing = os.environ.get('REACT_PRICING_URL', 'http://localhost:5173/pricing')
            url = f"{react_pricing}?token={jwt_token}" if jwt_token else react_pricing
            st.markdown(f'<script>window.location.href="{url}";</script>', unsafe_allow_html=True)


# ── Login Page (standalone) ───────────────────────────────────────────────
def show_login_page() -> None:
    st.markdown(
        """
        <div class="landing-header">
            <div class="landing-header-inner">
                <a class="landing-header-brand" href="?view=landing"><svg class="landing-header-logo" viewBox="0 0 24 24" width="26" height="26" fill="none" xmlns="http://www.w3.org/2000/svg" style="vertical-align: middle; margin-right: 8px;">
                              <path d="M12 2L3 5V11C3 16.55 6.84 21.74 12 23C17.16 21.74 21 16.55 21 11V5L12 2Z" stroke="url(#brand-logo-gradient-st)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
                              <path d="M12 6V18" stroke="url(#brand-logo-gradient-st)" stroke-width="2" stroke-dasharray="3 3" />
                              <path d="M8 12H16" stroke="url(#brand-logo-gradient-st)" stroke-width="2.5" stroke-linecap="round" />
                              <defs>
                                <linearGradient id="brand-logo-gradient-st" x1="3" y1="2" x2="21" y2="23" gradientUnits="userSpaceOnUse">
                                  <stop stop-color="#4ce3c1" />
                                  <stop offset="0.5" stop-color="#7dd3fc" />
                                  <stop offset="1" stop-color="#8b5cf6" />
                                </linearGradient>
                              </defs>
                            </svg>
                            <span>RepoGuard</span></a>
                <div class="landing-header-nav">
                    <a class="landing-header-link" href="?view=landing">Home</a>
                    <a class="landing-header-link" href="?view=analysis&pricing=1">Upgrade</a>
                </div>
            </div>
        </div>
        <div class="landing-wrap" style="grid-template-columns: 1fr; max-width: 860px; margin: 0 auto; padding: 0 24px;">
            <div class="landing-left" style="text-align:center; margin-bottom:12px;">
                <div class="landing-kicker" style="margin-left:auto; margin-right:auto;">Sign In</div>
                <h1 class="landing-title" style="margin-bottom:8px;">Access your RepoGuard workspace</h1>
                <p class="hero-sub" style="margin-bottom:8px; margin-left:auto; margin-right:auto;">Log in to run analyses, view history, and download reports.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.session_state["show_auth_modal"] = False
    st.markdown("<br>", unsafe_allow_html=True)
    spacer_l, form_col, spacer_r = st.columns([1.0, 1.0, 1.0])
    with form_col:
        show_auth_modal()


# ── Auth header bar ─────────────────────────────────────────────────────────
def render_auth_header() -> None:
    """Sticky auth bar shown at top of every page."""
    # Hide auth header controls on the standalone analysis view
    if st.session_state.get("current_view") == "analysis":
        return
    if not _AUTH_AVAILABLE:
        return
    user_email = st.session_state.get("user_email")
    user_plan  = st.session_state.get("user_plan", "free")

    if user_email:
        usage = get_usage_today(user_email)
        plan_cfg = get_plan(user_plan)
        token_lim = plan_cfg["token_limit"]
        token_used = usage["tokens_used"]
        analyses_done = usage["analyses_count"]
        analyses_lim  = plan_cfg["analyses_per_day"]
        pct = min(100, int(token_used / token_lim * 100)) if token_lim else 0
        plan_badge_color = "#7c3aed" if user_plan == "pro" else "#0ea5e9"

        st.markdown(
            f"""
            <div class="auth-header-bar">
              <span class="auth-user-email">👤 {user_email}</span>
              <span class="auth-plan-badge" style="background:{plan_badge_color}">{user_plan.upper()}</span>
              <span class="auth-token-info">🪙 {token_used:,} / {token_lim:,} tokens</span>
              <div class="auth-token-bar-wrap"><div class="auth-token-bar" style="width:{pct}%"></div></div>
              <span class="auth-analyses-info">📊 {analyses_done}/{analyses_lim} analyses today</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    try:
        params = st.query_params
    except Exception:
        params = {}

    # ── Handle logout ──────────────────────────────────────────────────────
    if "logout" in params:
        for k in ["jwt", "user_email", "user_plan"]:
            st.session_state[k] = None
        try:
            st.query_params.clear()
        except Exception:
            pass
        st.rerun()

    # ── Read token from URL (from React login redirect) ────────────────────
    token_in_url = (params.get("token", [None])[0]
                    if isinstance(params.get("token"), list)
                    else params.get("token"))
    if token_in_url:
        st.session_state["_post_token_ready"] = True

    # ── Pricing redirect ───────────────────────────────────────────────────
    pricing_param = (params.get("pricing", [""])[0]
                     if isinstance(params.get("pricing"), list)
                     else params.get("pricing", ""))
    if pricing_param:
        react_pricing = os.environ.get("REACT_PRICING_URL", "http://localhost:5173/pricing")
        st.markdown(
            f'''<meta http-equiv="refresh" content="0; url={react_pricing}">
<script>window.location.href="{react_pricing}";</script>
<div style="padding:16px">Redirecting to <a href="{react_pricing}">Upgrade</a>...</div>''',
            unsafe_allow_html=True,
        )
        return

    # ── Auth bootstrap ─────────────────────────────────────────────────────
    auth_session_bootstrap()
    try:
        handle_query_token()
    except Exception:
        pass

    inject_styles()

    react_login   = os.environ.get("REACT_LOGIN_URL",   "http://localhost:5173/login")
    react_pricing = os.environ.get("REACT_PRICING_URL", "http://localhost:5173/pricing")
    react_home    = os.environ.get("REACT_HOME_URL",    "http://localhost:5173")

    # ── Session State ──────────────────────────
    for key in ("analysis_result", "analysis_error", "pdf_report_bytes", "pdf_error"):
        if key not in st.session_state:
            st.session_state[key] = None
    if "analysis_running" not in st.session_state:
        st.session_state.analysis_running = False
    if "analysis_history" not in st.session_state:
        st.session_state.analysis_history = []

    # ── Top Navigation / Header ────────────────
    jwt_token = st.session_state.get("jwt") or ""
    react_pricing = os.environ.get('REACT_PRICING_URL', 'http://localhost:5173/pricing')
    upgrade_url = f"{react_pricing}?token={jwt_token}" if jwt_token else react_pricing
    react_home = react_pricing.replace("/pricing", "").replace("/login", "")

    is_pro = _is_pro_variant() or st.session_state.get("user_plan") == "pro"
    brand_text = 'RepoGuard <span class="brand-accent" style="color:#eab308">PRO</span><span class="pro-badge">EDITION</span>' if is_pro else 'RepoGuard <span class="brand-accent">AI</span>'

    st.markdown(
        textwrap.dedent(
            f"""
            <div class="top-nav">
                <div class="nav-left">
                    <div class="brand">{brand_text}</div>
                    <div class="nav-sub">AI-powered GitHub repository intelligence</div>
                </div>
                <div class="nav-right">
                    <a class="icon-btn" href="{react_home}" title="Home" style="margin-right: 8px;"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 6px;"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>Home</a>
                    <a class="icon-btn" href="{upgrade_url}" title="Upgrade">Upgrade</a>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    # ── Auth Header bar ────────────────────────────────────────────
    render_auth_header()

    # Show pricing section if flagged
    if st.session_state.get('show_pricing'):
        show_pricing_section()
        st.divider()

    # ── Input Panel ────────────────────────────
    st.markdown('<div class="input-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">Enter Repository URL</div>', unsafe_allow_html=True)
    col_url, col_btn = st.columns([6, 1])
    with col_url:
        repo_url = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/facebook/react",
            label_visibility="collapsed",
        )
    with col_btn:
        _user_email = st.session_state.get("user_email")
        # Allow anonymous analysis runs; only enforce limits for signed-in users
        _analyze_disabled = False
        analyze_clicked = st.button("Analyze", type="primary", use_container_width=True, disabled=_analyze_disabled)
    st.markdown("</div>", unsafe_allow_html=True)

    # Note: Analyze is available to anonymous users; sign in to track usage and access limits.

    # ── Usage Summary ─────────────────────────
    if _AUTH_AVAILABLE:
        _user_email = st.session_state.get("user_email")
        _user_plan = st.session_state.get("user_plan", "free")
        if _user_email:
            usage = get_usage_today(_user_email)
            tokens_left = tokens_remaining(_user_email, _user_plan)
            analyses_left = analyses_remaining(_user_email, _user_plan)
            from plans import plan_token_limit, plan_analyses_limit
            t_limit = plan_token_limit(_user_plan)
            a_limit = plan_analyses_limit(_user_plan)
            st.markdown(
                f"""
                <div class="usage-banner">
                    <div><b>Plan:</b> {_user_plan.upper()}</div>
                    <div><b>Tokens left today:</b> {tokens_left} / {t_limit}</div>
                    <div><b>Analyses left today:</b> {analyses_left} / {a_limit}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            if _is_pro_variant():
                st.success("Pro mode active on this URL. Sign in only if you want account-linked limits and usage history.")
            else:
                st.info("Sign in to see your daily token usage and limits.")

    # ── Run Analysis ───────────────────────────
    if analyze_clicked:
        if not repo_url.strip():
            st.warning("Please enter a GitHub repository URL.")
        else:
            # ── Auth gating (only enforce limits if user is signed in) ───────
            _user_email = st.session_state.get("user_email")
            _user_plan  = st.session_state.get("user_plan", "free")
            _blocked = False
            if _AUTH_AVAILABLE and _user_email:
                if not can_run_analysis(_user_email, _user_plan):
                    from plans import plan_analyses_limit, plan_token_limit
                    _alim = plan_analyses_limit(_user_plan)
                    _tlim = plan_token_limit(_user_plan)
                    st.warning(
                        f"⚠️ **Daily limit reached** — you have used all {_alim} analyses "
                        f"and {_tlim} tokens on the **{_user_plan.upper()}** plan today.\n\n"
                        "Upgrade to **Pro** for 30 analyses and 30 tokens per day."
                    )
                    st.session_state["show_pricing"] = True
                    _blocked = True

            if not _blocked:
                st.session_state.analysis_error = None
                st.session_state.pdf_report_bytes = None
                st.session_state.analysis_running = True
                try:
                    with st.spinner("Collecting GitHub data and running LLM tasks..."):
                        result = analyze_repository(repo_url.strip())
                        st.session_state.analysis_result = result
                        # ── Record token usage ─────────────────────────
                        if _AUTH_AVAILABLE and _user_email:
                            try:
                                # 1 token per analysis run
                                record_usage(_user_email, 1)
                            except Exception:
                                pass
                except AnalysisError as exc:
                    st.session_state.analysis_result = None
                    st.session_state.analysis_error = str(exc)
                except Exception as exc:
                    st.session_state.analysis_result = None
                    st.session_state.analysis_error = f"Unexpected error: {exc}"
                finally:
                    st.session_state.analysis_running = False

    analysis_result = st.session_state.analysis_result
    analysis_error = st.session_state.analysis_error

    # ── Progress Steps (visual only when analysis running) ──
    if st.session_state.get("analysis_running"):
        st.markdown(
            """
            <div class="progress-wrap">
              <div class="progress-step active">1. Fetching repository data</div>
              <div class="progress-step">2. Analyzing contributors</div>
              <div class="progress-step">3. Evaluating technical debt</div>
              <div class="progress-step">4. Running AI risk analysis</div>
              <div class="progress-step">5. Generating insights</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if analysis_error:
        st.error(f"Error: {analysis_error}")

    # ── Defaults ───────────────────────────────
    meta_provider = "—"
    meta_model = "—"
    runtime_text = "No run yet"
    metric_subtext = "Awaiting analysis"
    summary = {"health_score": "--", "bus_factor_percent": "--", "technical_debt_hours": "--", "security_score": "--"}

    chart_specs = [
        ("radar",           "Repository Radar"),
        ("network",         "Contributor Network"),
        ("language_pie",    "Language Distribution"),
        ("security_matrix", "Security Risk Matrix"),
        ("dependency_risk", "Dependency Risk"),
    ]
    chart_map = {key: placeholder_figure(title) for key, title in chart_specs}
    built_charts = None
    priorities: list = []

    # ── Populate from result ───────────────────
    if analysis_result:
        payload = analysis_result.get("summary", {})
        ai_meta = analysis_result.get("ai_analysis", {}).get("meta", {})
        meta_provider = str(ai_meta.get("provider", "—")).upper()
        meta_model = str(ai_meta.get("model", "—"))
        used_fallback = bool(ai_meta.get("used_fallback", False))
        fallback_count = int(ai_meta.get("fallback_count", 0)) if isinstance(ai_meta.get("fallback_count"), int) else 0
        failed_tasks = ai_meta.get("failed_tasks", {}) if isinstance(ai_meta.get("failed_tasks"), dict) else {}

        summary = {
            "health_score":          payload.get("health_score", "--"),
            "bus_factor_percent":    payload.get("bus_factor_percent", "--"),
            "technical_debt_hours":  payload.get("technical_debt_hours", "--"),
            "security_score":        payload.get("security_score", "--"),
        }

        priorities = payload.get("top_5_refactoring_priorities", [])

        runtime_ms = analysis_result.get("runtime", {}).get("total_elapsed_ms")
        if runtime_ms is not None:
            runtime_text = f"{runtime_ms:,} ms"

        if used_fallback:
            metric_subtext = "Estimated (AI rate limited)"
            st.info("\u26a1 AI is currently rate-limited \u2014 showing intelligent estimates based on your repository data. All key metrics are still computed accurately.")
        else:
            metric_subtext = "Live AI - LLaMA 3.3 70B"
            st.success(f"Analysis complete in {runtime_text}")

        repo_name = analysis_result.get("repository_data", {}).get("full_name", "Repository")
        history_entry = {
            "repo_name": repo_name,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "health_score": summary.get("health_score", "--"),
            "security_score": summary.get("security_score", "--"),
            "technical_debt_hours": summary.get("technical_debt_hours", "--"),
        }
        if not st.session_state.analysis_history or st.session_state.analysis_history[0].get("repo_name") != repo_name:
            st.session_state.analysis_history.insert(0, history_entry)

        try:
            built_charts = build_all_charts(analysis_result)
            for key, _ in chart_specs:
                if key in built_charts:
                    chart_map[key] = built_charts[key]
        except Exception as exc:
            st.info(f"Chart engine note: {exc}")

        if st.session_state.pdf_report_bytes is None:
            try:
                st.session_state.pdf_report_bytes = generate_pdf_bytes(analysis_result, built_charts)
            except Exception as exc:
                st.session_state.pdf_error = f"PDF generation failed: {exc}"

    # ── Status Bar ─────────────────────────────
    dot = f'<span class="status-dot"></span>' if analysis_result else ""
    st.markdown(
        f"""
        <div class="status-bar">
            <span class="status-chip">{dot} Provider: <b style="color:#e8f8ff">{meta_provider}</b></span>
            <span class="status-chip">Model: <b style="color:#e8f8ff">{meta_model}</b></span>
            <span class="status-chip">Runtime: <b style="color:#e8f8ff">{runtime_text}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Core Metrics ───────────────────────────
    section_header("📊", "Core Repository Metrics")
    show_metric_cards(summary, metric_subtext)

    # ── AI Insights (only after analysis) ──────
    if analysis_result:
        with st.expander("AI Insights", expanded=False):
            show_insight_boxes(analysis_result)

    # ── Visualizations (Tabbed) ─────────────────
    section_header("📈", "Analysis Visualizations")

    tab_labels = [title for _, title in chart_specs]
    tabs = st.tabs(tab_labels)
    for i, ((key, _), tab) in enumerate(zip(chart_specs, tabs)):
        with tab:
            st.markdown(
                f"""
                <div class="chart-shell">
                  <div class="chart-head">
                    <div class="chart-kicker">Visualization</div>
                    <div class="chart-title">{tab_labels[i]}</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.plotly_chart(
                chart_map.get(key, placeholder_figure(tab_labels[i])),
                use_container_width=True,
                config={"responsive": True, "displayModeBar": False},
            )

    # ── Repository Tree ─────────────────────────
    section_header("🗂️", "Repository Tree")
    repo_data = analysis_result.get("repository_data", {}) if analysis_result else {}
    repo_tree = repo_data.get("repo_tree", {"name": "/", "type": "dir", "children": {}})
    root_label = repo_data.get("full_name", "Repository")
    tree_html = _repo_tree_html(repo_tree, root_label)
    if not tree_html:
        tree_html = '<div class="tree-file">No tree data available yet. Run analysis to load it.</div>'
    st.markdown(f"<div class=\"repo-tree\">{tree_html}</div>", unsafe_allow_html=True)

    # ── Branches ────────────────────────────────
    section_header("🌿", "Branches")
    branches = repo_data.get("branches", [])
    branches_html = _branches_html(branches)
    if not branches_html:
        branches_html = '<div class="branch-item">No branch data available yet. Run analysis to load it.</div>'
    st.markdown(f"<div class=\"branch-list\">{branches_html}</div>", unsafe_allow_html=True)

    # ── Refactoring Priorities ─────────────────
    section_header("🔧", "Top Refactoring Priorities")
    show_priorities_table(priorities)

    # ── Project Intelligence Summary (expanded detailed repo summary) ──
    def show_project_intelligence(result: dict) -> None:
        repo = result.get("repository_data", {}) if result else {}
        ai = result.get("ai_analysis", {}) if result else {}
        ai_summary = ai.get("project_summary", {}) if isinstance(ai.get("project_summary", {}), dict) else {}

        name = repo.get("full_name", "Repository")
        short = ai_summary.get("short") or repo.get("description") or "A concise repository summary is not available."
        long_desc = ai_summary.get("detailed", "") or ai.get("repository_overview", "")

        languages = repo.get("languages") or {}
        lang_list = ", ".join(list(languages.keys())[:6]) if isinstance(languages, dict) and languages else "—"

        key_features = ai_summary.get("key_features") or ai.get("key_features") or [
            "Health, security, and bus-factor scoring",
            "Top refactoring priorities and effort estimates",
            "Dependency risk and vulnerability highlights",
        ]

        tech_stack = []
        if isinstance(languages, dict):
            tech_stack = [k for k in languages.keys()][:6]
        deps = repo.get("dependencies") or []
        patterns = ai_summary.get("patterns") or ai.get("patterns") or []
        api_overview = ai_summary.get("api_overview") or "No API overview generated from AI for this repository."
        endpoints = repo.get("api_endpoints") or []

        # Render HTML block resembling the project intelligence card
        features_html = "".join(f"<li class=\"pi-feat\">{f}</li>" for f in key_features)
        patterns_html = "".join(f"<span class=\"pi-pattern\">{p}</span>" for p in patterns[:6]) if patterns else "<em>No patterns detected</em>"
        tech_html = "".join(f"<span class=\"pi-tech\">{t}</span>" for t in tech_stack) if tech_stack else "—"

        st.markdown(
            f"""
            <div class="project-intel">
                <div class="pi-header">
                    <div class="pi-title">{name}</div>
                    <div class="pi-kicker">PROJECT INTELLIGENCE</div>
                </div>
                <div class="pi-grid">
                    <div class="pi-left">
                        <h3>What it does</h3>
                        <p>{short}</p>
                        <h3>Key Features</h3>
                        <ul class="pi-features">{features_html}</ul>
                    </div>
                    <div class="pi-right">
                        <h3>How it works</h3>
                        <p>{long_desc or 'The analysis synthesizes repository metadata, commit history, dependency manifests, and AI models to produce actionable signals.'}</p>
                        <h3>API Overview</h3>
                        <p>{api_overview}</p>
                        <h3>Tech Stack</h3>
                        <div class="pi-tech-list">{tech_html}</div>
                        <h3>Patterns</h3>
                        <div class="pi-patterns">{patterns_html}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### API Endpoints in Repository")
        if endpoints:
            endpoint_rows = [
                {
                    "Method": str(e.get("method", "ANY")),
                    "Path": str(e.get("path", "")),
                    "File": str(e.get("file", "")),
                    "Line": int(e.get("line", 0)) if str(e.get("line", "")).isdigit() else e.get("line", ""),
                }
                for e in endpoints[:60]
                if isinstance(e, dict)
            ]
            if endpoint_rows:
                st.dataframe(endpoint_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No API endpoints detected in scanned files for this repository.")
        else:
            st.info("No API endpoints detected in scanned files for this repository.")

    if analysis_result:
        section_header("🧠", "Project Intelligence")
        show_project_intelligence(analysis_result)

    # ── PDF Download ───────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    pdf_col, _ = st.columns([2, 5])
    with pdf_col:
        if st.session_state.pdf_error:
            st.warning(st.session_state.pdf_error)
        pdf_data = st.session_state.pdf_report_bytes if st.session_state.pdf_report_bytes is not None else b""
        st.download_button(
            label="Download PDF Report",
            data=pdf_data,
            file_name="repogard_health_report.pdf",
            mime="application/pdf",
            disabled=st.session_state.pdf_report_bytes is None,
            use_container_width=True,
        )

    # ── Footer ─────────────────────────────────
    st.markdown(
        """
        <div class="footer">
            Built using Streamlit · Groq API · GitHub API<br>
            RepoGuard - Repository Intelligence Platform
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
