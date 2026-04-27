import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import get_unit_config


FIXED_OPENING = """Attendance taking and uniform inspection. The leader calls each member's name and records presence or absence. Each member must present their personal items for inspection: Branch Book, Small Notebook, Pen, Rope, and Small Towel. Any missing items are noted and members are reminded to bring them next week. The leader opens with the Scout Promise."""

FIXED_CLOSING = """Members sit in a circle. The leader facilitates a structured reflection on the meeting. Each member is invited to share: one thing they enjoyed, one thing they learned, and one thing they could improve. The leader summarises the key themes of the meeting and connects them to the Scout Law. The meeting closes with the Scout Promise and formal dismissal."""


def format_duration(minutes: int) -> str:
    """Converts minutes to a readable format."""
    if minutes < 60:
        return f"{minutes} minutes"
    hours   = minutes // 60
    mins    = minutes % 60
    if mins == 0:
        return f"{hours} hour{'s' if hours > 1 else ''}"
    return f"{hours} hour{'s' if hours > 1 else ''} {mins} minutes"


def build_time_schedule(activities: list, total_meeting_minutes: int) -> list:
    """Builds a timestamped schedule for all activities including fixed bookends."""
    schedule = []
    current  = 0

    # Opening ceremony
    schedule.append({
        "start_min": 0,
        "end_min":   15,
        "label":     "Opening Ceremony",
        "type":      "fixed",
    })
    current = 15

    # Content activities
    for activity in activities:
        duration = activity.get("duration_minutes", 15)
        schedule.append({
            "start_min": current,
            "end_min":   current + duration,
            "label":     activity.get("activity_name", "Activity"),
            "type":      activity.get("activity_type", "game"),
            "slot":      activity.get("slot", 0),
        })
        current += duration

    # Reflection and closing
    schedule.append({
        "start_min": current,
        "end_min":   current + 15,
        "label":     "Reflection Circle & Closing",
        "type":      "fixed",
    })

    return schedule


def format_time(minutes: int) -> str:
    """Converts minute offset to HH:MM format starting from 00:00."""
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def run_formatting_agent(
    unit: str,
    theme: str,
    meeting_date: str,
    activities: list,
    master_materials: list,
    context: dict = None,
    validation: dict = None,
    custom_duration: int = None,
) -> dict:
    """
    Assembles the final meeting plan document as a structured dict.
    This is pure logic — no LLM call needed.

    Returns:
        Dict containing the complete formatted meeting plan
    """
    config          = get_unit_config(unit)
    meeting_minutes = custom_duration or config["meeting_duration"]
    content_minutes = meeting_minutes - 30

    schedule = build_time_schedule(activities, meeting_minutes)

    # ── Build the complete plan document ─────────────────────────────────────
    plan = {
        "header": {
            "title":          "SCOUT MEETING PLAN",
            "unit":           unit,
            "age_range":      f"{config['age_range'][0]}-{config['age_range'][1]} years",
            "gender":         config["gender"].capitalize(),
            "theme":          theme,
            "date":           meeting_date or datetime.today().strftime("%d/%m/%Y"),
            "total_duration": format_duration(meeting_minutes),
            "generated_by":   "ScoutMind — Lebanese Scouts Association",
            "generated_at":   datetime.now().strftime("%d/%m/%Y %H:%M"),
        },
        "context_advisories": context.get("advisories", []) if context else [],
        "master_materials_list": master_materials,
        "schedule": [],
    }

    # ── Opening Ceremony ──────────────────────────────────────────────────────
    plan["schedule"].append({
        "time_start":    "00:00",
        "time_end":      "00:15",
        "duration":      "15 minutes",
        "segment_title": "OPENING CEREMONY",
        "segment_type":  "fixed",
        "description":   FIXED_OPENING,
        "materials":     ["Attendance register", "Pen"],
        "leader_notes":  "This segment is fixed and must not be shortened. Maintain a formal, respectful tone.",
    })

    # ── Content Activities ────────────────────────────────────────────────────
    for i, activity in enumerate(activities):
        slot_info  = schedule[i + 1]  # +1 to skip opening
        start_time = format_time(slot_info["start_min"])
        end_time   = format_time(slot_info["end_min"])
        duration   = activity.get("duration_minutes", 15)

        # Format instructions
        instructions = activity.get("instructions", [])
        if isinstance(instructions, list):
            instructions_text = instructions
        else:
            instructions_text = [instructions]

        # Format educational technique
        edu_tech = activity.get("educational_technique", {})
        if isinstance(edu_tech, dict):
            edu_tech_text = (
                f"{edu_tech.get('name', 'N/A')}: {edu_tech.get('application', '')}"
                if edu_tech else None
            )
        else:
            edu_tech_text = str(edu_tech) if edu_tech else None

        plan["schedule"].append({
            "time_start":           start_time,
            "time_end":             end_time,
            "duration":             f"{duration} minutes",
            "segment_title":        f"ACTIVITY {activity.get('slot', i+1)} — {activity.get('activity_name', 'Activity').upper()}",
            "segment_type":         activity.get("activity_type", "game"),
            "energy_level":         activity.get("energy_level", "medium"),
            "objective":            activity.get("objective", ""),
            "instructions":         instructions_text,
            "materials":            activity.get("materials", []),
            "educational_technique": edu_tech_text,
            "leader_tips":          activity.get("leader_tips", ""),
            "theme_connection":     activity.get("theme_connection", ""),
        })

    # ── Reflection Circle & Closing ───────────────────────────────────────────
    closing_start = format_time(meeting_minutes - 15)
    closing_end   = format_time(meeting_minutes)

    plan["schedule"].append({
        "time_start":    closing_start,
        "time_end":      closing_end,
        "duration":      "15 minutes",
        "segment_title": "REFLECTION CIRCLE & CLOSING",
        "segment_type":  "fixed",
        "description":   FIXED_CLOSING,
        "materials":     ["Notebooks and pens (for journaling if applicable)"],
        "leader_notes":  "This segment is fixed. Ensure every member has a chance to speak. End on a positive, motivating note.",
    })

    # ── Validation Summary ────────────────────────────────────────────────────
    if validation:
        plan["validation"] = {
            "is_valid":       validation.get("is_valid", True),
            "warnings":       validation.get("warnings", []),
            "activity_count": validation.get("activity_count", len(activities)),
        }

    return plan


