import sys
import os
import json
from typing import TypedDict, Annotated, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base import get_llm, get_unit_config
from agents.educational_design  import run_educational_design_agent
from agents.scouting_context     import run_scouting_context_agent
from agents.activity_generator   import run_activity_generator_agent
from agents.context_awareness    import run_context_awareness_agent
from agents.validation           import run_validation_agent
from agents.formatting           import run_formatting_agent, plan_to_text, plan_to_markdown


# ── State Definition ──────────────────────────────────────────────────────────

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

    # Pipeline control
    current_agent:    str
    agent_thoughts:   list
    is_complete:      bool
    error:            Optional[str]
    needs_more_info:  bool
    clarification_question: Optional[str]


# ── Conversational Gate ───────────────────────────────────────────────────────

CONVERSATION_SYSTEM_PROMPT = """You are ScoutMind, an intelligent meeting planning assistant
for the Lebanese Scouts Association. You specialise exclusively in generating professional
weekly meeting plans for Lebanese scout units.

You are helpful, warm, and professional. You speak in clear prose — no bullet points,
no numbered lists, no emojis. You ask one clarifying question at a time when needed.

Units you support:
Beavers (Mixed, ages 3-7, 3-hour meetings),
Cubs (Mixed, ages 7-11, 3-hour meetings),
Girl Scouts (Girls, ages 11-16, 4-hour meetings),
Boy Scouts (Boys, ages 11-16, 4-hour meetings),
Pioneers (Girls, ages 11-16, 4-hour meetings),
Rovers (Boys, ages 16-22, 4-hour meetings).

If the user asks about anything unrelated to scout meeting planning, politely decline
and redirect them. Never use emojis or bullet points in your responses.

Follow this exact decision flow:

STEP 1 — If unit OR theme is missing and cannot be inferred: ask for it.
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

When ready to generate, respond with EXACTLY this JSON and nothing else:
{
  "ready_to_generate": true,
  "unit": "Cubs",
  "theme": "Friendship",
  "meeting_date": "27/04/2026",
  "custom_duration": null,
  "response": "One sentence confirming what you are generating — no emojis"
}

When asking a clarifying question:
{
  "ready_to_generate": false,
  "response": "Your single question in clean prose — no emojis, no bullet points"
}

When the user is off-topic, respond with:
{
  "ready_to_generate": false,
  "response": "I specialise exclusively in scout meeting planning for the Lebanese Scouts Association. I am not able to help with that, but I would be happy to help you plan your next scout meeting. Which unit are you leading?"
}"""


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
    if user_unit:
        system_content += (
            f"\n\nThe user is registered as a {user_unit} unit leader. "
            f"Pre-fill this as the default unit unless they specify otherwise."
        )

    # Build strictly alternating message history for Claude
    # Rule: SystemMessage first, then ONLY Human/AI alternating, ending with HumanMessage
    # Claude rejects: consecutive system messages, consecutive same-role messages

    history = conversation_history[-20:] if conversation_history else []

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
            flat.append(("assistant", text[:300]))
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

    # Try direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON object from anywhere in the response
    start = content.find("{")
    end   = content.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

    # Final fallback: return only the non-JSON prose as the response
    prose = content[:start].strip() if start != -1 else content.strip()
    return {
        "ready_to_generate": False,
        "response": prose or content,
    }


# ── Agent Node Functions ──────────────────────────────────────────────────────

def node_context_awareness(state: MeetingPlanState) -> MeetingPlanState:
    """Node 1: Check weather and occasions."""
    state["current_agent"] = "Context Awareness Agent"
    state["agent_thoughts"].append({
        "agent":   "Context Awareness Agent",
        "thought": f"Checking weather in Beirut and Lebanese calendar for {state.get('meeting_date', 'today')}...",
        "status":  "running",
    })
    try:
        context = run_context_awareness_agent(state.get("meeting_date"))
        state["context"] = context
        thought_text = f"Weather: {context['weather']['description']}. "
        if context["occasion"]["found"]:
            thought_text += f"Occasion detected: {context['occasion']['name']}. "
        thought_text += f"Generated {len(context['advisories'])} advisory/advisories."
        state["agent_thoughts"][-1]["thought"] = thought_text
        state["agent_thoughts"][-1]["status"]  = "done"
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Context Awareness Agent failed: {str(e)}"
    return state


