import json

from langchain_core.messages import HumanMessage, SystemMessage
from agents.base import get_llm, get_unit_config, ACTIVITY_TYPES, BOOKEND_MINUTES, _cb

SYSTEM_PROMPT = """You are the Educational Design Agent for ScoutMind, a meeting planning
system for the Lebanese Scouts Association.

Your sole responsibility is to design the sequence and structure of activities for a
scout meeting. You apply evidence-based educational therapy principles to ensure
the meeting is pedagogically sound and age-appropriate.

You must follow these rules strictly:
1. The meeting ALWAYS starts with a high-energy game after the opening ceremony.
2. The meeting ALWAYS ends with a high-energy game before the reflection circle.
3. Between those bookends, sequence activities to manage cognitive load effectively:
   - Alternate between high-energy and lower-energy activities.
   - Never place two lectures or two skill activities back to back.
   - Place cognitively demanding activities in the middle third of the meeting.
4. For Beavers (3-7): maximum 3 cognitive activities, insert energiser breaks every 15 minutes.
5. For Cubs (7-11): balance physical and cognitive activities roughly 60/40.
6. For older units (11+): can handle longer cognitive stretches but still alternate.
7. Apply educational therapy techniques: Think-Pair-Share in discussions, Scaffolded
   Learning in skills, Multisensory elements where possible, Reflective Journaling at end.

You must respond ONLY with a valid JSON object. No explanation, no preamble, no markdown.

The JSON must follow this exact structure:
{
  "sequence": [
    {
      "slot": 1,
      "activity_type": "game",
      "energy_level": "high",
      "duration_minutes": 15,
      "theme_focus": "brief description of what this slot should achieve",
      "educational_technique": "technique name or null",
      "placement_reason": "why this activity type is placed here"
    }
  ],
  "total_content_minutes": 150,
  "educational_notes": "overall pedagogical rationale for this sequence"
}"""

def run_educational_design_agent(
    unit: str,
    theme: str,
    total_content_minutes: int,
    custom_duration: int = None,
) -> dict:
    """
    Designs the activity sequence for a scout meeting.

    Args:
        unit:                   Scout unit name
        theme:                  Meeting theme
        total_content_minutes:  Available content minutes (after removing bookends)
        custom_duration:        Optional custom total meeting duration in minutes

    Returns:
        Dict with sequence and educational notes
    """
    llm    = get_llm(temperature=0.5)
    config = get_unit_config(unit)

    if custom_duration:
        total_content_minutes = custom_duration - BOOKEND_MINUTES

    _cb("Educational Design Agent", f"Calculating content time for {unit}: {total_content_minutes} minutes available after bookends...", "running")

    activity_type_info = "\n".join([
        f"- {k}: {v['duration_range'][0]}-{v['duration_range'][1]} minutes"
        for k, v in ACTIVITY_TYPES.items()
    ])

    user_message = f"""Design the activity sequence for the following scout meeting:

Unit: {unit}
Unit Description: {config['description']}
Theme: {theme}
Total content minutes available: {total_content_minutes} minutes
(This excludes the fixed 15-minute opening ceremony and 15-minute reflection circle)

Available activity types and their durations:
{activity_type_info}

Requirements:
- Fill exactly {total_content_minutes} minutes of content (±5 minutes tolerance)
- First activity MUST be a high-energy game
- Last activity MUST be a high-energy game
- Apply appropriate educational therapy techniques throughout
- All activities must be appropriate for {unit} (ages {config['age_range'][0]}-{config['age_range'][1]})
- Theme: {theme} — activities should connect to or reinforce this theme where possible

Respond with the JSON sequence only."""

    _cb("Educational Design Agent", f"Sending sequence design request to Claude for theme: {theme}...", "running")

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    content  = response.content.strip()

    # Strip markdown fences if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()

    result = json.loads(content)
    result["unit"]  = unit
    result["theme"] = theme

    # Enforce duration: if the LLM under-filled, pad with short games until exact
    sequence  = result.get("sequence", [])
    shortfall = total_content_minutes - sum(s.get("duration_minutes", 0) for s in sequence)
    if shortfall >= 5:
        _cb("Educational Design Agent", f"Enforcing duration constraints: padding {shortfall} minutes with filler activities...", "running")
    while shortfall >= 5:
        duration = 15 if shortfall >= 15 else 10 if shortfall >= 10 else 5
        sequence.append({
            "slot":                len(sequence) + 1,
            "activity_type":       "game",
            "energy_level":        "high",
            "duration_minutes":    duration,
            "theme_focus":         f"Energising reinforcement activity connecting to the theme: {theme}",
            "educational_technique": None,
            "placement_reason":    "Added to reach the required content duration",
        })
        shortfall -= duration

    # Re-number all slots sequentially
    for i, slot in enumerate(sequence):
        slot["slot"] = i + 1

    result["sequence"]               = sequence
    result["total_content_minutes"]  = total_content_minutes
    return result

if __name__ == "__main__":
    result = run_educational_design_agent(
        unit="Cubs",
        theme="Friendship",
        total_content_minutes=150,
    )
    print(json.dumps(result, indent=2))