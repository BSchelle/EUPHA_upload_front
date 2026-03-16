from __future__ import annotations
import dash  # L'import de la vraie librairie
from dash import dcc, html, Input, Output, State, ALL, ctx
import dash_bootstrap_components as dbc
import base64
from typing import Optional
import re
import io
import fitz  # PyMuPDF
import json
import uuid

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

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
        blocks.sort(key=lambda b: (round(b[1] / 20), b[0]))
        for block in blocks:
            full_text += block[4] + "\n"
    return full_text

def extract_pdf_metadata(uploaded_file) -> dict:
    """Extract metadata from PDF file."""
    metadata = {"doi": None, "abstract": None, "authors": []}
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

# --- LAYOUT COMPONENTS ---

logo_uri = load_svg_as_data_uri("eupha-logo.svg")

sidebar = html.Div(
    [
        html.Img(src=logo_uri, style={"width": "100%", "maxWidth": "220px", "height": "auto", "display": "block", "margin": "8px auto 20px auto"}) if logo_uri else html.Div(),
        html.H3("EU Fact Force", className="text-center font-weight-bold"),
        html.Hr(),
        html.H5("How it works", className="mb-3 font-weight-bold"),
        html.Ol([
            html.Li("Upload a PDF"),
            html.Li("Validate DOI + abstract"),
            html.Li("Validate authors"),
            html.Li("Click Upload file")
        ], className="pl-3")
    ],
    style={
        "padding": "2rem 1rem",
        "backgroundColor": "#f8f9fa",
        "height": "100vh",
        "position": "fixed",
        "top": 0,
        "left": 0,
        "width": "25%",
        "borderRight": "1px solid #dee2e6"
    }
)

main_content = html.Div(
    [
        html.H1("EU Fact Force - Article uploading page", className="mb-2"),
        html.H3("Welcome to EU Fact Force articles uploading pages", className="text-muted mb-4"),
        html.P("Thank you for collaborating with us, you will find here a page where you can upload and declare authors of your papers in attempt to build a safer and healthier community! Thank you for your contribution!"),

        dbc.Card([
            dbc.CardBody([
                html.H4("Upload & Metadatas", className="card-title font-weight-bold mb-4"),
                dcc.Upload(
                    id='upload-pdf',
                    children=html.Div(['Drop your article here or ', html.A('Select a PDF', className="font-weight-bold")]),
                    style={
                        'width': '100%', 'height': '80px', 'lineHeight': '80px',
                        'borderWidth': '2px', 'borderStyle': 'dashed', 'borderColor': '#adb5bd',
                        'textAlign': 'center', 'borderRadius': '10px', 'marginBottom': '20px',
                        'backgroundColor': '#f8f9fa', 'cursor': 'pointer'
                    }
                ),
                html.H5("General informations", className="mt-4 font-weight-bold"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Please share DOI"),
                        dbc.Input(id='input-doi', type='text', placeholder="ex: 10.1038/s41586-021-00000-x"),
                        dbc.Label("Please share your abstract", className="mt-3"),
                        dbc.Textarea(id='input-abstract', style={'height': 150}, placeholder="Lorem ipsum dolor sit amet"),
                        dbc.Checkbox(id='chk-meta-correct', label="This information is correct", className="mt-3 font-weight-bold text-success"),
                    ], width=12)
                ]),
            ])
        ], className="mb-4 shadow-sm", style={"borderRadius": "16px"}),

        dbc.Card([
            dbc.CardBody([
                html.H4("Authors", className="card-title font-weight-bold mb-4"),
                html.Div(id='authors-container'),
                dbc.Button("➕ Add an author", id='btn-add-author', n_clicks=0, color="info", outline=True, className="mt-3"),
                html.Br(),
                dbc.Checkbox(id='chk-authors-correct', label="Authors information is correct", className="mt-3 font-weight-bold text-success"),
            ])
        ], className="mb-4 shadow-sm", style={"borderRadius": "16px"}),

        dbc.Button("Upload file", id='btn-final-upload', color="primary", size="lg", className="w-100 mb-4"),
        html.Div(id='final-output', className="mt-4 pb-5")
    ],
    style={"marginLeft": "25%", "padding": "2rem 3rem", "maxWidth": "1200px"}
)

app.layout = html.Div([
    dcc.Store(id='session-store', data={}),
    sidebar,
    main_content
], style={"fontFamily": "system-ui, -apple-system, sans-serif"})


