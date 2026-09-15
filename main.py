import customtkinter as ctk
from PIL import Image, ImageDraw
import os
import shutil
import threading
from pathlib import Path
from tkinter import filedialog
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
except ImportError:
    genai = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    GEMINI_API_KEY = GEMINI_API_KEY.strip().replace("\\_", "_")

ASSISTANT_NAME = "Orvix"
ASSISTANT_SYSTEM_PROMPT = (
    "Tu es Orvix, l'intelligence sociale et pedagogique du projet Orvix. "
    "Dans la discussion, tu ne te presentes jamais comme Gemini, Google ou un modele externe. "
    "Ta mission principale est d'aider l'utilisateur a travailler a partir de ses documents : "
    "comprendre un texte, expliquer une notion, repondre a des questions, trouver la problematique, "
    "preparer une revision, creer des questions et proposer des quiz. "
    "Tes reponses doivent toujours tourner autour de l'objectif de l'interaction et du contenu disponible. "
    "Quand l'utilisateur demande une reponse basee sur un document mais qu'aucun document ou extrait n'est fourni, "
    "demande-lui d'ajouter ou de coller le passage utile au lieu d'inventer. "
    "Quand la demande est floue, pose une question courte et precise pour fixer l'objectif avant de developper. "
    "Quand tu peux aider tout de suite, commence par une reponse utile puis propose la prochaine etape. "
    "Pour les revisions, organise les idees, resume, cree des questions, corrige les reponses et explique les erreurs. "
    "Les langues de base sont le francais et l'anglais ; reponds dans la langue de l'utilisateur, "
    "ou en francais par defaut. "
    "Si l'utilisateur demande qui tu es, presente-toi simplement comme Orvix, l'assistant IA du projet Orvix."
)

GEMINI_MODEL = "gemini-3.7-flash"
BASE_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = BASE_DIR / "documents"
DATA_DIR = BASE_DIR / "data"
DOCUMENT_CONTEXT_FILE = DATA_DIR / "document_context.txt"
SUPPORTED_DOCUMENT_TYPES = (".txt", ".md", ".pdf")

DOCUMENTS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

gemini_client = None
gemini_chat_session = None
support_status_message = ""

def get_gemini_chat_session():
    global gemini_client, gemini_chat_session

    if gemini_chat_session is None:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        gemini_chat_session = gemini_client.chats.create(
            model=GEMINI_MODEL,
            history=[
                {
                    "role": "user",
                    "parts": [{"text": ASSISTANT_SYSTEM_PROMPT}]
                },
                {
                    "role": "model",
                    "parts": [{"text": "Compris. Je suis Orvix, l'assistant IA du projet Orvix."}]
                }
            ]
        )

    return gemini_chat_session

def format_assistant_error(error):
    error_text = str(error)

    if "503" in error_text or "UNAVAILABLE" in error_text or "high demand" in error_text:
        return (
            f"{ASSISTANT_NAME} est temporairement surcharge. "
            "Reessaie dans quelques instants."
        )

    if "API key" in error_text or "GEMINI_API_KEY" in error_text:
        return (
            f"La cle API de {ASSISTANT_NAME} semble invalide ou absente. "
            "Verifie le fichier .env."
        )

    return (
        f"{ASSISTANT_NAME} n'arrive pas a repondre pour le moment. "
        "Verifie la connexion, puis reessaie."
    )

def extract_text_from_document(path):
    suffix = path.suffix.lower()

    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore").strip()

    if suffix == ".pdf":
        if PdfReader is None:
            return ""

        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages).strip()

    return ""

def rebuild_document_context():
    sections = []

    for document_path in sorted(DOCUMENTS_DIR.iterdir()):
        if not document_path.is_file():
            continue
        if document_path.suffix.lower() not in SUPPORTED_DOCUMENT_TYPES:
            continue

        text = extract_text_from_document(document_path)
        if not text:
            continue

        sections.append(
            f"DOCUMENT: {document_path.name}\n{text}"
        )

    DOCUMENT_CONTEXT_FILE.write_text(
        "\n\n---\n\n".join(sections),
        encoding="utf-8"
    )