def node_educational_design(state: MeetingPlanState) -> MeetingPlanState:
    """Node 2: Design activity sequence."""
    state["current_agent"] = "Educational Design Agent"
    unit   = state["unit"]
    theme  = state["theme"]
    config = get_unit_config(unit)

    content_minutes = (state.get("custom_duration") or config["meeting_duration"]) - 30

    state["agent_thoughts"].append({
        "agent":   "Educational Design Agent",
        "thought": f"Designing activity sequence for {unit} unit ({content_minutes} minutes of content) on theme: {theme}. Applying educational therapy frameworks...",
        "status":  "running",
    })
    try:
        result = run_educational_design_agent(
            unit=unit,
            theme=theme,
            total_content_minutes=content_minutes,
            custom_duration=state.get("custom_duration"),
        )
        state["sequence"] = result.get("sequence", [])
        state["agent_thoughts"][-1]["thought"] = (
            f"Designed {len(state['sequence'])} activity slots. "
            f"First: {state['sequence'][0]['activity_type'] if state['sequence'] else 'N/A'}, "
            f"Last: {state['sequence'][-1]['activity_type'] if state['sequence'] else 'N/A'}. "
            f"Educational rationale: {result.get('educational_notes', '')[:100]}..."
        )
        state["agent_thoughts"][-1]["status"] = "done"
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Educational Design Agent failed: {str(e)}"
    return state


def node_scouting_context(state: MeetingPlanState) -> MeetingPlanState:
    """Node 3: Select activities from RAG."""
    state["current_agent"] = "Scouting Context Agent"
    context  = state.get("context", {})
    occasion = context.get("occasion", {}).get("name") if context else None
    weather  = context.get("weather", {}).get("advisory") if context else None

    state["agent_thoughts"].append({
        "agent":   "Scouting Context Agent",
        "thought": f"Querying knowledge base for {state['unit']} activities matching theme '{state['theme']}'. Aligning with scouting values and Lebanese context...",
        "status":  "running",
    })
    try:
        result = run_scouting_context_agent(
            unit=state["unit"],
            theme=state["theme"],
            sequence=state["sequence"],
            occasion=occasion,
            weather=weather,
        )
        state["selected"] = result
        selected_count = len(result.get("selected_activities", []))
        rag_pool       = result.get("rag_pool_size", 0)
        state["agent_thoughts"][-1]["thought"] = (
            f"Selected {selected_count} activities. "
            f"RAG knowledge base provided {rag_pool} candidate activities. "
            f"Context notes: {result.get('context_notes', '')[:100]}..."
        )
        state["agent_thoughts"][-1]["status"] = "done"
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Scouting Context Agent failed: {str(e)}"
    return state


def node_activity_generator(state: MeetingPlanState) -> MeetingPlanState:
    """Node 4: Generate full activity descriptions."""
    state["current_agent"] = "Activity Generator Agent"
    selected = state.get("selected", {}).get("selected_activities", [])

    state["agent_thoughts"].append({
        "agent":   "Activity Generator Agent",
        "thought": f"Writing full descriptions for {len(selected)} activities. Generating objectives, step-by-step instructions, materials lists, and leader tips...",
        "status":  "running",
    })
    try:
        result = run_activity_generator_agent(
            unit=state["unit"],
            theme=state["theme"],
            selected_activities=selected,
        )
        state["generated"] = result
        activities = result.get("activities", [])
        materials  = result.get("master_materials_list", [])
        state["agent_thoughts"][-1]["thought"] = (
            f"Generated full descriptions for {len(activities)} activities. "
            f"Master materials list contains {len(materials)} items. "
            f"All activities include objectives, instructions, and leader tips."
        )
        state["agent_thoughts"][-1]["status"] = "done"
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Activity Generator Agent failed: {str(e)}"
    return state


