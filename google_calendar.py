
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Fuseau horaire par défaut : Bénin.
DEFAULT_TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "Africa/Porto-Novo")

# En développement local, mémorise temporairement les flux OAuth.
OAUTH_FLOWS = {}

REDIRECT_URI = "http://localhost:8000/auth/google/callback"


def create_oauth_flow(state=None):
    """Prépare le flux OAuth Google."""
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Fichier OAuth introuvable : {CREDENTIALS_FILE}"
        )

    flow = Flow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        scopes=SCOPES,
        state=state,
    )
    flow.redirect_uri = REDIRECT_URI
    return flow


def get_google_auth_url():
    """Construit l'URL de connexion Google."""
    flow = create_oauth_flow()

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    OAUTH_FLOWS[state] = flow
    return authorization_url


def finish_google_auth(code: str, state: str):
    flow = OAUTH_FLOWS.pop(state, None)

    if flow is None:
        raise ValueError(
            "Session OAuth introuvable ou expirée. "
            "Relance la connexion Google."
        )

    flow.fetch_token(code=code)
    credentials = flow.credentials

    TOKEN_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )

    return True

def get_calendar_service():
    """Retourne un client Google Calendar authentifié."""
    if not TOKEN_FILE.exists():
        raise RuntimeError(
            "Google Calendar n'est pas connecté. "
            "Ouvre d'abord /auth/google/login."
        )

    credentials = Credentials.from_authorized_user_file(
        str(TOKEN_FILE), SCOPES
    )

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        TOKEN_FILE.write_text(
            credentials.to_json(), encoding="utf-8"
        )

    if not credentials.valid:
        raise RuntimeError(
            "Autorisation Google expirée. Reconnecte ton compte."
        )

    return build("calendar", "v3", credentials=credentials)


def list_upcoming_events(days: int = 7, max_results: int = 20):
    """Liste les événements à venir sur une période."""
    if not 1 <= days <= 90:
        raise ValueError("La période doit être comprise entre 1 et 90 jours.")

    service = get_calendar_service()
    timezone = ZoneInfo(DEFAULT_TIMEZONE)
    now = datetime.now(timezone)
    end = now + timedelta(days=days)

    response = service.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=end.isoformat(),
        maxResults=max(1, min(max_results, 100)),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return [
        {
            "id": event["id"],
            "summary": event.get("summary", "Sans titre"),
            "start": event.get("start", {}),
            "end": event.get("end", {}),
            "description": event.get("description", ""),
            "htmlLink": event.get("htmlLink", ""),
        }
        for event in response.get("items", [])
    ]


def create_calendar_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    timezone: str = DEFAULT_TIMEZONE,
):
    """Crée un événement après validation des informations."""
    if not summary.strip():
        raise ValueError("Le titre de l'événement est obligatoire.")

    tz = ZoneInfo(timezone)
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)

    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=tz)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=tz)

    if end_dt <= start_dt:
        raise ValueError("La fin doit être postérieure au début.")

    event = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": timezone,
        },
    }

    return get_calendar_service().events().insert(
        calendarId="primary", body=event
    ).execute()


def update_calendar_event(
    event_id: str,
    summary: str | None = None,
    start: str | None = None,
    end: str | None = None,
    timezone: str = DEFAULT_TIMEZONE,
):
    """Modifie les champs fournis d'un événement existant."""
    service = get_calendar_service()
    event = service.events().get(
        calendarId="primary", eventId=event_id
    ).execute()

    if summary is not None:
        if not summary.strip():
            raise ValueError("Le titre ne peut pas être vide.")
        event["summary"] = summary

    tz = ZoneInfo(timezone)

    if start is not None:
        start_dt = datetime.fromisoformat(start)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=tz)
        event["start"] = {
            "dateTime": start_dt.isoformat(),
            "timeZone": timezone,
        }

    if end is not None:
        end_dt = datetime.fromisoformat(end)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=tz)
        event["end"] = {
            "dateTime": end_dt.isoformat(),
            "timeZone": timezone,
        }

    effective_start = datetime.fromisoformat(
        event["start"].get("dateTime", "")
    )
    effective_end = datetime.fromisoformat(
        event["end"].get("dateTime", "")
    )

    if effective_end <= effective_start:
        raise ValueError("La fin doit être postérieure au début.")

    return service.events().update(
        calendarId="primary",
        eventId=event_id,
        body=event,
    ).execute()


def delete_calendar_event(event_id: str):
    """Supprime un événement identifié par son ID."""
    get_calendar_service().events().delete(
        calendarId="primary",
        eventId=event_id,
    ).execute()

    return {"success": True, "event_id": event_id}
