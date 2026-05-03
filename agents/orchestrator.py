import json
import re
from typing import TypedDict, Optional
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base import get_llm, get_unit_config, _active_callback, _cb, BOOKEND_MINUTES
from agents.educational_design  import run_educational_design_agent
from agents.scouting_context     import run_scouting_context_agent
from agents.activity_generator   import run_activity_generator_agent
from agents.context_awareness    import run_context_awareness_agent
from agents.validation           import run_validation_agent
from agents.formatting           import run_formatting_agent, plan_to_text, plan_to_markdown
from tools.time_validator        import validate_timing
from tools.plan_evaluator        import evaluate_plan

# State Definition 

class MeetingPlanState(TypedDict):
    # Inputs
    unit:             str
    theme:            str
    meeting_date:     Optional[str]
    custom_duration:  Optional[int]
    user_messages:    list
    conversation_history: list

    # Agent outputs
    context:          Optional[dict]
    sequence:         Optional[list]
    selected:         Optional[dict]
    generated:        Optional[dict]
    validation:       Optional[dict]
    plan:             Optional[dict]
    plan_text:        Optional[str]

    # Scheduling
    meeting_start_time: Optional[str]

    # Pipeline control
    current_agent:    str
    agent_thoughts:   list
    is_complete:      bool
    error:            Optional[str]
    needs_more_info:  bool
    clarification_question: Optional[str]


# Conversational Gate 

CONVERSATION_SYSTEM_PROMPT = """You are ScoutMind, an intelligent meeting planning assistant
for the Lebanese Scouts Association. You specialise in generating professional weekly meeting
plans for Lebanese scout units, and in helping leaders choose units, themes, and dates.

You are helpful, warm, and professional. You speak in clear prose — no bullet points,
no numbered lists, no emojis. You ask one clarifying question at a time when needed.

Units you support:
Beavers (Mixed, ages 3-7, 3-hour meetings),
Cubs (Mixed, ages 7-11, 3-hour meetings),
Girl Scouts (Girls, ages 11-16, 4-hour meetings),
Boy Scouts (Boys, ages 11-16, 4-hour meetings),
Pioneers (Girls, ages 16-19, 4-hour meetings),
Rovers (Boys, ages 16-19, 4-hour meetings).

Only decline and redirect if the user asks about something with NO connection to scouting
(e.g. homework help, cooking recipes, news). Questions about scouting units, scout
activities, themes, the LSA programme, meeting ideas, or unit characteristics are all
ON-TOPIC and must be answered helpfully.

CRITICAL HISTORY READING: Read the entire conversation history before responding.
If the user has mentioned a unit name at any point — even if they just said "cubs" or
"I'm leading Cubs" or "for my Cubs unit" — that IS the unit. Do not ask for it again.
Similarly, if a theme has been mentioned anywhere, do not ask for it again.

Follow this exact decision flow:

STEP 0 — If the user asks for suggestions, ideas, examples, OR information about scouting
  (e.g. "what themes can I use?", "what do each unit like?", "what activities suit Cubs?",
  "tell me about the units", "what kinds of themes work for Beavers?"): answer helpfully
  in 2-3 sentences of prose about the specific topic, then end with a gentle prompt to
  move forward. This step applies to ANY scouting knowledge question.
  -> ready_to_generate: false

STEP 1 — Check history AND the current message for unit and theme.
  - If ONLY the unit is missing: ask for the unit only.
  - If ONLY the theme is missing: ask for the theme only.
  - If BOTH are missing: ask for both in one sentence.
  Never ask for something already established in the conversation.
  -> ready_to_generate: false

STEP 2 — If unit and theme are both clear but no date has been mentioned yet:
  ask ONE question about the date only, explaining it helps with weather and
  Lebanese occasion context. If not, you will use today. Do NOT ask anything else.
  -> ready_to_generate: false

STEP 3 — If unit and theme are clear AND either a date was provided or the user
  said they do not have one or they said today or any similar response:
  generate immediately. No further questions.
  -> ready_to_generate: true

Never ask "shall I generate now?" — that is not a valid question.
Never ask more than one question per response.
Never use emojis or bullet points.

PDF EXPORT: Once a plan has been generated, a "Download as PDF" button appears automatically
below the plan in the UI. If the user asks about downloading or saving the plan as a PDF,
tell them to scroll down to find the button directly beneath the generated plan.

CRITICAL: Every single response MUST be a valid JSON object with BOTH "ready_to_generate"
AND "response" keys. Never omit the "response" key. Never respond with plain prose.

When ready to generate, respond with EXACTLY this JSON and nothing else:
{
  "ready_to_generate": true,
  "unit": "Cubs",
  "theme": "Friendship",
  "meeting_date": "27/04/2026",
  "custom_duration": null,
  "meeting_start_time": null,
  "response": "One sentence confirming what you are generating — no emojis"
}

IMPORTANT:
- custom_duration must be an INTEGER number of minutes (e.g. 180 for 3 hours, 240 for 4 hours) or null. Never a string, never a description.
- meeting_start_time must be a 24-hour "HH:MM" string (e.g. "13:00" for 1:00 PM, "09:00" for 9:00 AM) or null if the user did not mention a start time.

For ALL other responses (clarifying questions, suggestions, information, off-topic redirects),
you MUST include the "response" key:
{
  "ready_to_generate": false,
  "response": "Your helpful prose response here — no emojis, no bullet points"
}

Examples of correct behaviour when context is established in history:
- User said "I'm leading Cubs" earlier, now says "I want a nature theme" →
  {"ready_to_generate": false, "response": "Wonderful. Do you have a date in mind for your Cubs nature meeting, or shall I use today?"}
- User said "Cubs" and "friendship" but no date →
  {"ready_to_generate": false, "response": "Do you have a date in mind for your Cubs friendship meeting? If not, I will use today."}
- User says "no date" or "today" after being asked →
  {"ready_to_generate": true, "unit": "Cubs", "theme": "Friendship", "meeting_date": null, ...}"""