def node_validation(state: MeetingPlanState) -> MeetingPlanState:
    """Node 5: Validate the meeting plan."""
    state["current_agent"] = "Validation Agent"
    activities = state.get("generated", {}).get("activities", [])
    config     = get_unit_config(state["unit"])
    content_minutes = (state.get("custom_duration") or config["meeting_duration"]) - 30

    state["agent_thoughts"].append({
        "agent":   "Validation Agent",
        "thought": f"Validating {len(activities)} activities against meeting rules. Checking timing, energy bookends, cognitive load balance...",
        "status":  "running",
    })
    try:
        result = run_validation_agent(
            unit=state["unit"],
            theme=state["theme"],
            activities=activities,
            total_content_minutes=content_minutes,
            custom_duration=state.get("custom_duration"),
        )
        state["validation"] = result
        state["agent_thoughts"][-1]["thought"] = (
            f"Validation {'passed' if result['is_valid'] else 'failed'}. "
            f"{len(result['passed'])} checks passed, "
            f"{len(result['warnings'])} warnings, "
            f"{len(result['issues'])} issues. "
            f"{result['summary']}"
        )
        state["agent_thoughts"][-1]["status"] = "done"
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Validation Agent failed: {str(e)}"
    return state


def node_formatting(state: MeetingPlanState) -> MeetingPlanState:
    """Node 6: Format the final meeting plan."""
    state["current_agent"] = "Formatting Agent"
    activities = state.get("generated", {}).get("activities", [])
    materials  = state.get("generated", {}).get("master_materials_list", [])

    state["agent_thoughts"].append({
        "agent":   "Formatting Agent",
        "thought": "Assembling final meeting plan document. Adding timestamps, consolidating materials list, applying professional formatting...",
        "status":  "running",
    })
    try:
        plan = run_formatting_agent(
            unit=state["unit"],
            theme=state["theme"],
            meeting_date=state.get("meeting_date"),
            activities=activities,
            master_materials=materials,
            context=state.get("context"),
            validation=state.get("validation"),
            custom_duration=state.get("custom_duration"),
        )
        state["plan"]      = plan
        state["plan_text"] = plan_to_markdown(plan)
        state["is_complete"] = True
        state["agent_thoughts"][-1]["thought"] = (
            f"Meeting plan assembled successfully. "
            f"{len(plan['schedule'])} schedule segments. "
            f"Plan ready for display and PDF export."
        )
        state["agent_thoughts"][-1]["status"] = "done"
    except Exception as e:
        state["agent_thoughts"][-1]["status"] = "error"
        state["error"] = f"Formatting Agent failed: {str(e)}"
    return state


# ── Conditional Edge ──────────────────────────────────────────────────────────

def should_continue(state: MeetingPlanState) -> str:
    """Routes to END if there's an error, otherwise continues."""
    if state.get("error"):
        return "end"
    return "continue"


# ── Build the Graph ───────────────────────────────────────────────────────────

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


# ── Main Pipeline Runner ──────────────────────────────────────────────────────

def run_pipeline(
    unit: str,
    theme: str,
    meeting_date: str = None,
    custom_duration: int = None,
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
        conversation_history: Previous conversation messages
        progress_callback:    Optional callback(agent_name, thought, status)

    Returns:
        Final state dict with plan, plan_text, agent_thoughts, and validation
    """
    pipeline = build_pipeline()

    initial_state: MeetingPlanState = {
        "unit":                   unit,
        "theme":                  theme,
        "meeting_date":           meeting_date,
        "custom_duration":        custom_duration,
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

    if progress_callback and final_state.get("agent_thoughts"):
        for thought in final_state["agent_thoughts"]:
            progress_callback(
                thought["agent"],
                thought["thought"],
                thought["status"],
            )

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