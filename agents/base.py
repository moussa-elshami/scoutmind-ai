import os
import sys
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Unit Configuration ────────────────────────────────────────────────────────

UNIT_CONFIG = {
    "Beavers": {
        "age_range":        (3, 7),
        "gender":           "mixed",
        "meeting_duration": 180,
        "content_minutes":  150,
        "description":      "Very young children aged 3-7. Activities must be extremely simple, physical, sensory, and short. Maximum attention span is 10-15 minutes per activity.",
    },
    "Cubs": {
        "age_range":        (7, 11),
        "gender":           "mixed",
        "meeting_duration": 180,
        "content_minutes":  150,
        "description":      "Children aged 7-11. Can handle moderate complexity. Mix of physical and cognitive activities. Attention span 15-20 minutes.",
    },
    "Girl Scouts": {
        "age_range":        (11, 16),
        "gender":           "female",
        "meeting_duration": 240,
        "content_minutes":  210,
        "description":      "Girls aged 11-16. Can handle complex discussions, leadership themes, and multi-step skills. Respond well to collaborative and creative activities.",
    },
    "Boy Scouts": {
        "age_range":        (11, 16),
        "gender":           "male",
        "meeting_duration": 240,
        "content_minutes":  210,
        "description":      "Boys aged 11-16. Respond well to competition, outdoor skills, physical challenges, and leadership activities.",
    },
    "Pioneers": {
        "age_range":        (11, 16),
        "gender":           "female",
        "meeting_duration": 240,
        "content_minutes":  210,
        "description":      "Girls aged 11-16 in the Pioneers program. Focus on community service, leadership, and advanced scouting skills.",
    },
    "Rovers": {
        "age_range":        (16, 22),
        "gender":           "male",
        "meeting_duration": 240,
        "content_minutes":  210,
        "description":      "Young men aged 16-22. Can handle complex topics, self-directed learning, and leadership responsibilities.",
    },
}

ACTIVITY_TYPES = {
    "game":          {"duration_range": (10, 15), "label": "Game"},
    "song":          {"duration_range": (10, 10), "label": "Song / Chant"},
    "skill":         {"duration_range": (15, 20), "label": "Skill Activity"},
    "lecture":       {"duration_range": (15, 20), "label": "Educational Discussion"},
    "storytelling":  {"duration_range": (15, 15), "label": "Storytelling"},
    "team_challenge":{"duration_range": (15, 20), "label": "Team Challenge"},
    "craft":         {"duration_range": (15, 20), "label": "Craft Activity"},
}


def get_llm(temperature: float = 0.7) -> ChatAnthropic:
    """Returns a configured Claude claude-sonnet-4-6 instance."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("[INSERT"):
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. Please add it to your .env file."
        )
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        anthropic_api_key=api_key,
        temperature=temperature,
        max_tokens=32000,
    )


def get_unit_config(unit: str) -> dict:
    return UNIT_CONFIG.get(unit, UNIT_CONFIG["Cubs"])