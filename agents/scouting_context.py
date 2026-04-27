import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, SystemMessage
from agents.base import get_llm, get_unit_config
from rag.retriever import retrieve_for_meeting


SYSTEM_PROMPT = """You are the Scouting Context Agent for ScoutMind, a meeting planning
system for the Lebanese Scouts Association.

Your sole responsibility is to ensure every activity in a meeting plan is:
1. Aligned with Lebanese scouting values and traditions
2. Age and gender appropriate for the specific unit
3. Grounded in the scouting method: learning by doing, patrol system, outdoor activities
4. Culturally sensitive to the Lebanese context
5. Connected to the Scout Promise and Scout Law where appropriate

You receive a proposed activity sequence and a pool of retrieved activities from the
knowledge base. Your job is to:
- Select the most appropriate activity from the pool for each sequence slot
- If no suitable activity exists in the pool, propose a new one that fits
- Ensure gender-appropriate content for single-gender units
- Flag any activities that conflict with scouting values

You must respond ONLY with a valid JSON object. No explanation, no preamble, no markdown.

The JSON must follow this exact structure:
{
  "selected_activities": [
    {
      "slot": 1,
      "activity_id": "ACT001 or NEW",
      "activity_name": "name",
      "activity_type": "game",
      "duration_minutes": 15,
      "energy_level": "high",
      "source": "knowledge_base or generated",
      "scouting_alignment": "how this aligns with scouting values",
      "age_appropriateness": "why this is suitable for the unit"
    }
  ],
  "context_notes": "overall scouting context rationale"
}"""


def run_scouting_context_agent(
    unit: str,
    theme: str,
    sequence: list,
    occasion: str = None,
    weather: str = None,
) -> dict:
    """
    Selects appropriate activities for each sequence slot based on scouting context.

    Args:
        unit:      Scout unit name
        theme:     Meeting theme
        sequence:  Activity sequence from Educational Design Agent
        occasion:  Optional Lebanese/scouting occasion (e.g. 'Independence Day')
        weather:   Optional weather description (e.g. 'rainy, 15°C')

    Returns:
        Dict with selected activities and context notes
    """
    llm    = get_llm(temperature=0.6)
    config = get_unit_config(unit)

    # Retrieve relevant activities from RAG
    content_minutes = sum(s.get("duration_minutes", 15) for s in sequence)
    rag_data        = retrieve_for_meeting(theme, unit, content_minutes)

    # Build a compact summary of available activities for the prompt
    available = []
    for activity in rag_data["activities"]["all"][:15]:
        available.append({
            "id":           activity["id"],
            "name":         activity["name"],
            "type":         activity["type"],
            "duration":     activity["duration"],
            "energy_level": activity["energy_level"],
            "location":     activity["location"],
            "themes":       activity["themes"],
            "objective":    activity["objective"][:100] + "...",
        })

    occasion_note = f"\nSpecial occasion: {occasion}" if occasion else ""
    weather_note  = f"\nWeather conditions: {weather}" if weather else ""

    user_message = f"""Select appropriate activities for each slot in this scout meeting:

Unit: {unit} (ages {config['age_range'][0]}-{config['age_range'][1]}, {config['gender']})
Theme: {theme}{occasion_note}{weather_note}

ACTIVITY SEQUENCE TO FILL:
{json.dumps(sequence, indent=2)}

AVAILABLE ACTIVITIES FROM KNOWLEDGE BASE:
{json.dumps(available, indent=2)}

Instructions:
- Match each slot's activity_type and energy_level requirements
- Prefer activities from the knowledge base (use their ID)
- If no suitable match exists, set activity_id to "NEW" and propose one
- For outdoor activities, consider weather conditions if provided
- For special occasions, incorporate them into activity selection where natural
- Ensure all activities connect to the theme: {theme}
- Gender: {config['gender']} — ensure appropriateness

Respond with the JSON only."""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    content  = response.content.strip()

    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()

    result = json.loads(content)
    result["unit"]          = unit
    result["theme"]         = theme
    result["rag_pool_size"] = len(available)
    return result


if __name__ == "__main__":
    # Quick test
    test_sequence = [
        {"slot": 1, "activity_type": "game",    "energy_level": "high",   "duration_minutes": 15, "theme_focus": "energise group"},
        {"slot": 2, "activity_type": "lecture",  "energy_level": "low",    "duration_minutes": 20, "theme_focus": "discuss friendship values"},
        {"slot": 3, "activity_type": "skill",    "energy_level": "low",    "duration_minutes": 15, "theme_focus": "knot tying"},
        {"slot": 4, "activity_type": "game",     "energy_level": "high",   "duration_minutes": 10, "theme_focus": "close with energy"},
    ]
    result = run_scouting_context_agent("Cubs", "Friendship", test_sequence)
    print(json.dumps(result, indent=2))