_UNIT_ALIASES: dict[str, str] = {
    "beavers": "Beavers", "beaver": "Beavers",
    "cubs": "Cubs", "cub": "Cubs",
    "girl scouts": "Girl Scouts", "girl scout": "Girl Scouts",
    "boy scouts": "Boy Scouts", "boy scout": "Boy Scouts",
    "pioneers": "Pioneers", "pioneer": "Pioneers",
    "rovers": "Rovers", "rover": "Rovers",
}


def _extract_unit_from_history(history: list, current_message: str = "") -> str | None:
    """Scan conversation history and current message for an explicit unit mention."""
    all_texts = [current_message] + [
        (m.get("content", "") or "") for m in history if m.get("role") == "user"
    ]
    for text in all_texts:
        lower = text.lower()
        # Check multi-word aliases first (e.g. "girl scouts" before "scouts")
        for alias in sorted(_UNIT_ALIASES, key=len, reverse=True):
            if alias in lower:
                return _UNIT_ALIASES[alias]
    return None


def run_conversation_agent(
    user_message: str,
    conversation_history: list,
    user_unit: str = None,
) -> dict:
    """
    Handles conversational interaction before generation.
    Returns dict with ready_to_generate flag and parsed inputs.
    """
    from langchain_core.messages import AIMessage
    llm = get_llm(temperature=0.7)

    # Inject today's date so relative expressions like "upcoming Saturday" resolve correctly
    today_str = datetime.now().strftime("%A, %d/%m/%Y")
    system_content = CONVERSATION_SYSTEM_PROMPT + f"\n\nToday's date is {today_str}. Use this to resolve relative date expressions (e.g. 'upcoming Saturday', 'next week') into exact DD/MM/YYYY dates."

    # Determine the effective unit: first check explicit mentions, then fall back to registration
    detected_unit = _extract_unit_from_history(conversation_history or [], user_message)
    effective_unit = detected_unit or user_unit

    if effective_unit:
        system_content += (
            f"\n\nCONTEXT REMINDER: The unit for this conversation is '{effective_unit}'. "
            f"This is already established — do NOT ask the user which unit they lead. "
            f"Your only remaining question (if needed) is the theme, then the date."
        )

    # Build strictly alternating message history for Claude
    # Rule: SystemMessage first, then ONLY Human/AI alternating, ending with HumanMessage
    # Claude rejects: consecutive system messages, consecutive same-role messages

    history = conversation_history[-20:] if conversation_history else []

    # Patterns that indicate a stuck/looping assistant response — sanitize before sending
    _stuck_markers = [
        "could you tell me which unit you're leading and the theme",
        "could you tell me which unit you are leading and the theme",
        "i'm here to help you plan your scout meeting",
        "i am here to help you plan your scout meeting",
    ]

    def _is_stuck_response(text: str) -> bool:
        lower = text.lower()
        return any(m in lower for m in _stuck_markers)

    # Step 1: Flatten history into simple (role, text) tuples
    # Map all non-user roles to "assistant", truncate long content
    flat = []
    for msg in history:
        role = msg.get("role", "")
        text = (msg.get("content", "") or "").strip()
        if not text:
            continue
        if role == "user":
            flat.append(("user", text[:500]))
        elif role == "assistant":
            # Replace stuck loop messages so they don't prime the model to loop again
            sanitized = "I need a bit more information to generate your plan." if _is_stuck_response(text) else text[:300]
            flat.append(("assistant", sanitized))
        elif role == "plan":
            # Replace full plan with a short summary to avoid token bloat
            flat.append(("assistant", "I have generated the meeting plan as requested."))
        # Skip all other roles

    # Step 2: Drop leading assistant messages (must start with user)
    while flat and flat[0][0] == "assistant":
        flat.pop(0)

    # Step 3: Remove ALL consecutive same-role messages (keep first of each run)
    deduped = []
    for role, text in flat:
        if deduped and deduped[-1][0] == role:
            continue  # skip duplicate
        deduped.append((role, text))

    # Step 4: Ensure sequence ends with assistant before we add new user message
    # (already handled by appending HumanMessage at end)

    # Step 5: Build final Claude message list
    messages = [SystemMessage(content=system_content)]
    for role, text in deduped:
        if role == "user":
            messages.append(HumanMessage(content=text))
        else:
            messages.append(AIMessage(content=text))

    # Always end with the new user message
    messages.append(HumanMessage(content=user_message))

    response = llm.invoke(messages)
    content  = response.content.strip()

    # Strip markdown fences if present
    if "```" in content:
        parts = content.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("{"):
                content = stripped
                break

    content = content.strip()

    if effective_unit:
        _safe_default = f"I have noted your {effective_unit} unit. What theme would you like for your meeting?"
    else:
        _safe_default = "Which unit are you planning for, and what theme would you like for the meeting?"

    def _ensure_response(d: dict) -> dict:
        if "response" not in d:
            d["response"] = _safe_default
        return d

    # Try direct parse
    try:
        return _ensure_response(json.loads(content))
    except json.JSONDecodeError:
        pass

    # Try extracting JSON object from anywhere in the response
    start = content.find("{")
    end   = content.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return _ensure_response(json.loads(content[start:end]))
        except json.JSONDecodeError:
            pass

    # Fallback: use prose that precedes the broken JSON if substantial
    if start > 20:
        prose = content[:start].strip()
        if len(prose) >= 20:
            return {"ready_to_generate": False, "response": prose}

    # Last resort: use whatever the model returned rather than a generic hardcoded message
    if content and len(content) >= 10:
        return {"ready_to_generate": False, "response": content[:600]}

    return {
        "ready_to_generate": False,
        "response": "Could you tell me which unit you are leading and the theme for your meeting?",
    }


