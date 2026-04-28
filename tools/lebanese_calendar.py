from datetime import datetime, timedelta

# ── Full Lebanese & Scouting Calendar ─────────────────────────────────────────

OCCASIONS = {
    "01-01": {"name": "New Year's Day",               "type": "national",      "theme_suggestion": "new beginnings, goals, and hopes"},
    "02-09": {"name": "Saint Maroun's Day",            "type": "national",      "theme_suggestion": "Lebanese heritage and community pride"},
    "03-08": {"name": "International Women's Day",     "type": "international", "theme_suggestion": "equality, respect, and contributions of women"},
    "03-21": {"name": "Mother's Day",                  "type": "national",      "theme_suggestion": "family values, appreciation, and gratitude"},
    "03-25": {"name": "Lebanese Mother's Day",         "type": "national",      "theme_suggestion": "family values, appreciation, and gratitude"},
    "04-07": {"name": "World Health Day",              "type": "international", "theme_suggestion": "health, hygiene, first aid, and well-being"},
    "04-22": {"name": "Earth Day",                     "type": "international", "theme_suggestion": "environmental responsibility and Lebanese nature"},
    "05-01": {"name": "Labour Day",                    "type": "international", "theme_suggestion": "community contribution and civic responsibility"},
    "05-25": {"name": "Lebanese Liberation Day",       "type": "national",      "theme_suggestion": "resilience, national pride, and community strength"},
    "06-01": {"name": "World Children's Day",          "type": "international", "theme_suggestion": "childhood, play, rights, and happiness"},
    "06-05": {"name": "World Environment Day",         "type": "international", "theme_suggestion": "environmental action and nature conservation"},
    "08-04": {"name": "Beirut Port Explosion Memorial","type": "national",      "theme_suggestion": "community support, first aid, and helping those in need"},
    "09-01": {"name": "World Scouts Day",              "type": "scouting",      "theme_suggestion": "scouting values, Scout Promise, and global scouting community"},
    "10-01": {"name": "World Habitat Day",             "type": "international", "theme_suggestion": "community, shelter, and urban responsibility"},
    "10-11": {"name": "International Girl Day",        "type": "international", "theme_suggestion": "empowerment, leadership, and equality for girls"},
    "10-16": {"name": "World Food Day",                "type": "international", "theme_suggestion": "nutrition, food security, and gratitude"},
    "10-22": {"name": "Lebanese Independence Day Eve", "type": "national",      "theme_suggestion": "Lebanese heritage and national pride"},
    "11-01": {"name": "World Scouting Foundation Day", "type": "scouting",      "theme_suggestion": "the history of scouting and Baden-Powell's legacy"},
    "11-22": {"name": "Lebanese Independence Day",     "type": "national",      "theme_suggestion": "Lebanese identity, history, and civic responsibility"},
    "12-01": {"name": "World AIDS Day",                "type": "international", "theme_suggestion": "health awareness, compassion, and community support"},
    "12-10": {"name": "Human Rights Day",              "type": "international", "theme_suggestion": "rights, dignity, and responsibility toward others"},
    "12-25": {"name": "Christmas",                     "type": "religious",     "theme_suggestion": "giving, community, and kindness"},
}

UPCOMING_WINDOW = 7  # days to look ahead for upcoming occasions


def get_occasion(date_str: str = None) -> dict:
    """
    Returns occasion info for a given date, or None if no occasion.

    Args:
        date_str: Date in DD/MM/YYYY format, or None for today

    Returns:
        Dict with occasion details or found=False
    """
    try:
        date = datetime.strptime(date_str, "%d/%m/%Y") if date_str else datetime.today()
    except ValueError:
        date = datetime.today()

    key = date.strftime("%m-%d")

    if key in OCCASIONS:
        occ = OCCASIONS[key]
        return {
            "found":            True,
            "name":             occ["name"],
            "type":             occ["type"],
            "theme_suggestion": occ["theme_suggestion"],
            "date":             date.strftime("%d/%m/%Y"),
            "is_today":         True,
        }

    return {
        "found":            False,
        "name":             None,
        "type":             None,
        "theme_suggestion": None,
        "date":             date.strftime("%d/%m/%Y"),
        "is_today":         False,
    }


def get_upcoming_occasions(date_str: str = None, days: int = UPCOMING_WINDOW) -> list:
    """
    Returns all occasions within the next N days from the given date.

    Args:
        date_str: Starting date in DD/MM/YYYY format
        days:     Number of days to look ahead

    Returns:
        List of upcoming occasion dicts
    """
    try:
        start = datetime.strptime(date_str, "%d/%m/%Y") if date_str else datetime.today()
    except ValueError:
        start = datetime.today()

    upcoming = []
    for i in range(1, days + 1):
        check = start + timedelta(days=i)
        key   = check.strftime("%m-%d")
        if key in OCCASIONS:
            occ = OCCASIONS[key]
            upcoming.append({
                "name":             occ["name"],
                "type":             occ["type"],
                "theme_suggestion": occ["theme_suggestion"],
                "date":             check.strftime("%d/%m/%Y"),
                "days_away":        i,
            })

    return upcoming


def get_calendar_context(date_str: str = None) -> dict:
    """
    Full calendar context for a meeting date.
    Returns current occasion + upcoming occasions within 7 days.
    """
    current  = get_occasion(date_str)
    upcoming = get_upcoming_occasions(date_str)

    return {
        "meeting_date":      date_str or datetime.today().strftime("%d/%m/%Y"),
        "current_occasion":  current,
        "upcoming_occasions": upcoming,
        "has_any_occasion":  current["found"] or len(upcoming) > 0,
    }


if __name__ == "__main__":
    print("=== Test: Earth Day (22/04/2026) ===")
    result = get_calendar_context("22/04/2026")
    print(f"Current occasion: {result['current_occasion']['name']}")
    print(f"Upcoming (7 days): {len(result['upcoming_occasions'])}")

    print()
    print("=== Test: Random date ===")
    result2 = get_calendar_context("15/06/2026")
    print(f"Current occasion: {result2['current_occasion']['name'] or 'None'}")
    for occ in result2["upcoming_occasions"]:
        print(f"  In {occ['days_away']} days: {occ['name']}")

    print()
    print("=== Test: Independence Day (22/11/2026) ===")
    result3 = get_calendar_context("22/11/2026")
    print(f"Current: {result3['current_occasion']['name']}")
    print(f"Theme suggestion: {result3['current_occasion']['theme_suggestion']}")