def creer_ligne_auteur(index, name="", surname="", email=""):
    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col(dbc.Input(id={'type': 'auth-name', 'index': index}, value=name, placeholder="Name"), width=3),
                dbc.Col(dbc.Input(id={'type': 'auth-surname', 'index': index}, value=surname, placeholder="Surname"), width=4),
                dbc.Col(dbc.Input(id={'type': 'auth-email', 'index': index}, value=email, placeholder="Email (Corresponding)"), width=4),
                dbc.Col(dbc.Button("Remove", id={'type': 'remove-author', 'index': index}, color="danger", outline=True, className="w-100"), width=1)
            ], className="align-items-center")
        ], className="p-2")
    ], className="mb-3 border-light shadow-sm")


# --- CALLBACKS ---

@app.callback(
    Output('input-doi', 'value'),
    Output('input-abstract', 'value'),
    Output('session-store', 'data'),
    Input('upload-pdf', 'contents')
)
def handle_pdf_upload(contents):
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
    Input({'type': 'remove-author', 'index': ALL}, 'n_clicks'),
    Input('session-store', 'data'),
    State({'type': 'auth-name', 'index': ALL}, 'value'),
    State({'type': 'auth-surname', 'index': ALL}, 'value'),
    State({'type': 'auth-email', 'index': ALL}, 'value'),
    State({'type': 'auth-name', 'index': ALL}, 'id'),
)
def update_authors_list(add_clicks, remove_clicks, metadata, names, surnames, emails, ids):
    triggered = ctx.triggered_id

    # On new PDF load
    if triggered == 'session-store' and metadata:
        authors = metadata.get('authors', [])
        return [creer_ligne_auteur(str(uuid.uuid4()), a.get('name', ''), a.get('surname', ''), a.get('email', '')) for a in authors]

    # Reconstruct current list of authors from states
    current_authors = []
    if ids:
        for idx_id, name, surname, email in zip(ids, names, surnames, emails):
            current_authors.append({
                'index': idx_id['index'],
                'name': name or "",
                'surname': surname or "",
                'email': email or ""
            })

    if triggered == 'btn-add-author':
        current_authors.append({
            'index': str(uuid.uuid4()),
            'name': "",
            'surname': "",
            'email': ""
        })

    if isinstance(triggered, dict) and triggered.get('type') == 'remove-author':
        remove_index = triggered.get('index')
        current_authors = [a for a in current_authors if a['index'] != remove_index]

    return [creer_ligne_auteur(a['index'], a['name'], a['surname'], a['email']) for a in current_authors]


@app.callback(
    Output('input-doi', 'disabled'),
    Output('input-abstract', 'disabled'),
    Input('chk-meta-correct', 'value')
)
def lock_metadata(is_correct):
    return bool(is_correct), bool(is_correct)


@app.callback(
    Output({'type': 'auth-name', 'index': ALL}, 'disabled'),
    Output({'type': 'auth-surname', 'index': ALL}, 'disabled'),
    Output({'type': 'auth-email', 'index': ALL}, 'disabled'),
    Output({'type': 'remove-author', 'index': ALL}, 'disabled'),
    Output('btn-add-author', 'disabled'),
    Input('chk-authors-correct', 'value'),
    State({'type': 'auth-name', 'index': ALL}, 'id')
)
def lock_authors(is_correct, ids):
    is_corr = bool(is_correct)
    if not ids:
        return [], [], [], [], is_corr
    length = len(ids)
    return [is_corr]*length, [is_corr]*length, [is_corr]*length, [is_corr]*length, is_corr


@app.callback(
    Output('final-output', 'children'),
    Input('btn-final-upload', 'n_clicks'),
    State('input-doi', 'value'),
    State('input-abstract', 'value'),
    State({'type': 'auth-name', 'index': ALL}, 'value'),
    State({'type': 'auth-surname', 'index': ALL}, 'value'),
    State({'type': 'auth-email', 'index': ALL}, 'value'),
    prevent_initial_call=True
)
def finalize_and_display_json(n_clicks, doi, abstract, names, surnames, emails):

    authors_list = [
        {"name": n, "surname": s, "email": e}
        for n, s, e in zip(names, surnames, emails) if n or s
    ]

    metadata_json = {
        "doi": doi,
        "abstract": abstract,
        "authors": authors_list
    }

    return html.Div([
        dbc.Alert("Successfully contributed, thank you!", color="success"),
        html.H4("Metadata JSON"),
        html.Pre(json.dumps(metadata_json, indent=4), style={'backgroundColor': '#f8f9fa', 'padding': '15px', 'borderRadius': '8px', 'border': '1px solid #dee2e6'})
    ])


if __name__ == '__main__':
    app.run(debug=True, port=8050)