# Agent Node Functions 

def node_context_awareness(state: MeetingPlanState) -> MeetingPlanState:
    """Node 1: Check weather and occasions."""
    state["current_agent"] = "Context Awareness Agent"
    running_thought = f"Checking weather in Beirut and Lebanese calendar for {state.get('meeting_date', 'today')}..."
    state["agent_thoughts"].append({"agent": "Context Awareness Agent", "thought": running_thought, "status": "running"})
    _cb("Context Awareness Agent", running_thought, "running")
    try:
        context = run_context_awareness_agent(state.get("meeting_date"))
        state["context"] = context
        thought_text = f"Weather: {context['weather']['description']}. "
        if context["occasion"]["found"]:
            thought_text += f"Occasion detected: {context['occasion']['name']}. "
        thought_text += f"Generated {len(context['advisories'])} advisory/advisories."
        state["agent_thoughts"][-1]["thought"] = thought_text
        state["agent_thoughts"][-1]["status"]  = "done"
        _cb("Context Awareness Agent", thought_text, "done")
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Context Awareness Agent failed: {str(e)}"
        _cb("Context Awareness Agent", str(e), "error")
    return state


def node_educational_design(state: MeetingPlanState) -> MeetingPlanState:
    """Node 2: Design activity sequence."""
    state["current_agent"] = "Educational Design Agent"
    unit   = state["unit"]
    theme  = state["theme"]
    config = get_unit_config(unit)
    content_minutes = (state.get("custom_duration") or config["meeting_duration"]) - BOOKEND_MINUTES
    running_thought = f"Designing activity sequence for {unit} unit ({content_minutes} minutes of content) on theme: {theme}. Applying educational therapy frameworks..."
    state["agent_thoughts"].append({"agent": "Educational Design Agent", "thought": running_thought, "status": "running"})
    _cb("Educational Design Agent", running_thought, "running")
    try:
        result = run_educational_design_agent(
            unit=unit, theme=theme,
            total_content_minutes=content_minutes,
            custom_duration=state.get("custom_duration"),
        )
        state["sequence"] = result.get("sequence", [])
        done_thought = (
            f"Designed {len(state['sequence'])} activity slots. "
            f"First: {state['sequence'][0]['activity_type'] if state['sequence'] else 'N/A'}, "
            f"Last: {state['sequence'][-1]['activity_type'] if state['sequence'] else 'N/A'}. "
            f"Educational rationale: {result.get('educational_notes', '')[:100]}..."
        )
        state["agent_thoughts"][-1]["thought"] = done_thought
        state["agent_thoughts"][-1]["status"]  = "done"
        _cb("Educational Design Agent", done_thought, "done")
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Educational Design Agent failed: {str(e)}"
        _cb("Educational Design Agent", str(e), "error")
    return state


