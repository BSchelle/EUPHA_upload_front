import streamlit as st
import pandas as pd
import numpy as np

def main():

    #Initialisation de la session

    if "auteurs" not in st.session_state:
        st.session_state.auteurs = [{"surname": "", "name": "", "is_corresponding": False, "email": ""}]

    def add_author():
        st.session_state.auteurs.append({"surname": "", "name": "", "is_corresponding": False, "email": ""})

    #Header & welcome note
    st.set_page_config(page_title="EU Fact Force uploading hub")

    st.title('EU Fact Force - Article uploading page')

    st.write("## Welcome to EU Fact Force articles uploading pages")

    st.space("medium")

    st.write("##### Thank you for collaborating with us, you will find here a page where you can\
        upload and declare authors of your papers in attempt to build a safer and healthier community! \
        Thank you for your contribution!")

    st.title("Upload & Metadatas")

    uploaded_file = st.file_uploader(label='Please drop your article here ! (Please make sure it\'s a PDF file!)',
                     max_upload_size=10, type="pdf") #the maximum file size is set by the server.maxUploadSize
                                            #configuration option in your config.toml file. If this is an integer,
                                            # it must be positive and will override the server.maxUploadSize
                                            # configuration option.

    if uploaded_file:

        st.success(f'{uploaded_file.name} have been submitted to our database!', icon="✅")

        st.write('## Please share some key informations about the article with us!')

        st.header("General informations")

        col_doi, col_empty = st.columns([2, 1])

        with col_doi:
            doi = st.text_input("Please share DOI", placeholder="ex: 10.1038/s41586-021-00000-x")

        abstract = st.text_area("Please share your abstract", height=150, placeholder="Lorem ipsum dolor sit amet")

        st.header("Authors")

        for i in range(len(st.session_state.auteurs)):
            with st.expander(f"Author n°{i+1}", expanded=True):
                c1, c2 = st.columns(2)
                with c1:
                    st.text_input("Name", key=f"name_{i}")
                with c2:
                    st.text_input("Surname", key=f"surname_{i}")

                is_corr = st.checkbox("Is corresponding author ?", key=f"corr_{i}")
                if is_corr:
                    st.text_input("Corresponding author e-mail", key=f"email_{i}", placeholder='instutional@mail.edu')

        st.button("➕ Add an author", on_click=add_author)

        st.divider()

        #JSON generation
        if st.button("🚀 Upload metadatas", type="primary"):
            # final JSON
            authors_dict = {}
            for j in range(len(st.session_state.auteurs)):
                authors_dict[f"author_{j+1}"] = {
                    "name": st.session_state.get(f"name_{j}"),
                    "surname": st.session_state.get(f"surname_{j}"),
                    "is_corresponding": st.session_state.get(f"corr_{j}"),
                    "email": st.session_state.get(f"email_{j}") if st.session_state.get(f"corr_{j}") else None
                }

            # Structure finale demandée
            final_json = {
                "doi": doi,
                "abstract": abstract,
                "authors": authors_dict
            }

            st.success("Successfuly contributed, thank you !")
            return uploaded_file, final_json

if __name__ == "__main__":
    main()