def plan_to_text(plan: dict) -> str:
    """
    Converts a plan dict to a clean, formatted text document for display in the UI.
    """
    lines = []
    h     = plan["header"]

    lines.append("=" * 70)
    lines.append(h["title"].center(70))
    lines.append("=" * 70)
    lines.append(f"Unit          : {h['unit']} ({h['age_range']}, {h['gender']})")
    lines.append(f"Theme         : {h['theme']}")
    lines.append(f"Date          : {h['date']}")
    lines.append(f"Total Duration: {h['total_duration']}")
    lines.append(f"Generated By  : {h['generated_by']}")
    lines.append("=" * 70)

    if plan.get("context_advisories"):
        lines.append("")
        lines.append("CONTEXTUAL ADVISORIES")
        lines.append("-" * 70)
        for advisory in plan["context_advisories"]:
            lines.append(f"  {advisory}")

    lines.append("")
    lines.append("MATERIALS & PREPARATION LIST")
    lines.append("-" * 70)
    for item in plan.get("master_materials_list", []):
        lines.append(f"  - {item}")

    lines.append("")
    lines.append("=" * 70)
    lines.append("MEETING SCHEDULE")
    lines.append("=" * 70)

    for segment in plan.get("schedule", []):
        lines.append("")
        lines.append(f"[{segment['time_start']} - {segment['time_end']}]  {segment['segment_title']}  ({segment['duration']})")
        lines.append("-" * 70)

        if segment.get("segment_type") == "fixed":
            lines.append(segment.get("description", ""))
            if segment.get("materials"):
                lines.append("")
                lines.append("Materials:")
                for m in segment["materials"]:
                    lines.append(f"  - {m}")
            if segment.get("leader_notes"):
                lines.append("")
                lines.append(f"Leader Notes: {segment['leader_notes']}")
        else:
            if segment.get("energy_level"):
                lines.append(f"Type: {segment['segment_type'].replace('_', ' ').title()}  |  Energy: {segment['energy_level'].capitalize()}")
            lines.append("")
            lines.append("Objective:")
            lines.append(f"  {segment.get('objective', '')}")
            lines.append("")
            lines.append("Instructions:")
            for step in segment.get("instructions", []):
                lines.append(f"  {step}")
            lines.append("")
            lines.append("Materials:")
            for m in segment.get("materials", []):
                lines.append(f"  - {m}")
            if segment.get("educational_technique"):
                lines.append("")
                lines.append(f"Educational Technique: {segment['educational_technique']}")
            if segment.get("leader_tips"):
                lines.append("")
                lines.append(f"Leader Tips: {segment['leader_tips']}")
            if segment.get("theme_connection"):
                lines.append("")
                lines.append(f"Theme Connection: {segment['theme_connection']}")

    lines.append("")
    lines.append("=" * 70)
    lines.append("END OF MEETING PLAN".center(70))
    lines.append("=" * 70)

    return "\n".join(lines)


