import streamlit as st

from ui_shared import inject_styles, section_header


st.set_page_config(page_title="RepoGuard AI - Settings", layout="wide")


def main() -> None:
    inject_styles()
    section_header("Settings")

    st.markdown("<div class='settings-grid'>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="settings-card">
            <div class="settings-title">AI Provider</div>
            <div class="settings-sub">Choose default model and provider.</div>
        </div>
        <div class="settings-card">
            <div class="settings-title">Report Branding</div>
            <div class="settings-sub">Logo, footer text, and report metadata.</div>
        </div>
        <div class="settings-card">
            <div class="settings-title">Risk Thresholds</div>
            <div class="settings-sub">Configure score thresholds for alerts.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='settings-form'>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.selectbox("Default provider", ["Groq", "OpenAI", "Grok"], index=0)
        st.selectbox("Default model", ["llama-3.3-70b", "gpt-4o", "grok-beta"], index=0)
    with col2:
        st.slider("Minimum health score warning", 0, 100, 60)
        st.slider("Security risk threshold", 0, 100, 70)
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
