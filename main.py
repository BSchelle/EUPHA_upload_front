from __future__ import annotations

import base64
from typing import Optional
import re
import io
import fitz  # PyMuPDF
import streamlit as st
import pdfplumber


def load_svg_as_data_uri(svg_path: str) -> Optional[str]:
    """Return a data URI for an SVG file, or None if not found."""
    try:
        with open(svg_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64}"
    except FileNotFoundError:
        return None


def extract_doi_from_pdf(text: str) -> Optional[str]:
    """Extract DOI from PDF text using regex pattern."""
    # Pattern for DOI: 10.xxxx/xxxxx
    doi_pattern = r'(?:https?://)?(?:www\.)?(?:dx\.)?doi\.org/|(?:doi:)\s*(?=10\.)|(10\.\S+/\S+)'
    match = re.search(r'(?:doi[:\s]+)?(?:https?://)?(?:dx\.)?doi\.org/(10\.\S+)', text, re.IGNORECASE)
    if match:
        return match.group(1) if match.group(1).startswith('10.') else match.group(0)
    
    # Alternative pattern
    match = re.search(r'10\.\d{4,}/\S+', text)
    if match:
        return match.group(0)
    return None


def extract_abstract_from_pdf(text: str) -> Optional[str]:
    """Extract abstract from PDF text."""
    # Look for "Abstract" section
    abstract_pattern = r'(?:abstract|summary)\s*[:]*\s*(.+?)(?=(?:introduction|keywords|1\.\s|methods|methodology|introduction|related work|background)|\Z)'
    match = re.search(abstract_pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        abstract_text = match.group(1).strip()
        # Clean up and limit to reasonable length
        abstract_text = re.sub(r'\s+', ' ', abstract_text)[:500]
        return abstract_text if len(abstract_text) > 20 else None
    return None


def extract_authors_from_pdf(text: str) -> list[dict]:
    """Extract authors by finding the typical author line in scientific papers."""
    authors = []

    def clean_name(name: str) -> str:
        # Supprime chiffres, *, †, § collés au nom
        return re.sub(r'[\d\*†‡§]+', '', name).strip()

    lines = text.split('\n')[:50]

    for line in lines:
        line = line.strip()

        # Une ligne d'auteurs contient typiquement "and" ou une virgule
        # et ressemble à des noms propres (Majuscule, pas trop longue)
        if len(line) > 150 or len(line) < 5:
            continue
        if not re.search(r'\band\b|,', line):
            continue
        # Doit commencer par une majuscule
        if not re.match(r'^[A-Z]', line):
            continue
        # Ne doit pas contenir de mots typiques de non-auteurs
        skip_words = ['abstract', 'keywords', 'introduction', 'figure', 
                      'table', 'doi', 'http', 'university', 'institute',
                      'open access', 'copyright', 'license', 'received']
        if any(w in line.lower() for w in skip_words):
            continue
        # Tous les "mots" (après nettoyage) doivent ressembler à des noms propres
        # càd commencer par une majuscule ou être un chiffre/symbole
        test_line = clean_name(line)
        words = [w for w in re.split(r'[\s,]+', test_line) if w]
        if not words:
            continue
        # Au moins 80% des mots doivent commencer par une majuscule
        capitalized = sum(1 for w in words if re.match(r'^[A-Z]', w) or w.lower() == 'and')
        if capitalized / len(words) < 0.8:
            continue

        # C'est probablement une ligne d'auteurs — on parse
        raw_names = re.split(r',\s*|\s+and\s+', line)
        for raw in raw_names:
            name = clean_name(raw).strip()
            if not name or len(name) < 3:
                continue
            parts = name.split()
            if len(parts) >= 2:
                authors.append({
                    "name": " ".join(parts[:-1]),
                    "surname": parts[-1],
                    "email": ""
                })

    # Rattache l'email du corresponding author
    corr_match = re.search(
        r'\*Correspondence[:\s]+([A-Z][a-z]+(?:[\s\-][A-Za-z\-]+)+)\s+([\w.\-]+@[\w.\-]+\.\w+)',
        text
    )
    if corr_match and authors:
        corr_name = re.sub(r'[\d\*†‡§]+', '', corr_match.group(1)).strip()
        corr_email = corr_match.group(2)
        for author in authors:
            full = f"{author['name']} {author['surname']}"
            if corr_name in full or full in corr_name:
                author['email'] = corr_email

    return authors[:10]

def extract_text_by_blocks(uploaded_file_bytes) -> str:
    doc = fitz.open(stream=uploaded_file_bytes, filetype="pdf")
    full_text = ""
    for page in doc[:3]:
        # Trie les blocs par position verticale puis horizontale
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: (round(b[1] / 20), b[0]))  # y groupé, puis x
        for block in blocks:
            full_text += block[4] + "\n"
    return full_text
