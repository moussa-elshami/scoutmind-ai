import json

from agents.base import get_unit_config, BOOKEND_MINUTES, _cb


def run_validation_agent(
    unit: str,
    theme: str,
    activities: list,
    total_content_minutes: int,
    custom_duration: int = None,
) -> dict:
    """
    Validates the generated meeting plan against all structural rules.
    This agent is pure logic — no LLM call needed.

    Rules checked:
    1. Total time matches expected content minutes (±5 min tolerance)
    2. First activity is high-energy
    3. Last activity is high-energy
    4. No two consecutive lectures or skill activities
    5. All activities have required fields
    6. Materials list is present for all activities

    Args:
        unit:                  Scout unit name
        theme:                 Meeting theme
        activities:            List of fully described activities
        total_content_minutes: Expected content minutes
        custom_duration:       Optional custom meeting duration

    Returns:
        Dict with validation results and any issues found
    """
    issues   = []
    warnings = []
    passed   = []

    if custom_duration:
        total_content_minutes = custom_duration - BOOKEND_MINUTES

    _cb("Validation Agent", f"Checking total time balance ({len(activities)} activities, target {total_content_minutes} min)...", "running")

    # ── Rule 1: Total time ────────────────────────────────────────────────────
    actual_total = sum(a.get("duration_minutes", 0) for a in activities)
    tolerance    = 5
    expected     = total_content_minutes

    if abs(actual_total - expected) <= tolerance:
        passed.append(f"Total time: {actual_total} minutes (target: {expected} min ±{tolerance})")
    else:
        issues.append(
            f"Total time mismatch: activities sum to {actual_total} minutes "
            f"but expected {expected} minutes (±{tolerance} tolerance)."
        )

    _cb("Validation Agent", "Checking energy bookend rules (first and last activities)...", "running")

    # ── Rule 2: First activity is high-energy ─────────────────────────────────
    if activities:
        first = activities[0]
        if first.get("energy_level") == "high" or first.get("activity_type") == "game":
            passed.append("First activity is high-energy.")
        else:
            issues.append(
                f"First activity '{first.get('activity_name')}' is not high-energy. "
                f"Meeting must start with an energetic game."
            )

    # ── Rule 3: Last activity is high-energy ──────────────────────────────────
    if activities:
        last = activities[-1]
        if last.get("energy_level") == "high" or last.get("activity_type") == "game":
            passed.append("Last activity is high-energy.")
        else:
            issues.append(
                f"Last activity '{last.get('activity_name')}' is not high-energy. "
                f"Meeting must end with an energetic game."
            )

    _cb("Validation Agent", "Checking cognitive load balance and required activity fields...", "running")

    # ── Rule 4: No consecutive cognitive activities ───────────────────────────
    cognitive_types = {"lecture", "skill"}
    for i in range(len(activities) - 1):
        curr = activities[i].get("activity_type", "")
        nxt  = activities[i + 1].get("activity_type", "")
        if curr in cognitive_types and nxt in cognitive_types:
            warnings.append(
                f"Slots {i+1} and {i+2}: consecutive cognitive activities "
                f"({curr} followed by {nxt}). Consider inserting an energiser."
            )

    if not any("consecutive" in w for w in warnings):
        passed.append("No consecutive cognitive activities found.")

    # ── Rule 5: All activities have required fields ───────────────────────────
    required_fields = ["activity_name", "activity_type", "duration_minutes",
                       "objective", "instructions", "materials"]
    missing_fields  = []

    for i, activity in enumerate(activities):
        for field in required_fields:
            if not activity.get(field):
                missing_fields.append(f"Slot {i+1} missing field: '{field}'")

    if missing_fields:
        issues.extend(missing_fields)
    else:
        passed.append("All activities have required fields.")

    # ── Rule 6: Age appropriateness warning ───────────────────────────────────
    config  = get_unit_config(unit)
    age_min = config["age_range"][0]
    if age_min <= 7:
        long_activities = [
            a for a in activities
            if a.get("duration_minutes", 0) > 20
        ]
        if long_activities:
            warnings.append(
                f"Unit {unit} (ages {age_min}+): "
                f"{len(long_activities)} activities exceed 20 minutes. "
                f"Consider shortening for young members."
            )

    # ── Summary ───────────────────────────────────────────────────────────────
    is_valid = len(issues) == 0

    return {
        "is_valid":             is_valid,
        "unit":                 unit,
        "theme":                theme,
        "total_content_minutes": actual_total,
        "expected_minutes":     expected,
        "activity_count":       len(activities),
        "passed":               passed,
        "warnings":             warnings,
        "issues":               issues,
        "summary": (
            "Validation passed. Plan is ready for formatting."
            if is_valid
            else f"Validation failed with {len(issues)} issue(s). Review required."
        ),
    }


if __name__ == "__main__":
    test_activities = [
        {"slot": 1, "activity_name": "Zip Zap Boing",        "activity_type": "game",    "duration_minutes": 10, "energy_level": "high",   "objective": "Energise", "instructions": ["Step 1"], "materials": ["None"]},
        {"slot": 2, "activity_name": "Friendship Discussion", "activity_type": "lecture", "duration_minutes": 20, "energy_level": "low",    "objective": "Discuss",  "instructions": ["Step 1"], "materials": ["Whiteboard"]},
        {"slot": 3, "activity_name": "Knot Tying",           "activity_type": "skill",   "duration_minutes": 15, "energy_level": "low",    "objective": "Skill",    "instructions": ["Step 1"], "materials": ["Rope"]},
        {"slot": 4, "activity_name": "Relay Race",           "activity_type": "game",    "duration_minutes": 15, "energy_level": "high",   "objective": "Energise", "instructions": ["Step 1"], "materials": ["Cones"]},
        {"slot": 5, "activity_name": "Craft Activity",       "activity_type": "craft",   "duration_minutes": 20, "energy_level": "low",    "objective": "Create",   "instructions": ["Step 1"], "materials": ["Paper"]},
        {"slot": 6, "activity_name": "Capture the Flag",     "activity_type": "game",    "duration_minutes": 15, "energy_level": "high",   "objective": "Energise", "instructions": ["Step 1"], "materials": ["Flags"]},
        {"slot": 7, "activity_name": "Story Circle",         "activity_type": "storytelling", "duration_minutes": 15, "energy_level": "low", "objective": "Listen", "instructions": ["Step 1"], "materials": ["None"]},
        {"slot": 8, "activity_name": "Scout Relay",          "activity_type": "game",    "duration_minutes": 10, "energy_level": "high",   "objective": "Close",    "instructions": ["Step 1"], "materials": ["Cones"]},
    ]

    result = run_validation_agent("Cubs", "Friendship", test_activities, 150)
    print(json.dumps(result, indent=2))