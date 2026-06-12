import streamlit as st

from ui_shared import inject_styles
import os


st.set_page_config(page_title="RepoGuard AI - Landing", layout="wide")


def main() -> None:
    inject_styles()

  # If query param requests login, redirect to React login SPA
  try:
    params = st.query_params
    view = params.get("view", [None])[0] if isinstance(params.get("view"), list) else params.get("view")
    if view == "login":
      react_login = os.environ.get("REACT_LOGIN_URL", "http://localhost:5175/login")
      st.markdown(
        f"""
        <meta http-equiv="refresh" content="0; url={react_login}">
        <script>window.location.href="{react_login}";</script>
        <div style="padding:16px">Redirecting to <a href="{react_login}">React login</a>...</div>
        """,
        unsafe_allow_html=True,
      )
      return
  except Exception:
    pass

    st.markdown(
        """
        <div class="landing-wrap">
          <div class="landing-left">
            <div class="landing-kicker">RepoGuard AI</div>
            <h1 class="landing-title">Analyze repository health and risk to make faster engineering decisions.</h1>
            <div class="landing-points">
              <div class="landing-point">Extract actionable repository insights from commits, contributors, dependencies, and code quality signals.</div>
              <div class="landing-point">Reduce blind spots with evidence-based health, security, and bus-factor scoring.</div>
              <div class="landing-point">Get dashboard visuals and PDF-ready output for team reviews and leadership reporting.</div>
            </div>
            <div style="display:flex;gap:12px;justify-content:center;">
              <a class="landing-cta" href="http://localhost:5175/login" target="_self">🔐 Log In</a>
              <a class="landing-cta" href="http://localhost:5175/pricing" target="_self">💎 Pricing</a>
              <a class="landing-cta" href="http://localhost:8514/" target="_self">Get Started</a>
            </div>
          </div>

          <div class="landing-right">
            <div class="pdf-preview-card">
              <div class="pdf-badge">PDF</div>
              <div class="pdf-header-row">
                <span>section</span><span>status</span><span>owner</span><span>risk</span>
              </div>
              <div class="pdf-row"><span>Security</span><span>Open</span><span>Platform</span><span>High</span></div>
              <div class="pdf-row"><span>Tech Debt</span><span>Review</span><span>Core</span><span>Medium</span></div>
              <div class="pdf-row"><span>Bus Factor</span><span>Flagged</span><span>Infra</span><span>High</span></div>
              <div class="pdf-row"><span>PR Flow</span><span>Stable</span><span>App</span><span>Low</span></div>
            </div>

            <div class="score-card-mock">
              <div class="score-title">Repository Score Container</div>
              <div class="score-grid">
                <div><b>84%</b><span>Health</span></div>
                <div><b>72%</b><span>Security</span></div>
                <div><b>38h</b><span>Debt</span></div>
                <div><b>61%</b><span>Bus Factor</span></div>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
