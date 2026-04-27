import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import get_unit_config, ACTIVITY_TYPES


def validate_timing(
    unit: str,
    activities: list,
    custom_duration: int = None,
) -> dict:
    """
    Validates and corrects activity timing for a meeting plan.

    Args:
        unit:            Scout unit name
        activities:      List of activity dicts with duration_minutes
        custom_duration: Optional custom total meeting duration

    Returns:
        Dict with timing analysis and corrected activities if needed
    """
    config          = get_unit_config(unit)
    meeting_minutes = custom_duration or config["meeting_duration"]
    content_minutes = meeting_minutes - 30  # subtract fixed bookends
    actual_total    = sum(a.get("duration_minutes", 0) for a in activities)
    difference      = actual_total - content_minutes
    tolerance       = 5

    result = {
        "unit":              unit,
        "meeting_minutes":   meeting_minutes,
        "content_minutes":   content_minutes,
        "actual_total":      actual_total,
        "difference":        difference,
        "within_tolerance":  abs(difference) <= tolerance,
        "activities":        activities,
        "adjustments_made":  [],
    }

    if abs(difference) <= tolerance:
        result["status"]  = "ok"
        result["message"] = f"Timing is within tolerance. Total: {actual_total} min (target: {content_minutes} min)."
        return result

    # Need to adjust
    adjusted    = [dict(a) for a in activities]
    remaining   = difference  # positive = too long, negative = too short

    if difference > 0:
        # Too long — shorten activities starting from the middle
        result["status"] = "adjusted_shorter"
        indices = list(range(1, len(adjusted) - 1))  # skip first and last
        for i in indices:
            if remaining <= 0:
                break
            act      = adjusted[i]
            act_type = act.get("activity_type", "game")
            min_dur  = ACTIVITY_TYPES.get(act_type, {}).get("duration_range", (10, 20))[0]
            current  = act.get("duration_minutes", 15)
            can_cut  = current - min_dur
            cut      = min(can_cut, remaining)
            if cut > 0:
                adjusted[i]["duration_minutes"] = current - cut
                remaining -= cut
                result["adjustments_made"].append(
                    f"Slot {i+1} '{act.get('activity_name', '')}': reduced by {cut} min ({current} → {current-cut} min)"
                )
    else:
        # Too short — extend activities in the middle
        result["status"] = "adjusted_longer"
        indices = list(range(1, len(adjusted) - 1))
        for i in indices:
            if remaining >= 0:
                break
            act      = adjusted[i]
            act_type = act.get("activity_type", "game")
            max_dur  = ACTIVITY_TYPES.get(act_type, {}).get("duration_range", (10, 20))[1]
            current  = act.get("duration_minutes", 15)
            can_add  = max_dur - current
            add      = min(can_add, abs(remaining))
            if add > 0:
                adjusted[i]["duration_minutes"] = current + add
                remaining += add
                result["adjustments_made"].append(
                    f"Slot {i+1} '{act.get('activity_name', '')}': extended by {add} min ({current} → {current+add} min)"
                )

    new_total = sum(a.get("duration_minutes", 0) for a in adjusted)
    result["activities"]      = adjusted
    result["adjusted_total"]  = new_total
    result["message"]         = (
        f"Timing adjusted from {actual_total} to {new_total} min "
        f"(target: {content_minutes} min). "
        f"{len(result['adjustments_made'])} adjustment(s) made."
    )
    return result


if __name__ == "__main__":
    test_activities = [
        {"slot": 1, "activity_name": "Game 1",     "activity_type": "game",    "duration_minutes": 15},
        {"slot": 2, "activity_name": "Lecture",    "activity_type": "lecture", "duration_minutes": 25},
        {"slot": 3, "activity_name": "Skill",      "activity_type": "skill",   "duration_minutes": 20},
        {"slot": 4, "activity_name": "Challenge",  "activity_type": "team_challenge", "duration_minutes": 25},
        {"slot": 5, "activity_name": "Song",       "activity_type": "song",    "duration_minutes": 10},
        {"slot": 6, "activity_name": "Craft",      "activity_type": "craft",   "duration_minutes": 25},
        {"slot": 7, "activity_name": "Story",      "activity_type": "storytelling", "duration_minutes": 15},
        {"slot": 8, "activity_name": "Final Game", "activity_type": "game",    "duration_minutes": 20},
    ]
    result = validate_timing("Cubs", test_activities)
    print(f"Status:     {result['status']}")
    print(f"Target:     {result['content_minutes']} min")
    print(f"Actual:     {result['actual_total']} min")
    print(f"Message:    {result['message']}")
    if result["adjustments_made"]:
        print("Adjustments:")
        for adj in result["adjustments_made"]:
            print(f"  - {adj}")