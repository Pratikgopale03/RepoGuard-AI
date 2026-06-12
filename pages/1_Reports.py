import streamlit as st

from ui_shared import inject_styles, section_header


st.set_page_config(page_title="RepoGuard AI - Reports", layout="wide")


def main() -> None:
    inject_styles()
    section_header("Reports")

    history = st.session_state.get("analysis_history", [])
    if not history:
        st.info("No reports generated yet. Run an analysis to populate reports.")
        return

    st.markdown('<div class="report-grid">', unsafe_allow_html=True)
    for item in history[:12]:
        st.markdown(
            f"""
            <div class="report-card">
                <div class="report-title">{item.get('repo_name', 'Repository')}</div>
                <div class="report-meta">{item.get('timestamp', '')}</div>
                <div class="report-metrics">
                    <div><span>Health</span><b>{item.get('health_score', '--')}%</b></div>
                    <div><span>Security</span><b>{item.get('security_score', '--')}%</b></div>
                    <div><span>Debt</span><b>{item.get('technical_debt_hours', '--')}h</b></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