def load_document_context(max_chars=16000):
    if not DOCUMENT_CONTEXT_FILE.exists():
        return ""

    content = DOCUMENT_CONTEXT_FILE.read_text(encoding="utf-8", errors="ignore").strip()
    if len(content) <= max_chars:
        return content

    return content[:max_chars] + "\n\n[Contexte tronque : documents plus longs disponibles.]"

def build_document_prompt(user_prompt):
    document_context = load_document_context()

    if not document_context:
        return user_prompt

    return (
        "Reponds a la demande de l'utilisateur en utilisant d'abord les documents ci-dessous. "
        "Si les documents ne contiennent pas l'information necessaire, dis-le clairement et "
        "demande le passage ou le document manquant.\n\n"
        f"{document_context}\n\n"
        f"QUESTION DE L'UTILISATEUR:\n{user_prompt}"
    )

def get_document_count():
    return len([
        path for path in DOCUMENTS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_DOCUMENT_TYPES
    ])

def get_document_names():
    return [
        path.name for path in sorted(DOCUMENTS_DIR.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_DOCUMENT_TYPES
    ]

try:
    rebuild_document_context()
except Exception:
    pass

ctk.set_appearance_mode("light")

# =========================================================
# COULEURS
# =========================================================

TEAL = "#14B8A6"
TEAL_DARK = "#0F8F83"
TEAL_LIGHT = "#E8F8F6"

WHITE = "#FFFFFF"
BG = "#F7FAFA"

BLACK = "#111827"
TEXT_SECONDARY = "#667085"
TEXT_LIGHT = "#98A2B3"

BORDER = "#D8EAE7"
LINE = "#E8EEEE"
HOVER = "#F3F7F7"

# =========================================================
# CREATION DES ICONES
# =========================================================

def create_icon(icon_type, color):
    size = 40

    image = Image.new(
        "RGBA",
        (size, size),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(image)

    width = 3

    if icon_type == "chat":

        draw.rounded_rectangle(
            (7, 8, 33, 29),
            radius=7,
            outline=color,
            width=width
        )

        draw.line(
            (14, 29, 11, 34, 20, 29),
            fill=color,
            width=width
        )

    elif icon_type == "revision":

        draw.rounded_rectangle(
            (9, 6, 31, 34),
            radius=4,
            outline=color,
            width=width
        )

        draw.line(
            (14, 14, 26, 14),
            fill=color,
            width=width
        )

        draw.line(
            (14, 20, 26, 20),
            fill=color,
            width=width
        )

        draw.line(
            (14, 26, 22, 26),
            fill=color,
            width=width
        )

    elif icon_type == "quiz":

        draw.ellipse(
            (7, 7, 33, 33),
            outline=color,
            width=width
        )

        draw.arc(
            (14, 11, 27, 24),
            start=200,
            end=520,
            fill=color,
            width=width
        )

        draw.ellipse(
            (19, 27, 22, 30),
            fill=color
        )

    elif icon_type == "support":

        draw.rounded_rectangle(
            (8, 9, 32, 32),
            radius=4,
            outline=color,
            width=width
        )

        draw.line(
            (13, 6, 24, 6, 28, 10),
            fill=color,
            width=width
        )

        draw.line(
            (14, 17, 26, 17),
            fill=color,
            width=width
        )

        draw.line(
            (14, 23, 26, 23),
            fill=color,
            width=width
        )

    elif icon_type == "settings":

        draw.ellipse(
            (14, 14, 26, 26),
            outline=color,
            width=width
        )

        for x1, y1, x2, y2 in [
            (20, 5, 20, 11),
            (20, 29, 20, 35),
            (5, 20, 11, 20),
            (29, 20, 35, 20),
            (9, 9, 13, 13),
            (27, 27, 31, 31),
            (9, 31, 13, 27),
            (27, 13, 31, 9)
        ]:
            draw.line(
                (x1, y1, x2, y2),
                fill=color,
                width=width
            )

    elif icon_type == "send":

        draw.line(
            (8, 20, 30, 20),
            fill=color,
            width=3
        )

        draw.line(
            (23, 13, 30, 20),
            fill=color,
            width=3
        )

        draw.line(
            (23, 27, 30, 20),
            fill=color,
            width=3
        )

    return ctk.CTkImage(
        light_image=image,
        dark_image=image,
        size=(23, 23)
    )

# =========================================================
# ICONES
# =========================================================

icons_normal = {
    "chat": create_icon("chat", BLACK),
    "revision": create_icon("revision", BLACK),
    "quiz": create_icon("quiz", BLACK),
    "support": create_icon("support", BLACK),
    "settings": create_icon("settings", BLACK)
}

icons_active = {
    "chat": create_icon("chat", TEAL_DARK),
    "revision": create_icon("revision", TEAL_DARK),
    "quiz": create_icon("quiz", TEAL_DARK),
    "support": create_icon("support", TEAL_DARK)
}

send_icon = create_icon(
    "send",
    WHITE
)

# =========================================================
# APPLICATION
# =========================================================

app = ctk.CTk()

app.title("Orvix")

app.geometry("1450x850")

app.minsize(
    1150,
    700
)

app.configure(
    fg_color=BG
)

app.grid_columnconfigure(
    0,
    weight=0
)

app.grid_columnconfigure(
    1,
    weight=1
)

app.grid_rowconfigure(
    0,
    weight=0
)

app.grid_rowconfigure(
    1,
    weight=1
)

# =========================================================
# BARRE DU HAUT
# =========================================================

topbar = ctk.CTkFrame(
    app,
    height=70,
    corner_radius=0,
    fg_color=TEAL
)

topbar.grid(
    row=0,
    column=0,
    columnspan=2,
    sticky="nsew"
)

topbar.grid_propagate(False)

# =========================================================
# LOGO
# =========================================================

logo_frame = ctk.CTkFrame(
    topbar,
    fg_color="transparent"
)

logo_frame.pack(
    side="left",
    padx=26
)

logo_icon = ctk.CTkLabel(
    logo_frame,
    text="O",
    width=34,
    height=34,
    corner_radius=17,
    fg_color=WHITE,
    text_color=TEAL_DARK,
    font=ctk.CTkFont(
        family="Segoe UI",
        size=16,
        weight="bold"
    )
)

logo_icon.pack(
    side="left"
)

logo_text = ctk.CTkLabel(
    logo_frame,
    text="ORVIX",
    text_color=WHITE,
    font=ctk.CTkFont(
        family="Segoe UI",
        size=24,
        weight="bold"
    )
)

logo_text.pack(
    side="left",
    padx=(9, 0)
)

top_user = ctk.CTkLabel(
    topbar,
    text="Alex   |   Etudiant",
    text_color=WHITE,
    font=ctk.CTkFont(
        family="Segoe UI",
        size=13
    )
)

top_user.pack(
    side="right",
    padx=28
)

# =========================================================
# SIDEBAR
# =========================================================

sidebar = ctk.CTkFrame(
    app,
    width=220,
    fg_color=WHITE,
    corner_radius=0
)

sidebar.grid(
    row=1,
    column=0,
    sticky="nsew"
)

sidebar.grid_propagate(False)

sidebar_content = ctk.CTkFrame(
    sidebar,
    fg_color="transparent"
)

sidebar_content.pack(
    fill="both",
    expand=True,
    padx=11,
    pady=14
)

# =========================================================
# NAVIGATION
# =========================================================

buttons = []


def set_active(active_button):

    for data in buttons:

        button = data["button"]

        button.configure(
            fg_color="transparent",
            text_color=BLACK,
            image=data["normal_icon"]
        )

    for data in buttons:

        if data["button"] == active_button:

            active_button.configure(
                fg_color=TEAL_LIGHT,
                text_color=TEAL_DARK,
                image=data["active_icon"]
            )

            break


def create_nav_button(
    text,
    icon_name,
    command=None
):

    button = ctk.CTkButton(
        sidebar_content,

        text=text,

        image=icons_normal[icon_name],

        compound="left",

        command=command,

        height=28,

        corner_radius=8,

        anchor="w",

        fg_color="transparent",

        hover_color="#F1F7F6",

        text_color=BLACK,

        border_spacing=10,

        font=ctk.CTkFont(
            family="Segoe UI",
            size=16,
            weight="normal"
        )
    )

    button.pack(
        fill="x",
        pady=1
    )

    buttons.append({
        "button": button,
        "normal_icon": icons_normal[icon_name],
        "active_icon": icons_active[icon_name]
    })

    return button

# =========================================================
# MAIN
# =========================================================

main = ctk.CTkFrame(
    app,
    fg_color=BG,
    corner_radius=0
)

main.grid(
    row=1,
    column=1,
    sticky="nsew"
)

main.grid_columnconfigure(
    0,
    weight=1
)

main.grid_rowconfigure(
    0,
    weight=1
)


def clear_main():

    for widget in main.winfo_children():

        widget.destroy()

# =========================================================
# CHAT
# =========================================================

def show_chat():

    clear_main()

    set_active(
        btn_chat
    )

    page = ctk.CTkFrame(
        main,
        fg_color=WHITE
    )

    page.pack(
        fill="both",
        expand=True
    )

    conversation = ctk.CTkScrollableFrame(
        page,
        fg_color="transparent",
        scrollbar_button_color=BORDER,
        scrollbar_button_hover_color=TEAL_LIGHT
    )

    conversation.pack(
        fill="both",
        expand=True
    )

    welcome = ctk.CTkFrame(
        conversation,
        fg_color="transparent"
    )

    welcome.pack(
        expand=True,
        pady=(150, 30)
    )

    title = ctk.CTkLabel(
        welcome,
        text="Que veux-tu etudier ?",
        text_color=BLACK,
        font=ctk.CTkFont(
            family="Segoe UI",
            size=30,
            weight="bold"
        )
    )

    title.pack(
        pady=(0, 8)
    )

    subtitle = ctk.CTkLabel(
        welcome,
        text="Pose une question a partir de tes supports.",
        text_color=TEXT_SECONDARY,
        font=ctk.CTkFont(
            family="Segoe UI",
            size=14
        )
    )

    subtitle.pack()

    # =====================================================
    # BARRE DE SAISIE
    # =====================================================

    input_container = ctk.CTkFrame(
        page,
        fg_color="transparent"
    )

    input_container.pack(
        side="bottom",
        fill="x",
        padx=140,
        pady=(0, 22)
    )

    input_wrapper = ctk.CTkFrame(
        input_container,
        fg_color=WHITE,
        height=52,
        corner_radius=16,
        border_width=1,
        border_color="#D4DADB"
    )

    input_wrapper.pack(
        fill="x"
    )

    input_wrapper.pack_propagate(False)

    input_wrapper.grid_columnconfigure(
        0,
        weight=1
    )

    message_entry = ctk.CTkEntry(
        input_wrapper,
        height=36,
        placeholder_text="Pose une question sur ton cours",
        fg_color=WHITE,
        border_width=0,
        text_color=BLACK,
        placeholder_text_color=TEXT_LIGHT,
        font=ctk.CTkFont(
            family="Segoe UI",
            size=14
        )
    )

    message_entry.grid(
        row=0,
        column=0,
        sticky="ew",
        padx=(14, 5),
        pady=7
    )

    def add_message(text, is_user=False, color=None):
        row = ctk.CTkFrame(conversation, fg_color="transparent")
        row.pack(fill="x", padx=70, pady=6)

        bubble = ctk.CTkLabel(
            row,
            text=text,
            wraplength=680,
            justify="left",
            anchor="w",
            fg_color=color or (TEAL_LIGHT if is_user else "#F2F4F7"),
            text_color=BLACK,
            corner_radius=14,
            font=ctk.CTkFont(family="Segoe UI", size=14)
        )
        bubble.pack(side="right" if is_user else "left", padx=8)
        conversation._parent_canvas.yview_moveto(1.0)
        return bubble

    def finish_response(loading_label, answer):
        loading_label.configure(text=answer)
        send_button.configure(state="normal")
        message_entry.configure(state="normal")
        message_entry.focus_set()
        conversation._parent_canvas.yview_moveto(1.0)

    def ask_assistant(prompt, loading_label):
        try:
            response = get_gemini_chat_session().send_message(build_document_prompt(prompt))
            answer = response.text or f"{ASSISTANT_NAME} n'a retourne aucune reponse."
        except Exception as error:
            answer = format_assistant_error(error)

        app.after(0, lambda: finish_response(loading_label, answer))

    def send_message(event=None):
        prompt = message_entry.get().strip()
        if not prompt:
            return

        if welcome.winfo_exists():
            welcome.destroy()

        add_message(prompt, is_user=True)
        message_entry.delete(0, "end")

        if genai is None:
            add_message(
                "Le paquet google-genai manque. Installe les dependances avec : "
                "py -m pip install -r requirements.txt",
                color="#FEF3F2"
            )
            return

        if not GEMINI_API_KEY:
            add_message(
                f"La cle API de {ASSISTANT_NAME} n'est pas configuree. Consulte le fichier .env.",
                color="#FEF3F2"
            )
            return

        send_button.configure(state="disabled")
        message_entry.configure(state="disabled")
        loading_label = add_message(f"{ASSISTANT_NAME} reflechit...")
        threading.Thread(
            target=ask_assistant,
            args=(prompt, loading_label),
            daemon=True
        ).start()

    send_button = ctk.CTkButton(
        input_wrapper,

        text="",

        image=send_icon,

        width=36,
        height=36,

        corner_radius=18,

        fg_color=TEAL,
        hover_color=TEAL_DARK,

        border_width=0,
        command=send_message
    )

    send_button.grid(
        row=0,
        column=1,
        padx=(3, 8),
        pady=8
    )

    helper = ctk.CTkLabel(
        input_container,
        text=f"{ASSISTANT_NAME} utilise les supports disponibles pour construire ses reponses.",
        text_color=TEXT_LIGHT,
        font=ctk.CTkFont(
            family="Segoe UI",
            size=11
        )
    )

    helper.pack(
        pady=(7, 0)
    )

    message_entry.bind("<Return>", send_message)
    message_entry.focus_set()

# =========================================================
# CARTES SUPPORT
# =========================================================

def create_stat_card(
    parent,
    value,
    label
):

    card = ctk.CTkFrame(
        parent,

        height=58,

        fg_color=WHITE,

        corner_radius=9,

        border_width=1,

        border_color=BORDER
    )

    card.pack_propagate(False)

    value_label = ctk.CTkLabel(
        card,

        text=value,

        text_color=BLACK,

        font=ctk.CTkFont(
            family="Segoe UI",
            size=17,
            weight="bold"
        )
    )

    value_label.pack(
        anchor="w",
        padx=15,
        pady=(7, 0)
    )

    label_widget = ctk.CTkLabel(
        card,

        text=label,

        text_color=TEXT_SECONDARY,

        font=ctk.CTkFont(
            family="Segoe UI",
            size=11
        )
    )

    label_widget.pack(
        anchor="w",
        padx=15,
        pady=(0, 4)
    )

    return card

# =========================================================
# SUPPORT
# =========================================================

def show_support():
    global support_status_message

    clear_main()

    set_active(
        btn_support
    )

    page = ctk.CTkFrame(
        main,
        fg_color="transparent"
    )

    page.pack(
        fill="both",
        expand=True,
        padx=52,
        pady=38
    )

    status_message = ctk.StringVar(value=support_status_message)

    def add_documents():
        global support_status_message

        selected_files = filedialog.askopenfilenames(
            title="Ajouter des documents",
            filetypes=[
                ("Documents supportes", "*.pdf *.txt *.md"),
                ("PDF", "*.pdf"),
                ("Texte", "*.txt *.md")
            ]
        )

        if not selected_files:
            return

        copied = 0
        for selected_file in selected_files:
            source = Path(selected_file)
            if source.suffix.lower() not in SUPPORTED_DOCUMENT_TYPES:
                continue

            destination = DOCUMENTS_DIR / source.name
            if destination.exists():
                destination = DOCUMENTS_DIR / f"{source.stem}_{copied + 1}{source.suffix}"

            shutil.copy2(source, destination)
            copied += 1

        rebuild_document_context()
        support_status_message = f"{copied} document(s) ajoute(s). Orvix peut maintenant les utiliser."
        show_support()

    header = ctk.CTkFrame(
        page,
        fg_color="transparent"
    )

    header.pack(
        fill="x"
    )

    header.grid_columnconfigure(
        0,
        weight=1
    )

    left_header = ctk.CTkFrame(
        header,
        fg_color="transparent"
    )

    left_header.grid(
        row=0,
        column=0,
        sticky="w"
    )

    title = ctk.CTkLabel(
        left_header,
        text="Support",
        text_color=BLACK,
        font=ctk.CTkFont(
            family="Segoe UI",
            size=32,
            weight="bold"
        )
    )

    title.pack(
        anchor="w"
    )

    subtitle = ctk.CTkLabel(
        left_header,
        text="Ajoute les documents utilises par Orvix.",
        text_color=TEXT_SECONDARY,
        font=ctk.CTkFont(
            family="Segoe UI",
            size=14
        )
    )

    subtitle.pack(
        anchor="w",
        pady=(5, 0)
    )

    add_button = ctk.CTkButton(
        header,
        text="+ Ajouter un document",
        width=200,
        height=42,
        fg_color=TEAL,
        hover_color=TEAL_DARK,
        text_color=WHITE,
        corner_radius=11,
        command=add_documents,
        font=ctk.CTkFont(
            family="Segoe UI",
            size=13,
            weight="bold"
        )
    )

    add_button.grid(
        row=0,
        column=1,
        sticky="e"
    )

    # =====================================================
    # CARTES STATISTIQUES
    # =====================================================

    stats = ctk.CTkFrame(
        page,
        fg_color="transparent"
    )

    stats.pack(
        fill="x",
        pady=(24, 24)
    )

    create_stat_card(
        stats,
        str(get_document_count()),
        "Documents"
    ).pack(
        side="left",
        fill="x",
        expand=True,
        padx=(0, 7)
    )

    create_stat_card(
        stats,
        "Pret",
        "Analyse texte"
    ).pack(
        side="left",
        fill="x",
        expand=True,
        padx=7
    )

    create_stat_card(
        stats,
        "Local",
        "Stockage"
    ).pack(
        side="left",
        fill="x",
        expand=True,
        padx=(7, 0)
    )

    # =====================================================
    # DOCUMENTS
    # =====================================================

    documents_header = ctk.CTkFrame(
        page,
        fg_color="transparent"
    )

    documents_header.pack(
        fill="x",
        pady=(2, 8)
    )

    docs_title = ctk.CTkLabel(
        documents_header,
        text="Mes documents",
        text_color=BLACK,
        font=ctk.CTkFont(
            family="Segoe UI",
            size=19,
            weight="bold"
        )
    )

    docs_title.pack(
        side="left"
    )

    search = ctk.CTkEntry(
        documents_header,
        width=240,
        height=36,
        placeholder_text="Rechercher",
        fg_color=WHITE,
        border_width=1,
        border_color=BORDER,
        text_color=BLACK,
        placeholder_text_color=TEXT_SECONDARY,
        corner_radius=9
    )

    search.pack(
        side="right"
    )

    separator = ctk.CTkFrame(
        page,
        height=1,
        fg_color=LINE
    )

    separator.pack(
        fill="x",
        pady=(2, 22)
    )

    documents = get_document_names()

    empty = ctk.CTkFrame(
        page,
        fg_color="transparent"
    )

    empty.pack(
        fill="x",
        pady=(35, 0)
    )

    if documents:
        for document_name in documents:
            document_row = ctk.CTkFrame(
                empty,
                fg_color=WHITE,
                corner_radius=8,
                border_width=1,
                border_color=BORDER,
                height=44
            )

            document_row.pack(
                fill="x",
                pady=5
            )

            document_row.pack_propagate(False)

            document_label = ctk.CTkLabel(
                document_row,
                text=document_name,
                text_color=BLACK,
                font=ctk.CTkFont(
                    family="Segoe UI",
                    size=13
                )
            )

            document_label.pack(
                side="left",
                padx=14
            )
    else:
        empty_title = ctk.CTkLabel(
            empty,
            text="Aucun document ajoute",
            text_color=BLACK,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=19,
                weight="bold"
            )
        )

        empty_title.pack()

        empty_subtitle = ctk.CTkLabel(
            empty,
            text="Ajoute ton premier PDF ou texte pour commencer.",
            text_color=TEXT_SECONDARY,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=13
            )
        )

        empty_subtitle.pack(
            pady=(5, 16)
        )

    second_button = ctk.CTkButton(
        empty,
        text="+ Ajouter un document",
        width=180,
        height=39,
        fg_color=WHITE,
        hover_color=TEAL_LIGHT,
        border_width=1,
        border_color=TEAL,
        text_color=TEAL_DARK,
        corner_radius=10,
        command=add_documents,
        font=ctk.CTkFont(
            family="Segoe UI",
            size=12,
            weight="bold"
        )
    )

    second_button.pack()

    status = ctk.CTkLabel(
        page,
        textvariable=status_message,
        text_color=TEAL_DARK,
        font=ctk.CTkFont(
            family="Segoe UI",
            size=12
        )
    )

    status.pack(
        pady=(16, 0)
    )

