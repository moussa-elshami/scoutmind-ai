import json

from langchain_core.messages import HumanMessage, SystemMessage
from agents.base import get_llm, get_unit_config, _cb
from rag.retriever import retrieve_activities, retrieve_techniques


SYSTEM_PROMPT = """You are the Activity Generator Agent for ScoutMind, a meeting planning
system for the Lebanese Scouts Association.

Your sole responsibility is to write complete, professional, detailed descriptions
for each activity in a scout meeting plan.

For every activity you must produce:
1. A clear, engaging activity name
2. The precise objective (what members will learn or achieve)
3. Step-by-step instructions (numbered, detailed enough for any leader to follow)
4. A complete materials list specific to this activity
5. An educational technique note (how a therapy/learning technique is embedded)
6. Leader tips (what to watch for, common mistakes, adaptations)

Your descriptions must be:
- Professional and print-ready
- Specific to the unit's age group
- Connected to the meeting theme
- Practical and realistic for a Lebanese scout meeting context

You must respond ONLY with a valid JSON object. No explanation, no preamble, no markdown.

The JSON must follow this exact structure:
{
  "activities": [
    {
      "slot": 1,
      "activity_name": "Full Activity Name",
      "activity_type": "game",
      "duration_minutes": 15,
      "energy_level": "high",
      "objective": "Clear statement of what members will achieve",
      "instructions": [
        "Step 1: ...",
        "Step 2: ...",
        "Step 3: ..."
      ],
      "materials": [
        "Item 1 (quantity)",
        "Item 2 (quantity)"
      ],
      "educational_technique": {
        "name": "technique name",
        "application": "how it is applied in this specific activity"
      },
      "leader_tips": "Practical advice for the leader running this activity",
      "theme_connection": "How this activity connects to the meeting theme"
    }
  ],
  "master_materials_list": [
    "Consolidated item 1",
    "Consolidated item 2"
  ]
}"""


def run_activity_generator_agent(
    unit: str,
    theme: str,
    selected_activities: list,
    techniques: list = None,
) -> dict:
    """
    Generates full activity descriptions for each slot.

    Args:
        unit:                Scout unit name
        theme:               Meeting theme
        selected_activities: List of selected activities from Scouting Context Agent
        techniques:          Optional list of educational techniques from RAG

    Returns:
        Dict with fully described activities and master materials list
    """
    llm    = get_llm(temperature=0.7)
    config = get_unit_config(unit)

    # Retrieve educational techniques for this unit
    _cb("Activity Generator Agent", "Retrieving educational techniques from knowledge base...", "running")
    if not techniques:
        techniques = retrieve_techniques(theme, unit, n_results=4)

    # Retrieve full activity details from RAG for knowledge-base activities
    _cb("Activity Generator Agent", f"Loading knowledge base details for {len(selected_activities)} activities...", "running")
    kb_activities = {}
    for act in selected_activities:
        if act.get("source") == "knowledge_base" and act.get("activity_id", "").startswith("ACT"):
            results = retrieve_activities(act["activity_name"], unit, n_results=3)
            for r in results:
                if r["id"] == act["activity_id"]:
                    kb_activities[act["activity_id"]] = r
                    break

    techniques_summary = "\n".join([
        f"- {t['name']}: {t.get('scouting_adaptation', '')[:150]}"
        for t in techniques[:4]
    ]) if techniques else "Apply Think-Pair-Share, Scaffolded Learning, and Reflective Journaling."

    user_message = f"""Generate complete activity descriptions for this scout meeting:

Unit: {unit} (ages {config['age_range'][0]}-{config['age_range'][1]}, {config['gender']})
Theme: {theme}

ACTIVITIES TO DESCRIBE:
{json.dumps(selected_activities, indent=2)}

KNOWLEDGE BASE DETAILS (use these as the basis where available):
{json.dumps(kb_activities, indent=2)}

EDUCATIONAL TECHNIQUES TO INCORPORATE:
{techniques_summary}

Requirements:
- Keep instructions to 4-6 clear numbered steps maximum
- Materials must be specific with quantities
- Each activity must clearly connect to the theme: {theme}
- Age group: {unit} ({config['age_range'][0]}-{config['age_range'][1]} years)
- Leader tips: 1-2 sentences maximum
- Include a master_materials_list consolidating ALL materials
- Be concise but complete — quality over length

Respond with valid JSON only. No markdown, no preamble."""

    _cb("Activity Generator Agent", f"Sending generation request to Claude for {len(selected_activities)} activities...", "running")

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    content  = response.content.strip()

    _cb("Activity Generator Agent", "Parsing and validating JSON response...", "running")

    # Strip markdown fences
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()

    # Try direct parse first
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        # Extract JSON between first { and last }
        start = content.find("{")
        end   = content.rfind("}") + 1
        if start != -1 and end > start:
            try:
                result = json.loads(content[start:end])
            except json.JSONDecodeError:
                # Final fallback: retry all activities with stricter brevity constraints
                fallback_msg = f"""The previous response had JSON formatting issues.
Generate descriptions for ALL {len(selected_activities)} activities from this list:
{json.dumps(selected_activities, indent=2)}

Unit: {unit}, Theme: {theme}
STRICT LIMITS: instructions max 4 steps, leader_tips max 1 sentence, objective max 1 sentence.
Respond with valid JSON only."""
                fallback_response = llm.invoke([
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=fallback_msg),
                ])
                fallback_content = fallback_response.content.strip()
                if fallback_content.startswith("```"):
                    fallback_content = fallback_content.split("```")[1]
                    if fallback_content.startswith("json"):
                        fallback_content = fallback_content[4:]
                result = json.loads(fallback_content.strip())
        else:
            raise ValueError("Could not extract valid JSON from response.")

    result["unit"]  = unit
    result["theme"] = theme

    # Re-attach source metadata from selected_activities so it flows to the formatter
    slot_to_meta = {
        a.get("slot"): {"source": a.get("source", "generated"), "activity_id": a.get("activity_id", "NEW")}
        for a in selected_activities
    }
    for act in result.get("activities", []):
        meta = slot_to_meta.get(act.get("slot"), {})
        act["source"]      = meta.get("source", "generated")
        act["activity_id"] = meta.get("activity_id", "NEW")

    return result


if __name__ == "__main__":
    test_selected = [
        {
            "slot": 1,
            "activity_id": "ACT021",
            "activity_name": "Energiser: Zip Zap Boing",
            "activity_type": "game",
            "duration_minutes": 10,
            "energy_level": "high",
            "source": "knowledge_base",
        },
        {
            "slot": 2,
            "activity_id": "ACT011",
            "activity_name": "Friendship Web Discussion",
            "activity_type": "lecture",
            "duration_minutes": 20,
            "energy_level": "low",
            "source": "knowledge_base",
        },
    ]
    result = run_activity_generator_agent("Cubs", "Friendship", test_selected)
    print(json.dumps(result, indent=2))