def plan_to_markdown(plan: dict) -> str:
    """
    Converts a plan dict to clean markdown for display in the chat interface.
    """
    lines = []
    h = plan["header"]

    lines.append(f"# Scout Meeting Plan")
    lines.append(f"**Unit:** {h['unit']} ({h['age_range']}, {h['gender']})  ")
    lines.append(f"**Theme:** {h['theme']}  ")
    lines.append(f"**Date:** {h['date']}  ")
    lines.append(f"**Total Duration:** {h['total_duration']}  ")
    lines.append(f"**Generated by:** {h['generated_by']}")
    lines.append("")
    lines.append("---")

    # Context advisories
    if plan.get("context_advisories"):
        lines.append("")
        lines.append("### Contextual Advisories")
        for advisory in plan["context_advisories"]:
            lines.append(f"> {advisory}")

    # Master materials list
    materials = plan.get("master_materials_list", [])
    if materials:
        lines.append("")
        lines.append("### Materials & Preparation List")
        for item in materials:
            lines.append(f"- {item}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Meeting Schedule")

    for segment in plan.get("schedule", []):
        lines.append("")
        lines.append(f"### `{segment['time_start']} — {segment['time_end']}` &nbsp; {segment['segment_title']} *({segment['duration']})*")

        if segment.get("segment_type") == "fixed":
            lines.append("")
            lines.append(segment.get("description", ""))
            if segment.get("materials"):
                lines.append("")
                lines.append("**Materials:**")
                for m in segment["materials"]:
                    lines.append(f"- {m}")
            if segment.get("leader_notes"):
                lines.append("")
                lines.append(f"> **Leader Notes:** {segment['leader_notes']}")
        else:
            seg_type = segment.get("segment_type", "").replace("_", " ").title()
            energy   = segment.get("energy_level", "").capitalize()
            lines.append(f"*{seg_type} &nbsp;|&nbsp; Energy: {energy}*")
            lines.append("")

            if segment.get("objective"):
                lines.append(f"**Objective:** {segment['objective']}")
                lines.append("")

            if segment.get("instructions"):
                lines.append("**Instructions:**")
                for j, step in enumerate(segment["instructions"], 1):
                    # Clean up step numbering if already present
                    step_text = step.lstrip("0123456789. ")
                    lines.append(f"{j}. {step_text}")
                lines.append("")

            if segment.get("materials"):
                lines.append("**Materials:**")
                for m in segment["materials"]:
                    lines.append(f"- {m}")
                lines.append("")

            if segment.get("educational_technique"):
                lines.append(f"**Educational Technique:** {segment['educational_technique']}")
                lines.append("")

            if segment.get("leader_tips"):
                lines.append(f"> **Leader Tips:** {segment['leader_tips']}")
                lines.append("")

            if segment.get("theme_connection"):
                lines.append(f"> **Theme Connection:** {segment['theme_connection']}")

        lines.append("")
        lines.append("---")

    lines.append("")
    lines.append("*End of Meeting Plan — Generated by ScoutMind*")

    return "\n".join(lines)


if __name__ == "__main__":
    test_activities = [
        {
            "slot": 1, "activity_name": "Zip Zap Boing", "activity_type": "game",
            "duration_minutes": 10, "energy_level": "high",
            "objective": "Energise the group and build focus.",
            "instructions": ["Step 1: Stand in a circle.", "Step 2: Pass the energy."],
            "materials": ["None required"],
            "educational_technique": {"name": "Energiser Break", "application": "Resets attention before cognitive activities."},
            "leader_tips": "Keep energy high. Play 2-3 rounds.",
            "theme_connection": "Builds the group connection central to friendship.",
        },
    ]

    plan = run_formatting_agent(
        unit="Cubs",
        theme="Friendship",
        meeting_date="27/04/2026",
        activities=test_activities,
        master_materials=["None required"],
    )
    print(plan_to_text(plan))