def node_scouting_context(state: MeetingPlanState) -> MeetingPlanState:
    """Node 3: Select activities from RAG."""
    state["current_agent"] = "Scouting Context Agent"
    context  = state.get("context", {})
    occasion = context.get("occasion", {}).get("name") if context else None
    weather  = context.get("weather", {}).get("advisory") if context else None
    running_thought = f"Querying knowledge base for {state['unit']} activities matching theme '{state['theme']}'. Aligning with scouting values and Lebanese context..."
    state["agent_thoughts"].append({"agent": "Scouting Context Agent", "thought": running_thought, "status": "running"})
    _cb("Scouting Context Agent", running_thought, "running")
    try:
        result = run_scouting_context_agent(
            unit=state["unit"], theme=state["theme"],
            sequence=state["sequence"], occasion=occasion, weather=weather,
        )
        state["selected"] = result
        selected_count = len(result.get("selected_activities", []))
        rag_pool       = result.get("rag_pool_size", 0)
        done_thought = (
            f"Selected {selected_count} activities. "
            f"RAG knowledge base provided {rag_pool} candidate activities. "
            f"Context notes: {result.get('context_notes', '')[:100]}..."
        )
        state["agent_thoughts"][-1]["thought"] = done_thought
        state["agent_thoughts"][-1]["status"]  = "done"
        _cb("Scouting Context Agent", done_thought, "done")
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Scouting Context Agent failed: {str(e)}"
        _cb("Scouting Context Agent", str(e), "error")
    return state


def node_activity_generator(state: MeetingPlanState) -> MeetingPlanState:
    """Node 4: Generate full activity descriptions."""
    state["current_agent"] = "Activity Generator Agent"
    selected = state.get("selected", {}).get("selected_activities", [])
    running_thought = f"Writing full descriptions for {len(selected)} activities. Generating objectives, step-by-step instructions, materials lists, and leader tips..."
    state["agent_thoughts"].append({"agent": "Activity Generator Agent", "thought": running_thought, "status": "running"})
    _cb("Activity Generator Agent", running_thought, "running")
    try:
        result = run_activity_generator_agent(
            unit=state["unit"], theme=state["theme"], selected_activities=selected,
        )
        state["generated"] = result
        activities = result.get("activities", [])
        materials  = result.get("master_materials_list", [])
        done_thought = (
            f"Generated full descriptions for {len(activities)} activities. "
            f"Master materials list contains {len(materials)} items. "
            f"All activities include objectives, instructions, and leader tips."
        )
        state["agent_thoughts"][-1]["thought"] = done_thought
        state["agent_thoughts"][-1]["status"]  = "done"
        _cb("Activity Generator Agent", done_thought, "done")
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Activity Generator Agent failed: {str(e)}"
        _cb("Activity Generator Agent", str(e), "error")
    return state


