# app.py
from __future__ import annotations

import base64
from typing import Optional

import streamlit as st


def load_svg_as_data_uri(svg_path: str) -> Optional[str]:
    """Return a data URI for an SVG file, or None if not found."""
    try:
        with open(svg_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64}"
    except FileNotFoundError:
        return None


def set_modern_css() -> None:
    st.markdown(
        """
        <style>
          .block-container { padding-top: 1.2rem; padding-bottom: 2.2rem; max-width: 1050px; }

          .card {
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(0,0,0,0.06);
            border-radius: 16px;
            padding: 16px 16px;
            box-shadow: 0 10px 26px rgba(0,0,0,0.06);
          }

          .sidebar-logo { margin-top: 8px; margin-bottom: 6px; display:block; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    # Page config must be first
    st.set_page_config(page_title="EU Fact Force uploading hub", page_icon="📄", layout="wide")
    set_modern_css()

    # -----------------------------
    # Session init
    # -----------------------------
    if "auteurs" not in st.session_state:
        st.session_state.auteurs = [{"surname": "", "name": "", "email": ""}]

    st.session_state.setdefault("meta_confirmed", False)
    st.session_state.setdefault("authors_confirmed", False)
    st.session_state.setdefault("meta_manual", False)
    st.session_state.setdefault("authors_manual", False)

    def add_author():
        st.session_state.auteurs.append({"surname": "", "name": "", "email": ""})

    # -----------------------------
    # Sidebar
    # -----------------------------
    with st.sidebar:
        
        logo_uri = load_svg_as_data_uri("eupha-logo.svg")
        if logo_uri:
            st.markdown(
                f'<img class="sidebar-logo" src="{logo_uri}" style="width: 100%; max-width: 220px; height:auto;">',
                unsafe_allow_html=True,
            )
        st.markdown("### EU Fact Force")
        st.markdown("---")
        st.markdown("**How it works**")
        st.markdown(
            "1) Upload a PDF\n"
            "2) Add DOI + abstract\n"
            "3) Declare authors\n"
            "4) Click **Upload metadatas**"
        )


    st.title("EU Fact Force - Article uploading page")
    st.write("## Welcome to EU Fact Force articles uploading pages")
    st.write("")
    st.write(
        "##### Thank you for collaborating with us, you will find here a page where you can"
        " upload and declare authors of your papers in attempt to build a safer and healthier community! "
        "Thank you for your contribution!"
    )

    st.write("")
    st.title("Upload & Metadatas")

    # -----------------------------
    # Upload
    # -----------------------------

    uploaded_file = st.file_uploader(
        label="Please drop your article here ! (Please make sure it's a PDF file!)",
        type="pdf",
        help=(
            "The maximum file size is set by the server.maxUploadSize configuration option "
            "in your config.toml file."
        ),
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if not uploaded_file:
        st.info("Upload a PDF to continue.")
        return

    st.success(f"{uploaded_file.name} have been submitted to our database!", icon="✅")
    st.write("##### Please share some key informations about the article with us!")

    # -----------------------------
    # Metadata section
    # -----------------------------
    st.write("")
    
    st.header("General informations")

    col_doi, _ = st.columns([2, 1])
    with col_doi:
        doi = st.text_input("Please share DOI", placeholder="ex: 10.1038/s41586-021-00000-x")

    abstract = st.text_area("Please share your abstract", height=150, placeholder="Lorem ipsum dolor sit amet")

    st.write("")
    c1, c2 = st.columns([1, 1])

    with c1:
        if st.button("✅ Information is correct", key="meta_ok"):
            st.session_state.meta_confirmed = True
            st.session_state.meta_manual = False

    with c2:
        if st.button("✍️ Please fill manually", key="meta_manual_btn"):
            st.session_state.meta_manual = True
            st.session_state.meta_confirmed = False

    if st.session_state.meta_confirmed:
        st.success("Metadata confirmed by reviewer.")
    elif st.session_state.meta_manual:
        st.warning("Please fill metadata manually (reviewer flagged it as not correct).")

    st.markdown("</div>", unsafe_allow_html=True)

    # -----------------------------
    # Authors section
    # -----------------------------
    st.write("")
   
    st.header("Authors")

    for i in range(len(st.session_state.auteurs)):
        with st.expander(f"Author n°{i+1}", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Name", key=f"name_{i}")
            with c2:
                st.text_input("Surname", key=f"surname_{i}")

            st.text_input(
                "Author e-mail (optional)",
                key=f"email_{i}",
                placeholder="name@institution.edu",
            )

    st.button("➕ Add an author", on_click=add_author)

    st.write("")
    c3, c4 = st.columns([1, 1])

    with c3:
        if st.button("✅ Information is correct", key="authors_ok"):
            st.session_state.authors_confirmed = True
            st.session_state.authors_manual = False

    with c4:
        if st.button("✍️ Please fill manually", key="authors_manual_btn"):
            st.session_state.authors_manual = True
            st.session_state.authors_confirmed = False

    if st.session_state.authors_confirmed:
        st.success("Authors confirmed by reviewer.")
    elif st.session_state.authors_manual:
        st.warning("Please fill authors manually (reviewer flagged it as not correct).")

    st.divider()

    # -----------------------------
    # Upload metadatas
    # -----------------------------
    if st.button("🚀 Upload metadatas", type="primary"):
        authors_dict = {}
        for j in range(len(st.session_state.auteurs)):
            authors_dict[f"author_{j+1}"] = {
                "name": st.session_state.get(f"name_{j}"),
                "surname": st.session_state.get(f"surname_{j}"),
                "email": st.session_state.get(f"email_{j}") or None,
            }



        st.success("Successfuly contributed, thank you !")




if __name__ == "__main__":
    main()