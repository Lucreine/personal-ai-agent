
import json
import os
import httpx

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

WEATHER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Consulte la météo actuelle d'une ville.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Nom de la ville.",
                    }
                },
                "required": ["city"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_forecast",
            "description": "Consulte les prévisions météo pour demain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                },
                "required": ["city"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_weather",
            "description": "Compare la météo actuelle de plusieurs villes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 5,
                    }
                },
                "required": ["cities"],
                "additionalProperties": False,
            },
        },
    }
]

TOOLS.extend(WEATHER_TOOLS)

def search_web( query: str, topic: str = "general", time_range: str | None = None ) -> str:
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


def _weather_request(endpoint: str, **params) -> dict:
    """Appelle WeatherAPI et vérifie les erreurs."""
    api_key = os.getenv("WEATHER_API_KEY")

    if not api_key:
        raise RuntimeError("La variable WEATHER_API_KEY est absente.")

    response = httpx.get(
        f"https://api.weatherapi.com/v1/{endpoint}.json",
        params={"key": api_key, **params},
        timeout=15.0,
    )
    response.raise_for_status()

    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", "Erreur WeatherAPI"))

    return data


def get_current_weather(city: str) -> str:
    """Retourne la météo actuelle d'une ville."""
    data = _weather_request("current", q=city)

    return json.dumps({
        "city": data["location"]["name"],
        "country": data["location"]["country"],
        "local_time": data["location"]["localtime"],
        "temperature_c": data["current"]["temp_c"],
        "feels_like_c": data["current"]["feelslike_c"],
        "condition": data["current"]["condition"]["text"],
        "humidity": data["current"]["humidity"],
        "wind_kph": data["current"]["wind_kph"],
    }, ensure_ascii=False)


def get_weather_forecast(city: str) -> str:
    """Retourne les prévisions météorologiques pour demain."""
    data = _weather_request("forecast", q=city, days=2)

    # La première journée peut être aujourd'hui ou une journée partielle.
    # La date de demain est obtenue à partir de l'heure locale du lieu.
    from datetime import date, timedelta

    local_date = date.fromisoformat(data["location"]["localtime"][:10])
    tomorrow = (local_date + timedelta(days=1)).isoformat()

    forecast = next(
        (
            day for day in data["forecast"]["forecastday"]
            if day["date"] == tomorrow
        ),
        None,
    )

    if forecast is None:
        raise RuntimeError("Les prévisions pour demain sont indisponibles.")

    return json.dumps({
        "city": data["location"]["name"],
        "country": data["location"]["country"],
        "date": forecast["date"],
        "condition": forecast["day"]["condition"]["text"],
        "min_temp_c": forecast["day"]["mintemp_c"],
        "max_temp_c": forecast["day"]["maxtemp_c"],
        "chance_of_rain": forecast["day"]["daily_chance_of_rain"],
    }, ensure_ascii=False)


def compare_weather(cities: list[str]) -> str:
    """Compare la météo actuelle de plusieurs villes."""
    if len(cities) < 2:
        raise ValueError("Indique au moins deux villes à comparer.")

    if len(cities) > 5:
        raise ValueError("Tu peux comparer cinq villes au maximum.")

    results = [
        json.loads(get_current_weather(city))
        for city in cities
    ]

    return json.dumps(results, ensure_ascii=False)
