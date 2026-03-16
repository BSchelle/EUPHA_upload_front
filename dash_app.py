from __future__ import annotations
import dash  # L'import de la vraie librairie
from dash import dcc, html, Input, Output, State, ALL, ctx
import dash_bootstrap_components as dbc
import base64
from typing import Optional
import re
import io
import fitz  # PyMuPDF
import pdfplumber


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])


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

        # Extract metadata
        metadata["doi"] = extract_doi_from_pdf(pdf_text)
        metadata["abstract"] = extract_abstract_from_pdf(pdf_text)
        metadata["authors"] = extract_authors_from_pdf(pdf_text)

    except Exception as e:
        print(f"Error processing PDF: {e}")
    return metadata

app.layout = dbc.Container([
    dcc.Store(id='session-store', data={}), # Remplace st.session_state

    html.H1("EU Fact Force - Article uploading page"),

    dcc.Upload(
        id='upload-pdf',
        children=html.Div(['Glissez-déposez ou ', html.A('Sélectionnez un PDF')]),
        style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px', 'borderStyle': 'dashed', 'textAlign': 'center'}
    ),

    html.Hr(),
    dbc.Row([
        dbc.Col([
            dbc.Label("DOI"),
            dbc.Input(id='input-doi', type='text'),
            dbc.Label("Abstract"),
            dbc.Textarea(id='input-abstract', style={'height': 150}),
            dbc.Checkbox(id='chk-meta-correct', label="Informations correctes"),
        ], width=6)
    ]),

    html.Hr(),
    html.H3("Authors"),
    html.Div(id='authors-container'), # Ici s'afficheront les auteurs
    dbc.Button("➕ Add an author", id='btn-add-author', n_clicks=0, color="info", className="mt-2"),

    html.Hr(),
    dbc.Button("Upload file", id='btn-final-upload', color="primary", size="lg"),
    html.Div(id='final-output') # Pour le JSON final ou le graphe Cytoscape
], fluid=True)

@app.callback(
    Output('input-doi', 'value'),
    Output('input-abstract', 'value'),
    Output('session-store', 'data'),
    Input('upload-pdf', 'contents'),
    State('upload-pdf', 'filename')
)
def handle_pdf_upload(contents, filename):
    if contents is None:
        return dash.no_update, dash.no_update, {}

    # Décodage et appel de votre fonction existante
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    # Appel de votre fonction : extract_pdf_metadata
    metadata = extract_pdf_metadata(io.BytesIO(decoded))

    return metadata.get('doi', ''), metadata.get('abstract', ''), metadata

@app.callback(
    Output('authors-container', 'children'),
    Input('btn-add-author', 'n_clicks'),
    Input('session-store', 'data'), # Déclenché quand le PDF est lu
    State('authors-container', 'children')
)
def update_authors_list(n_clicks, metadata, current_children):
    triggered_id = ctx.triggered_id
    new_children = current_children or []

    # Si on vient de charger un PDF : on génère les lignes d'auteurs
    if triggered_id == 'session-store' and metadata:
        authors = metadata.get('authors', [])
        return [creer_ligne_auteur(i, a['name'], a['surname']) for i, a in enumerate(authors)]

    # Si on clique sur "Ajouter"
    if triggered_id == 'btn-add-author':
        new_index = len(new_children)
        new_children.append(creer_ligne_auteur(new_index))

    return new_children

def creer_ligne_auteur(index, name="", surname=""):
    return dbc.Card([
        dbc.Row([
            dbc.Col(dbc.Input(id={'type': 'auth-name', 'index': index}, value=name)),
            dbc.Col(dbc.Input(id={'type': 'auth-surname', 'index': index}, value=surname)),
        ])
    ], className="mb-2 p-2")

@app.callback(
    Output('cytoscape-graph', 'elements'), # Si votre graphe est sur la page
    Input('btn-final-upload', 'n_clicks'),
    State('input-doi', 'value'),
    State({'type': 'auth-name', 'index': ALL}, 'value'),
    State({'type': 'auth-surname', 'index': ALL}, 'value'),
    prevent_initial_call=True
)
def finalize_and_plot(n_clicks, doi, names, surnames):
    # Créer les nouveaux nœuds pour Cytoscape
    new_elements = []
    # Créer le nœud "Article"
    new_elements.append({'data': {'id': doi, 'label': f"Article: {doi}"}})

    # Créer les nœuds "Auteurs" et les liens
    for n, s in zip(names, surnames):
        auth_id = f"{n}_{s}"
        new_elements.append({'data': {'id': auth_id, 'label': f"{n} {s}"}})
        new_elements.append({'data': {'source': auth_id, 'target': doi}})

    return new_elements


if __name__ == '__main__':
    app.run(debug=True, port=8050)