def node_validation(state: MeetingPlanState) -> MeetingPlanState:
    """Node 5: Validate the meeting plan."""
    state["current_agent"] = "Validation Agent"
    activities = state.get("generated", {}).get("activities", [])
    config     = get_unit_config(state["unit"])
    content_minutes = (state.get("custom_duration") or config["meeting_duration"]) - BOOKEND_MINUTES
    running_thought = f"Validating {len(activities)} activities against meeting rules. Checking timing, energy bookends, cognitive load balance..."
    state["agent_thoughts"].append({"agent": "Validation Agent", "thought": running_thought, "status": "running"})
    _cb("Validation Agent", running_thought, "running")
    try:
        # Auto-correct timing before validation so Rule 1 runs on fixed durations
        timing = validate_timing(state["unit"], activities, state.get("custom_duration"))
        if timing["adjustments_made"]:
            activities = timing["activities"]
            state["generated"]["activities"] = activities
            _cb("Validation Agent",
                f"Time validator corrected {len(timing['adjustments_made'])} duration(s): "
                + "; ".join(timing["adjustments_made"]),
                "running")

        result = run_validation_agent(
            unit=state["unit"], theme=state["theme"], activities=activities,
            total_content_minutes=content_minutes, custom_duration=state.get("custom_duration"),
        )
        if timing["adjustments_made"]:
            result["time_corrections"] = timing["adjustments_made"]
        state["validation"] = result
        done_thought = (
            f"Validation {'passed' if result['is_valid'] else 'failed'}. "
            f"{len(result['passed'])} checks passed, "
            f"{len(result['warnings'])} warnings, "
            f"{len(result['issues'])} issues. "
            f"{result['summary']}"
        )
        state["agent_thoughts"][-1]["thought"] = done_thought
        state["agent_thoughts"][-1]["status"]  = "done"
        _cb("Validation Agent", done_thought, "done")
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Validation Agent failed: {str(e)}"
        _cb("Validation Agent", str(e), "error")
    return state


def node_formatting(state: MeetingPlanState) -> MeetingPlanState:
    """Node 6: Format the final meeting plan."""
    state["current_agent"] = "Formatting Agent"
    activities = state.get("generated", {}).get("activities", [])
    materials  = state.get("generated", {}).get("master_materials_list", [])
    running_thought = "Assembling final meeting plan document. Adding timestamps, consolidating materials list, applying professional formatting..."
    state["agent_thoughts"].append({"agent": "Formatting Agent", "thought": running_thought, "status": "running"})
    _cb("Formatting Agent", running_thought, "running")
    try:
        plan = run_formatting_agent(
            unit=state["unit"], theme=state["theme"],
            meeting_date=state.get("meeting_date"), activities=activities,
            master_materials=materials, context=state.get("context"),
            validation=state.get("validation"), custom_duration=state.get("custom_duration"),
            start_time_minutes=_parse_start_time(state.get("meeting_start_time")),
        )
        quality = evaluate_plan(
            unit=state["unit"], activities=activities,
            context=state.get("context"), custom_duration=state.get("custom_duration"),
        )
        plan["quality_score"] = quality
        state["plan"]        = plan
        state["plan_text"]   = plan_to_markdown(plan)
        state["is_complete"] = True
        done_thought = (
            f"Meeting plan assembled successfully. "
            f"{len(plan['schedule'])} schedule segments. "
            f"Quality score: {quality['total']}/100 (Grade {quality['grade']}). "
            f"Plan ready for display and PDF export."
        )
        state["agent_thoughts"][-1]["thought"] = done_thought
        state["agent_thoughts"][-1]["status"]  = "done"
        _cb("Formatting Agent", done_thought, "done")
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Formatting Agent failed: {str(e)}"
        _cb("Formatting Agent", str(e), "error")
    return state


# Conditional Edge 

def should_continue(state: MeetingPlanState) -> str:
    """Routes to END if there's an error, otherwise continues."""
    if state.get("error"):
        return "end"
    return "continue"


# Helpers 