# =========================================================
# BOUTONS DE NAVIGATION
# =========================================================

btn_chat = create_nav_button(
    "Chat",
    "chat",
    show_chat
)

btn_revision = create_nav_button(
    "Revision",
    "revision"
)

btn_quiz = create_nav_button(
    "Quiz",
    "quiz"
)

btn_support = create_nav_button(
    "Support",
    "support",
    show_support
)

# =========================================================
# HISTORIQUE
# =========================================================

history_section = ctk.CTkFrame(
    sidebar_content,
    fg_color="transparent"
)

history_section.pack(
    fill="both",
    expand=True,
    pady=(20, 10)
)

history_title = ctk.CTkLabel(
    history_section,
    text="RECENTS",
    text_color=TEXT_LIGHT,
    font=ctk.CTkFont(
        family="Segoe UI",
        size=11,
        weight="bold"
    )
)

history_title.pack(
    anchor="w",
    padx=10,
    pady=(0, 7)
)

history_empty = ctk.CTkLabel(
    history_section,
    text="Aucune conversation",
    text_color=TEXT_LIGHT,
    font=ctk.CTkFont(
        family="Segoe UI",
        size=12
    )
)

history_empty.pack(
    anchor="w",
    padx=10
)

# =========================================================
# PROFIL
# =========================================================

