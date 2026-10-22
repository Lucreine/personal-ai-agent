
import json
import os

from tavily import TavilyClient


# Définition de l'outil que le LLM pourra choisir.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Recherche des informations actuelles sur Internet. "
                "Utilise cet outil pour les actualités récentes, les événements, "
                "les informations susceptibles d'avoir changé et les questions "
                "qui nécessitent des sources en ligne."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Le sujet précis à rechercher sur Internet.",
                    },
                    "topic": {
                        "type": "string",
                        "enum": ["general", "news"],
                        "description": (
                            "general pour une recherche classique, "
                            "news pour les actualités."
                        ),
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["day", "week", "month", "year"],
                        "description": (
                            "Période de recherche : jour, semaine, mois ou année."
                        ),
                    },
                },
                "required": ["query", "topic"],
                "additionalProperties": False,
            },
        },
    }
]


def search_web(
    query: str,
    topic: str = "general",
    time_range: str | None = None,
) -> str:
    """Effectue une recherche Internet et renvoie les résultats avec leurs sources."""

    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise RuntimeError("La variable TAVILY_API_KEY est absente.")

    client = TavilyClient(api_key=api_key)

    options = {
        "query": query,
        "topic": topic,
        "max_results": 5,
        "search_depth": "basic",
    }

    if time_range:
        options["time_range"] = time_range

    response = client.search(**options)

    results = [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "published_date": item.get("published_date"),
        }
        for item in response.get("results", [])
    ]

    return json.dumps(
        {
            "query": query,
            "topic": topic,
            "results": results,
        },
        ensure_ascii=False,
    )