def extract_pdf_metadata(uploaded_file) -> dict:
    """Extract metadata from PDF file."""
    metadata = {
        "doi": None,
        "abstract": None,
        "authors": []
    }
    
    try:
        # Extract text from PDF
        pdf_text = extract_text_by_blocks(uploaded_file.read())

        st.write(pdf_text)
        # Extract metadata
        metadata["doi"] = extract_doi_from_pdf(pdf_text)
        metadata["abstract"] = extract_abstract_from_pdf(pdf_text)
        metadata["authors"] = extract_authors_from_pdf(pdf_text)
        
    except Exception as e:
        st.warning(f"Could not extract metadata from PDF: {str(e)}")
    
    return metadata


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

    # Session init
    if "auteurs" not in st.session_state:
        st.session_state.auteurs = []

    st.session_state.setdefault("extracted_metadata", None)
    st.session_state.setdefault("pdf_file", None)
    st.session_state.setdefault("meta_edit_doi", "")
    st.session_state.setdefault("meta_edit_abstract", "")
    st.session_state.setdefault("meta_is_correct", False)
    st.session_state.setdefault("authors_is_correct", False)

    def add_author():
        st.session_state.auteurs.append({"surname": "", "name": "", "email": ""})

    def remove_author(index: int):
        if index < len(st.session_state.auteurs):
            st.session_state.auteurs.pop(index)

    # Sidebar
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
            "2) Validate DOI + abstract\n"
            "3) Validate authors\n"
            "4) Click **Upload file**"
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

    # Upload section
    uploaded_file = st.file_uploader(
        label="Please drop your article here ! (Please make sure it's a PDF file!)",
        type="pdf",
        help=(
            "The maximum file size is set by the server.maxUploadSize configuration option "
            "in your config.toml file."
        ),
    )

    if not uploaded_file:
        st.info("Upload a PDF to continue.")
        return

    # Extract metadata from PDF if it's a new file
    if uploaded_file.name != st.session_state.pdf_file:
        st.session_state.pdf_file = uploaded_file.name
        st.session_state.meta_is_correct = False
        st.session_state.authors_is_correct = False
        st.session_state.meta_edit_doi = ""
        st.session_state.meta_edit_abstract = ""
        st.session_state.auteurs = []
        
        with st.spinner("Extracting metadata from PDF..."):
            st.session_state.extracted_metadata = extract_pdf_metadata(uploaded_file)
        
        # Initialize with extracted data
        extracted_doi = st.session_state.extracted_metadata.get("doi")
        extracted_abstract = st.session_state.extracted_metadata.get("abstract")
        extracted_authors = st.session_state.extracted_metadata.get("authors", [])
        
        if extracted_doi:
            st.session_state.meta_edit_doi = extracted_doi
        if extracted_abstract:
            st.session_state.meta_edit_abstract = extracted_abstract
        if extracted_authors:
            st.session_state.auteurs = extracted_authors
        
        st.success("Metadata extracted from PDF! ✨")

    st.success(f"{uploaded_file.name} have been submitted to our database!")
    st.write("##### Please share some key informations about the article with us!")

    # Metadata section
    st.write("")
    st.header("General informations")

    extracted_doi = st.session_state.extracted_metadata.get("doi") if st.session_state.extracted_metadata else None
    extracted_abstract = st.session_state.extracted_metadata.get("abstract") if st.session_state.extracted_metadata else None

    col_doi, col_status = st.columns([3, 1])
    with col_doi:
        st.text_input(
            "Please share DOI", 
            value=st.session_state.meta_edit_doi,
            key="meta_doi_input",
            disabled=st.session_state.meta_is_correct,
            on_change=lambda: setattr(st.session_state, 'meta_edit_doi', st.session_state.meta_doi_input),
            placeholder="ex: 10.1038/s41586-021-00000-x"
        )
        if extracted_doi:
            st.caption(f"✨ Extracted from PDF: {extracted_doi}")
    
    with col_status:
        if st.session_state.meta_is_correct:
            st.success("✓ Locked")
        else:
            st.info("Editable")

    st.text_area(
        "Please share your abstract", 
        value=st.session_state.meta_edit_abstract,
        key="meta_abstract_input",
        height=150,
        disabled=st.session_state.meta_is_correct,
        on_change=lambda: setattr(st.session_state, 'meta_edit_abstract', st.session_state.meta_abstract_input),
        placeholder="Lorem ipsum dolor sit amet"
    )
    if extracted_abstract:
        st.caption("✨ Extracted from PDF (may be truncated)")

    st.write("")
    
    col_check, col_space = st.columns([2, 3])
    with col_check:
        st.checkbox(
            "This information is correct",
            value=st.session_state.meta_is_correct,
            key="meta_is_correct",
            help="Check this box to lock the fields and confirm the data is correct"
        )
    
    if st.session_state.meta_is_correct:
        st.success("✓ Metadata validated and locked.")
    else:
        st.info("💡 You can still edit the fields above.")

    # Authors section
    st.write("")
    st.header("Authors")

    if len(st.session_state.auteurs) == 0:
        st.info("No authors found. Click the button below to add one.")
    #afficher la liste bruts des auteurs extraits du pdf
    
    st.write(st.session_state.auteurs)
    for i in range(len(st.session_state.auteurs)):
        with st.expander(f"Author n°{i+1}", expanded=True):
            col_delete, col_info = st.columns([1, 4])
            
            with col_delete:
                if not st.session_state.authors_is_correct:
                    if st.button("Remove", key=f"remove_author_{i}"):
                        remove_author(i)
                        st.rerun()
            
            # with col_info:
            #     if st.session_state.auteurs[i].get("name") or st.session_state.auteurs[i].get("surname"):
            #         st.caption(f"Name: {st.session_state.auteurs[i].get('name', '')} | Surname: {st.session_state.auteurs[i].get('surname', '')}")
            
            c1, c2 = st.columns(2)
            with c1:
                name_val = st.text_input(
                    "Name", 
                    value=st.session_state.auteurs[i].get("name", ""),
                    key=f"name_{i}",
                    disabled=st.session_state.authors_is_correct
                )
                st.session_state.auteurs[i]["name"] = name_val
            
            with c2:
                surname_val = st.text_input(
                    "Surname", 
                    value=st.session_state.auteurs[i].get("surname", ""),
                    key=f"surname_{i}",
                    disabled=st.session_state.authors_is_correct
                )
                st.session_state.auteurs[i]["surname"] = surname_val

            is_corr = st.checkbox(
                "Is corresponding author ?", 
                key=f"corr_{i}",
                disabled=st.session_state.authors_is_correct
            )
            if is_corr:
                email_val = st.text_input(
                    "Corresponding author e-mail", 
                    value=st.session_state.auteurs[i].get("email", ""),
                    key=f"email_{i}",
                    disabled=st.session_state.authors_is_correct,
                    placeholder='institutional@mail.edu'
                )
                st.session_state.auteurs[i]["email"] = email_val

    st.write("")
    
    if not st.session_state.authors_is_correct:
        if st.button("➕ Add an author", on_click=add_author):
            pass

    st.write("")
    col_check_auth, col_space_auth = st.columns([2, 3])
    
    with col_check_auth:
        st.checkbox(
            "Authors information is correct",
            value=st.session_state.authors_is_correct,
            key="authors_is_correct",
            help="Check this box to lock the authors list and confirm the data is correct"
        )
    
    if st.session_state.authors_is_correct:
        st.success(f"✓ {len(st.session_state.auteurs)} author(s) validated and locked.")
    else:
        st.info("💡 You can still edit, add, or remove authors.")

    st.divider()

    # Upload metadatas section
    if st.button("Upload file", type="primary"):
        if not st.session_state.meta_is_correct:
            st.error("❌ Please validate the metadata (DOI and abstract) before uploading.")
        elif not st.session_state.authors_is_correct:
            st.error("❌ Please validate the authors list before uploading.")
        elif len(st.session_state.auteurs) == 0:
            st.error("❌ Please add at least one author before uploading.")
        else:
            # Build final JSON
            authors_dict = {}
            for j, author in enumerate(st.session_state.auteurs):
                authors_dict[f"author_{j+1}"] = {
                    "name": author.get("name", ""),
                    "surname": author.get("surname", ""),
                    "email": author.get("email") or None,
                }

            final_json = {
                "doi": st.session_state.meta_edit_doi,
                "abstract": st.session_state.meta_edit_abstract,
                "authors": authors_dict
            }

            st.success("Successfully contributed, thank you!")
            st.json(final_json)


if __name__ == "__main__":
    main()
