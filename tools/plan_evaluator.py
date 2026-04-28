from agents.base import get_unit_config, BOOKEND_MINUTES


def evaluate_plan(
    unit: str,
    activities: list,
    context: dict = None,
    custom_duration: int = None,
) -> dict:
    """
    Scores a generated meeting plan across four dimensions (0-25 each, 100 total).

    Dimensions:
      1. Timing accuracy  - how close total activity time is to the target
      2. Structure        - bookend rules, no consecutive cognitive activities
      3. Variety          - diversity of activity types
      4. Context-awareness - use of weather / occasion advisories

    Args:
        unit:            Scout unit name
        activities:      List of activity dicts (from activity generator)
        context:         Context dict from context awareness agent (optional)
        custom_duration: Optional custom meeting duration

    Returns:
        Dict with per-dimension scores, total, grade letter, and explanation lines
    """
    config          = get_unit_config(unit)
    meeting_minutes = custom_duration or config["meeting_duration"]
    content_minutes = meeting_minutes - BOOKEND_MINUTES
    scores          = {}
    notes           = {}

    # ── Dimension 1: Timing accuracy (0-25) ──────────────────────────────────
    actual_total = sum(a.get("duration_minutes", 0) for a in activities)
    diff         = abs(actual_total - content_minutes)

    if diff == 0:
        timing_score = 25
        timing_note  = f"Perfect timing: {actual_total} min exactly matches target."
    elif diff <= 2:
        timing_score = 23
        timing_note  = f"Excellent timing: {actual_total} min ({diff} min off target)."
    elif diff <= 5:
        timing_score = 20
        timing_note  = f"Good timing: {actual_total} min ({diff} min off target, within tolerance)."
    elif diff <= 10:
        timing_score = 14
        timing_note  = f"Acceptable timing: {actual_total} min ({diff} min off target)."
    elif diff <= 20:
        timing_score = 8
        timing_note  = f"Poor timing: {actual_total} min ({diff} min off target)."
    else:
        timing_score = 0
        timing_note  = f"Timing failure: {actual_total} min ({diff} min off target, severely over/under)."

    scores["timing"]  = timing_score
    notes["timing"]   = timing_note

    # ── Dimension 2: Structure (0-25) ─────────────────────────────────────────
    structure_score  = 25
    structure_issues = []

    if activities:
        first = activities[0]
        if first.get("energy_level") != "high" and first.get("activity_type") != "game":
            structure_score -= 8
            structure_issues.append(
                f"First activity '{first.get('activity_name', 'unknown')}' is not high-energy."
            )

        last = activities[-1]
        if last.get("energy_level") != "high" and last.get("activity_type") != "game":
            structure_score -= 8
            structure_issues.append(
                f"Last activity '{last.get('activity_name', 'unknown')}' is not high-energy."
            )

    cognitive_types = {"lecture", "skill"}
    consecutive_count = 0
    for i in range(len(activities) - 1):
        curr = activities[i].get("activity_type", "")
        nxt  = activities[i + 1].get("activity_type", "")
        if curr in cognitive_types and nxt in cognitive_types:
            consecutive_count += 1

    if consecutive_count > 0:
        penalty = min(9, consecutive_count * 3)
        structure_score -= penalty
        structure_issues.append(
            f"{consecutive_count} consecutive cognitive activity pair(s) detected."
        )

    structure_score = max(0, structure_score)
    notes["structure"] = (
        f"Structure score {structure_score}/25. " +
        (" ".join(structure_issues) if structure_issues else "All structural rules satisfied.")
    )
    scores["structure"] = structure_score

    # ── Dimension 3: Variety (0-25) ───────────────────────────────────────────
    all_types     = {"game", "song", "skill", "lecture", "storytelling", "team_challenge", "craft"}
    used_types    = {a.get("activity_type", "") for a in activities}
    used_types   &= all_types
    type_count    = len(used_types)
    total_acts    = len(activities)

    # Score based on how many of 7 types are used
    if type_count >= 6:
        variety_score = 25
    elif type_count == 5:
        variety_score = 22
    elif type_count == 4:
        variety_score = 18
    elif type_count == 3:
        variety_score = 13
    elif type_count == 2:
        variety_score = 8
    else:
        variety_score = 3

    scores["variety"] = variety_score
    notes["variety"]  = (
        f"{type_count}/7 activity types used ({', '.join(sorted(used_types))}). "
        f"{total_acts} total activities."
    )

    # ── Dimension 4: Context-awareness (0-25) ─────────────────────────────────
    context_score = 0
    context_notes_list = []

    if context:
        weather  = context.get("weather", {})
        occasion = context.get("occasion", {})
        advisories = context.get("advisories", [])

        if weather.get("description") and weather["description"] != "unknown":
            context_score += 10
            context_notes_list.append(
                f"Weather data used: {weather['description']} ({weather.get('temperature', '?')}C)."
            )

        if occasion.get("found"):
            context_score += 10
            context_notes_list.append(
                f"Lebanese occasion integrated: {occasion.get('name', 'N/A')}."
            )

        if advisories:
            context_score += 5
            context_notes_list.append(
                f"{len(advisories)} advisory/advisories generated."
            )
    else:
        context_notes_list.append("No context data available (weather/occasion check skipped).")

    context_score = min(25, context_score)
    scores["context_awareness"] = context_score
    notes["context_awareness"]  = " ".join(context_notes_list) if context_notes_list else "No context used."

    # ── Total & Grade ─────────────────────────────────────────────────────────
    total = sum(scores.values())

    if total >= 90:
        grade = "A"
    elif total >= 80:
        grade = "B"
    elif total >= 65:
        grade = "C"
    elif total >= 50:
        grade = "D"
    else:
        grade = "F"

    return {
        "total":      total,
        "max":        100,
        "grade":      grade,
        "scores":     scores,
        "notes":      notes,
        "unit":       unit,
        "activities": len(activities),
    }


if __name__ == "__main__":
    test_activities = [
        {"activity_name": "Zip Zap",        "activity_type": "game",         "duration_minutes": 10, "energy_level": "high"},
        {"activity_name": "Scout Law Talk",  "activity_type": "lecture",      "duration_minutes": 15, "energy_level": "low"},
        {"activity_name": "Friendship Song", "activity_type": "song",         "duration_minutes": 10, "energy_level": "medium"},
        {"activity_name": "Knot Tying",      "activity_type": "skill",        "duration_minutes": 20, "energy_level": "low"},
        {"activity_name": "Bridge Builder",  "activity_type": "team_challenge","duration_minutes": 20, "energy_level": "medium"},
        {"activity_name": "Story Circle",    "activity_type": "storytelling", "duration_minutes": 15, "energy_level": "low"},
        {"activity_name": "Nature Craft",    "activity_type": "craft",        "duration_minutes": 20, "energy_level": "low"},
        {"activity_name": "Relay Race",      "activity_type": "game",         "duration_minutes": 10, "energy_level": "high"},
    ]
    test_context = {
        "weather":    {"description": "Clear skies", "temp_c": 22},
        "occasion":   {"found": False, "name": None},
        "advisories": ["Good weather — consider outdoor activities."],
    }
    result = evaluate_plan("Cubs", test_activities, context=test_context)
    print(f"Total score: {result['total']}/100  Grade: {result['grade']}")
    for dim, score in result["scores"].items():
        print(f"  {dim:20s}: {score}/25  — {result['notes'][dim]}")
