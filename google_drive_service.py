
import io
import os
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credential.json"
TOKEN_FILE = BASE_DIR / "token.json"

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

GOOGLE_DOCS_MIME = "application/vnd.google-apps.document"


def get_drive_service():
    """Retourne un client Drive authentifié en lecture seule."""
    credentials = None

    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            str(TOKEN_FILE), SCOPES
        )

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(
                "credentials.json introuvable. "
                "Télécharge les identifiants OAuth Google Cloud."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE), SCOPES
        )
        credentials = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")

    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def search_drive_files(query: str, page_size: int = 10) -> str:
    """Recherche des fichiers par nom dans le Drive accessible."""
    query = query.strip()
    if not query:
        return "Indique un nom ou un mot-clé à rechercher dans Google Drive."

    service = get_drive_service()

    # Recherche par nom. Les fichiers supprimés sont exclus.
    escaped_query = query.replace("\\", "\\\\").replace("'", "\\'")
    response = service.files().list(
        q=f"name contains '{escaped_query}' and trashed = false",
        pageSize=min(max(page_size, 1), 20),
        orderBy="modifiedTime desc",
        fields=(
            "files(id,name,mimeType,webViewLink,modifiedTime,size,"
            "description)"
        ),
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    files = response.get("files", [])
    if not files:
        return f"Aucun fichier trouvé dans Google Drive pour : {query}"

    lines = []
    for file in files:
        lines.append(
            f"- Nom : {file.get('name', 'Sans nom')}\n"
            f"  ID : {file['id']}\n"
            f"  Type : {file.get('mimeType', 'inconnu')}\n"
            f"  Modifié : {file.get('modifiedTime', 'inconnu')}\n"
            f"  Lien : {file.get('webViewLink', 'indisponible')}"
        )

    return "\n".join(lines)


def _download_file(service, file_id: str) -> bytes:
    """Télécharge le contenu d'un fichier non Google Workspace."""
    request = service.files().get_media(fileId=file_id)
    stream = io.BytesIO()
    downloader = MediaIoBaseDownload(stream, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    return stream.getvalue()


def read_drive_file(file_id: str) -> str:
    """Lit un Google Doc ou un fichier textuel pris en charge."""
    service = get_drive_service()

    metadata = service.files().get(
        fileId=file_id,
        fields="id,name,mimeType,webViewLink,size",
    ).execute()

    name = metadata.get("name", "Sans nom")
    mime_type = metadata.get("mimeType", "")

    # Google Docs : exporter le contenu en texte brut.
    if mime_type == GOOGLE_DOCS_MIME:
        content = service.files().export(
            fileId=file_id,
            mimeType="text/plain",
        ).execute()

        if isinstance(content, bytes):
            text = content.decode("utf-8", errors="replace")
        else:
            text = str(content)

    # Fichiers textuels classiques.
    elif (
        mime_type.startswith("text/")
        or Path(name).suffix.lower() in {
            ".txt", ".md", ".csv", ".json", ".xml", ".log"
        }
    ):
        raw = _download_file(service, file_id)
        text = raw.decode("utf-8-sig", errors="replace")

    else:
        return (
            f"Le fichier « {name} » existe, mais son type "
            f"({mime_type}) n'est pas encore pris en charge pour la lecture."
        )

    # Limiter le contenu transmis au modèle.
    max_chars = 30000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Contenu tronqué pour limiter la taille.]"

    return (
        f"Document : {name}\n"
        f"Type : {mime_type}\n"
        f"Lien : {metadata.get('webViewLink', 'indisponible')}\n\n"
        f"Contenu :\n{text}"
    )