profile = ctk.CTkFrame(
    sidebar_content,
    fg_color="#FBFDFD",
    corner_radius=10,
    border_width=1,
    border_color=BORDER,
    height=50
)

profile.pack(
    side="bottom",
    fill="x"
)

profile.pack_propagate(False)

avatar = ctk.CTkLabel(
    profile,
    text="A",
    width=30,
    height=30,
    corner_radius=15,
    fg_color=TEAL,
    text_color=WHITE,
    font=ctk.CTkFont(
        family="Segoe UI",
        size=12,
        weight="bold"
    )
)

avatar.pack(
    side="left",
    padx=(9, 8)
)

profile_info = ctk.CTkFrame(
    profile,
    fg_color="transparent"
)

profile_info.pack(
    side="left"
)

profile_name = ctk.CTkLabel(
    profile_info,
    text="Alex",
    text_color=BLACK,
    font=ctk.CTkFont(
        family="Segoe UI",
        size=12,
        weight="bold"
    )
)

profile_name.pack(
    anchor="w"
)

profile_role = ctk.CTkLabel(
    profile_info,
    text="Etudiant",
    text_color=TEXT_SECONDARY,
    font=ctk.CTkFont(
        family="Segoe UI",
        size=10
    )
)

profile_role.pack(
    anchor="w"
)

# =========================================================
# PARAMETRES
# =========================================================

bottom_section = ctk.CTkFrame(
    sidebar_content,
    fg_color="transparent"
)

bottom_section.pack(
    side="bottom",
    fill="x",
    pady=(0, 7)
)

bottom_line = ctk.CTkFrame(
    bottom_section,
    height=1,
    fg_color=LINE
)

bottom_line.pack(
    fill="x",
    pady=(0, 6)
)

settings = ctk.CTkButton(
    bottom_section,

    text="Parametres",

    image=icons_normal["settings"],

    compound="left",

    height=38,

    corner_radius=8,

    anchor="w",

    fg_color="transparent",

    hover_color=HOVER,

    text_color=BLACK,

    border_spacing=10,

    font=ctk.CTkFont(
        family="Segoe UI",
        size=15
    )
)

settings.pack(
    fill="x"
)

# =========================================================
# DEMARRAGE
# =========================================================

show_chat()

app.mainloop()
