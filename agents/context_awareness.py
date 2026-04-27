import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# ── Lebanese & Scouting Occasions Calendar ────────────────────────────────────

LEBANESE_OCCASIONS = {
    # Format: "MM-DD": {"name": ..., "type": ..., "suggestion": ...}
    "01-01": {"name": "New Year's Day",             "type": "national",  "suggestion": "Plan activities around new beginnings, goals, and hopes for the year."},
    "02-09": {"name": "Saint Maroun's Day",          "type": "national",  "suggestion": "Incorporate Lebanese heritage, culture, and community pride."},
    "03-08": {"name": "Women's Day",                 "type": "international", "suggestion": "Focus on equality, respect, and the contributions of women in scouting and society."},
    "03-25": {"name": "Lebanese Mother's Day",       "type": "national",  "suggestion": "Plan activities around appreciation, family values, and gratitude."},
    "04-22": {"name": "Earth Day",                   "type": "international", "suggestion": "Focus on environmental responsibility, Lebanese nature, and conservation."},
    "05-25": {"name": "Lebanese Liberation Day",     "type": "national",  "suggestion": "Incorporate themes of resilience, national pride, and community strength."},
    "08-04": {"name": "Beirut Port Explosion Memorial", "type": "national", "suggestion": "Reflect on community support, first aid, and helping those in need."},
    "09-01": {"name": "World Scouts Day",            "type": "scouting",  "suggestion": "Celebrate scouting values, the Scout Promise, and the global scouting community."},
    "10-22": {"name": "Lebanese Independence Day Eve", "type": "national", "suggestion": "Incorporate Lebanese heritage activities and national pride themes."},
    "11-22": {"name": "Lebanese Independence Day",   "type": "national",  "suggestion": "Focus on Lebanese identity, history, and civic responsibility."},
    "12-25": {"name": "Christmas",                   "type": "religious", "suggestion": "Plan inclusive activities around giving, community, and kindness."},
}

UPCOMING_WINDOW_DAYS = 7


def check_occasion(meeting_date: str = None) -> dict:
    """
    Checks if the meeting date falls on or near a Lebanese or scouting occasion.

    Args:
        meeting_date: Date string in DD/MM/YYYY format, or None for today

    Returns:
        Dict with occasion info or None
    """
    try:
        if meeting_date:
            date = datetime.strptime(meeting_date, "%d/%m/%Y")
        else:
            date = datetime.today()
    except ValueError:
        date = datetime.today()

    month_day = date.strftime("%m-%d")

    if month_day in LEBANESE_OCCASIONS:
        occasion = LEBANESE_OCCASIONS[month_day]
        return {
            "found":      True,
            "name":       occasion["name"],
            "type":       occasion["type"],
            "suggestion": occasion["suggestion"],
            "date":       date.strftime("%d/%m/%Y"),
        }

    return {"found": False, "name": None, "type": None, "suggestion": None}


def get_weather(meeting_date: str = None) -> dict:
    """
    Fetches weather for Beirut, Lebanon using OpenWeatherMap API.
    Falls back gracefully if API key is not set.

    Returns:
        Dict with weather info and indoor/outdoor recommendation
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

        # Determine indoor/outdoor recommendation
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
    occasion = check_occasion(meeting_date)
    weather  = get_weather(meeting_date)

    context = {
        "meeting_date": meeting_date or datetime.today().strftime("%d/%m/%Y"),
        "occasion":     occasion,
        "weather":      weather,
        "advisories":   [],
    }

    if occasion["found"]:
        context["advisories"].append(
            f"Occasion: {occasion['name']} — {occasion['suggestion']}"
        )

    if weather["advisory"]:
        context["advisories"].append(weather["advisory"])

    return context


if __name__ == "__main__":
    # Test with today's date
    result = run_context_awareness_agent()
    print(json.dumps(result, indent=2))

    # Test with a specific occasion date
    result2 = run_context_awareness_agent("22/04/2026")
    print(json.dumps(result2, indent=2))