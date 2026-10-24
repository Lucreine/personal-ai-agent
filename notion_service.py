
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_VERSION = os.getenv("NOTION_VERSION", "2026-03-11")
NOTION_API_URL = "https://api.notion.com/v1"


def _headers() -> dict:
    if not NOTION_TOKEN:
        raise RuntimeError("La variable NOTION_TOKEN est absente du fichier .env")

    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def search_notion_pages(query: str, page_size: int = 10) -> str:
    """Recherche les pages Notion accessibles à l'intégration."""
    query = query.strip()
    if not query:
        return "Indique un sujet ou un mot-clé à rechercher dans Notion."

    response = httpx.post(
        f"{NOTION_API_URL}/search",
        headers=_headers(),
        json={
            "query": query,
            "filter": {"property": "object", "value": "page"},
            "page_size": min(max(page_size, 1), 20),
        },
        timeout=20,
    )
    response.raise_for_status()

    results = response.json().get("results", [])
    if not results:
        return f"Aucune page Notion trouvée pour : {query}"

    pages = []
    for page in results:
        properties = page.get("properties", {})
        title = "Sans titre"

        for prop in properties.values():
            if prop.get("type") == "title":
                title_parts = prop.get("title", [])
                title = "".join(
                    item.get("plain_text", "") for item in title_parts
                ) or title
                break

        pages.append({
            "id": page["id"],
            "title": title,
            "url": page.get("url", ""),
        })

    return "\n".join(
        f"- {page['title']} (ID: {page['id']})\n  URL: {page['url']}"
        for page in pages
    )

def _get_block_text(block: dict) -> str:
    """Extrait le texte d'un bloc Notion."""
    block_type = block.get("type", "")
    data = block.get(block_type, {})

    if block_type in ("child_page", "child_database"):
        return data.get("title", "")

    rich_text = data.get("rich_text", data.get("title", []))

    if isinstance(rich_text, str):
        return rich_text

    return "".join(
        item.get("plain_text", "")
        for item in rich_text
        if isinstance(item, dict)
    )


def get_notion_page_content(page_id: str, max_blocks: int = 100) -> str:
    """Récupère le contenu textuel d'une page Notion."""
    response = httpx.get(
        f"{NOTION_API_URL}/blocks/{page_id}/children",
        headers=_headers(),
        params={"page_size": min(max(max_blocks, 1), 100)},
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    blocks = data.get("results", [])
    lines = []

    for block in blocks:
        text = _get_block_text(block)
        if text:
            lines.append(text)

        # Lire aussi les blocs enfants, par exemple les listes imbriquées.
        if block.get("has_children") and len(lines) < max_blocks:
            child_content = get_notion_page_content(block["id"], max_blocks=30)
            if child_content:
                lines.append(child_content)

    if data.get("has_more"):
        lines.append(
            "[Note : la page contient d'autres blocs qui n'ont pas été chargés.]"
        )

    return "\n".join(lines) or "Cette page ne contient pas de texte lisible."
