import os
import json
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from tools.lebanese_calendar import get_occasion


def get_weather(meeting_date: str = None) -> dict:
    """
    Fetches weather for Beirut, Lebanon using OpenWeatherMap API.
    Falls back gracefully if API key is not set.
    """
    import requests

    api_key = os.getenv("OPENWEATHER_API_KEY", "")
    if not api_key or api_key.startswith("[INSERT"):
        return {
            "available":      False,
            "description":    "Weather data unavailable",
            "temperature":    None,
            "recommendation": "indoors/outdoors",
            "advisory":       None,
        }

    try:
        url    = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q":     "Beirut,LB",
            "appid": api_key,
            "units": "metric",
        }
        response = requests.get(url, params=params, timeout=5)
        data     = response.json()

        if response.status_code != 200:
            raise ValueError(f"API error: {data.get('message', 'unknown')}")

        weather_id   = data["weather"][0]["id"]
        description  = data["weather"][0]["description"].capitalize()
        temp         = round(data["main"]["temp"])
        feels_like   = round(data["main"]["feels_like"])

        if weather_id < 700:  # Rain, snow, thunderstorm
            recommendation = "indoors"
            advisory = f"Current weather: {description}, {temp}°C. Outdoor activities are not recommended today. All activities should be adapted for indoor use."
        elif temp < 10 or temp > 35:
            recommendation = "indoors"
            advisory = f"Current weather: {description}, {temp}°C (feels like {feels_like}°C). Temperature is outside comfortable range. Consider indoor alternatives."
        else:
            recommendation = "outdoors"
            advisory = f"Current weather: {description}, {temp}°C. Conditions are suitable for outdoor activities."

        return {
            "available":      True,
            "description":    description,
            "temperature":    temp,
            "feels_like":     feels_like,
            "recommendation": recommendation,
            "advisory":       advisory,
        }

    except Exception as e:
        return {
            "available":      False,
            "description":    "Weather data unavailable",
            "temperature":    None,
            "recommendation": "indoors/outdoors",
            "advisory":       None,
            "error":          str(e),
        }


def run_context_awareness_agent(meeting_date: str = None) -> dict:
    """
    Runs the context awareness checks and returns a context report.

    Args:
        meeting_date: Optional date string in DD/MM/YYYY format

    Returns:
        Dict with occasion and weather context
    """
    occasion = get_occasion(meeting_date)
    weather  = get_weather(meeting_date)

    context = {
        "meeting_date": meeting_date or datetime.today().strftime("%d/%m/%Y"),
        "occasion":     occasion,
        "weather":      weather,
        "advisories":   [],
    }

    if occasion["found"]:
        context["advisories"].append(
            f"Occasion: {occasion['name']} — {occasion['theme_suggestion']}"
        )

    if weather["advisory"]:
        context["advisories"].append(weather["advisory"])

    return context


if __name__ == "__main__":
    result = run_context_awareness_agent()
    print(json.dumps(result, indent=2))

    result2 = run_context_awareness_agent("22/04/2026")
    print(json.dumps(result2, indent=2))