def _parse_start_time(value) -> int:
    """Convert a meeting start-time value to minutes since midnight.
    Accepts: "13:00", "1:00 PM", "13:30", integers (already minutes). Returns 0 if unparseable.
    """
    if not value:
        return 0
    if isinstance(value, int):
        return value
    s = str(value).strip()
    # HH:MM 24-hour
    m = re.match(r'^(\d{1,2}):(\d{2})$', s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    # H:MM AM/PM
    m = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)$', s)
    if m:
        h, mins, period = int(m.group(1)), int(m.group(2)), m.group(3).upper()
        if period == 'PM' and h != 12:
            h += 12
        elif period == 'AM' and h == 12:
            h = 0
        return h * 60 + mins
    return 0


# Build the Graph 

def build_pipeline() -> StateGraph:
    graph = StateGraph(MeetingPlanState)

    # Add nodes
    graph.add_node("context_awareness",  node_context_awareness)
    graph.add_node("educational_design", node_educational_design)
    graph.add_node("scouting_context",   node_scouting_context)
    graph.add_node("activity_generator", node_activity_generator)
    graph.add_node("validate_plan",      node_validation)
    graph.add_node("formatting",         node_formatting)

    # Set entry point
    graph.set_entry_point("context_awareness")

    # Add edges with error checking
    graph.add_conditional_edges("context_awareness",  should_continue, {"continue": "educational_design", "end": END})
    graph.add_conditional_edges("educational_design", should_continue, {"continue": "scouting_context",   "end": END})
    graph.add_conditional_edges("scouting_context",   should_continue, {"continue": "activity_generator", "end": END})
    graph.add_conditional_edges("activity_generator", should_continue, {"continue": "validate_plan",      "end": END})
    graph.add_conditional_edges("validate_plan",      should_continue, {"continue": "formatting",         "end": END})
    graph.add_edge("formatting", END)

    return graph.compile()


# Main Pipeline Runner

def run_pipeline(
    unit: str,
    theme: str,
    meeting_date: str = None,
    custom_duration: int = None,
    meeting_start_time: str = None,
    conversation_history: list = None,
    progress_callback=None,
) -> dict:
    """
    Runs the full multi-agent pipeline.

    Args:
        unit:                 Scout unit name
        theme:                Meeting theme
        meeting_date:         Optional date string DD/MM/YYYY
        custom_duration:      Optional custom meeting duration in minutes
        meeting_start_time:   Optional start time string "HH:MM" (24 h) or "H:MM AM/PM"
        conversation_history: Previous conversation messages
        progress_callback:    Optional callback(agent_name, thought, status)

    Returns:
        Final state dict with plan, plan_text, agent_thoughts, and validation
    """
    # Normalize custom_duration — the LLM sometimes returns it as a string
    if custom_duration is not None:
        try:
            custom_duration = int(custom_duration)
        except (ValueError, TypeError):
            custom_duration = None

    # Register callback for this thread so nodes can fire it live
    _active_callback.fn = progress_callback

    pipeline = build_pipeline()

    initial_state: MeetingPlanState = {
        "unit":                   unit,
        "theme":                  theme,
        "meeting_date":           meeting_date,
        "custom_duration":        custom_duration,
        "meeting_start_time":     meeting_start_time,
        "user_messages":          [],
        "conversation_history":   conversation_history or [],
        "context":                None,
        "sequence":               None,
        "selected":               None,
        "generated":              None,
        "validation":             None,
        "plan":                   None,
        "plan_text":              None,
        "current_agent":          "Initializing",
        "agent_thoughts":         [],
        "is_complete":            False,
        "error":                  None,
        "needs_more_info":        False,
        "clarification_question": None,
    }

    final_state = pipeline.invoke(initial_state)

    # Clear callback after pipeline completes
    _active_callback.fn = None

    return final_state


if __name__ == "__main__":
    print("Running full pipeline test...")
    print("Unit: Cubs | Theme: Friendship | Date: 27/04/2026")
    print()

    def print_progress(agent, thought, status):
        icon = "✓" if status == "done" else "✗" if status == "error" else "..."
        print(f"  [{icon}] {agent}")
        print(f"       {thought[:120]}...")
        print()

    result = run_pipeline(
        unit="Cubs",
        theme="Friendship",
        meeting_date="27/04/2026",
        progress_callback=print_progress,
    )

    if result.get("error"):
        print(f"Pipeline failed: {result['error']}")
    elif result.get("plan_text"):
        print(result["plan_text"][:2000])
        print("\n... (truncated)")
        print(f"\nPipeline complete. {len(result['agent_thoughts'])} agents ran successfully.")
    else:
        print("Pipeline completed but no plan was generated.")