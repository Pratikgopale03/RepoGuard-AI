import streamlit as st

from ui_shared import inject_styles, section_header


st.set_page_config(page_title="RepoGuard AI - About", layout="wide")


def main() -> None:
    inject_styles()
    section_header("About RepoGuard AI")

    st.markdown(
        """
        <div class="about-card">
            <div class="about-title">Repository Intelligence for Engineering Teams</div>
            <div class="about-body">
                RepoGuard AI delivers code health, contributor resilience, technical debt, and security
                diagnostics in a single developer-centric dashboard. Use it to monitor repository risk
                and generate executive-ready reports.
            </div>
        </div>
        <div class="about-grid">
            <div class="about-feature">
                <div class="about-feature-title">Audit-ready reporting</div>
                <div class="about-feature-body">Export structured PDF reports for leadership reviews.</div>
            </div>
            <div class="about-feature">
                <div class="about-feature-title">Operational visibility</div>
                <div class="about-feature-body">Track contributor concentration and backlog health.</div>
            </div>
            <div class="about-feature">
                <div class="about-feature-title">Actionable insights</div>
                <div class="about-feature-body">Translate metrics into refactoring priorities.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
