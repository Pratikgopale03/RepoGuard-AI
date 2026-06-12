import streamlit as st


def inject_styles() -> None:
    with open("styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def section_header(title: str) -> None:
    html = f'<div class="sec-header"><span class="sec-title">{title}</span><div class="sec-line"></div></div>'
    st.markdown(html, unsafe_allow_html=True)
