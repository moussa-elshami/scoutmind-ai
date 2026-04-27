import os
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.utils import embedding_functions
from rag.embeddings import (
    get_chroma_client,
    get_embedding_function,
    ACTIVITIES_COLLECTION,
    TECHNIQUES_COLLECTION,
)

# ── Unit Age Mapping ──────────────────────────────────────────────────────────
UNIT_AGE_MAP = {
    "Beavers":     (3,  7),
    "Cubs":        (7,  11),
    "Girl Scouts": (11, 16),
    "Boy Scouts":  (11, 16),
    "Pioneers":    (11, 16),
    "Rovers":      (16, 22),
}


def get_unit_age(unit: str) -> tuple:
    return UNIT_AGE_MAP.get(unit, (7, 16))


def retrieve_activities(
    query: str,
    unit: str,
    n_results: int = 10,
    activity_type: str = None,
    energy_level: str = None,
) -> list[dict]:
    """
    Retrieves relevant scouting activities from ChromaDB.

    Args:
        query:         Semantic search query (e.g. 'friendship teamwork game')
        unit:          Scout unit name (e.g. 'Cubs')
        n_results:     Number of results to retrieve before filtering
        activity_type: Optional filter ('game', 'skill', 'lecture', etc.)
        energy_level:  Optional filter ('high', 'medium', 'low')

    Returns:
        List of activity dicts with full metadata
    """
    client     = get_chroma_client()
    ef         = get_embedding_function()
    collection = client.get_or_create_collection(
        name=ACTIVITIES_COLLECTION,
        embedding_function=ef,
    )

    where_filters = []

    if activity_type:
        where_filters.append({"type": {"$eq": activity_type}})

    if energy_level:
        where_filters.append({"energy_level": {"$eq": energy_level}})

    where = {"$and": where_filters} if len(where_filters) > 1 else \
            where_filters[0] if len(where_filters) == 1 else None

    count = collection.count()
    if count == 0:
        return []

    query_kwargs = {
        "query_texts": [query],
        "n_results":   min(n_results, count),
    }
    if where:
        query_kwargs["where"] = where

    results = collection.query(**query_kwargs)

    activities = []
    if results and results["metadatas"]:
        for i, meta in enumerate(results["metadatas"][0]):
            # Filter by unit suitability
            units_str = meta.get("units", "")
            if unit and unit not in units_str:
                continue

            activities.append({
                "id":           meta.get("id"),
                "name":         meta.get("name"),
                "type":         meta.get("type"),
                "duration":     meta.get("duration"),
                "energy_level": meta.get("energy_level"),
                "location":     meta.get("location"),
                "units":        units_str,
                "themes":       meta.get("themes"),
                "objective":    meta.get("objective"),
                "instructions": meta.get("instructions"),
                "materials":    json.loads(meta.get("materials", "[]")),
                "distance":     results["distances"][0][i] if results.get("distances") else None,
            })

    return activities


def retrieve_techniques(
    query: str,
    unit: str,
    activity_type: str = None,
    n_results: int = 5,
) -> list[dict]:
    """
    Retrieves relevant educational therapy techniques from ChromaDB.

    Args:
        query:         Semantic search query
        unit:          Scout unit name
        activity_type: Optional filter for compatible activity types
        n_results:     Number of results

    Returns:
        List of technique dicts
    """
    client     = get_chroma_client()
    ef         = get_embedding_function()
    collection = client.get_or_create_collection(
        name=TECHNIQUES_COLLECTION,
        embedding_function=ef,
    )

    age_min, age_max = get_unit_age(unit)

    count = collection.count()
    if count == 0:
        return []

    query_kwargs = {
        "query_texts": [query],
        "n_results":   min(n_results, count),
    }

    results = collection.query(**query_kwargs)

    techniques = []
    if results and results["metadatas"]:
        for i, meta in enumerate(results["metadatas"][0]):
            # Filter by age range compatibility
            tech_age_min = meta.get("age_min", 0)
            tech_age_max = meta.get("age_max", 99)
            if not (tech_age_min <= age_max and tech_age_max >= age_min):
                continue

            # Filter by activity type compatibility if specified
            if activity_type:
                compatible = meta.get("compatible", "")
                if activity_type not in compatible:
                    continue

            techniques.append({
                "id":                   meta.get("id"),
                "name":                 meta.get("name"),
                "cognitive_load":       meta.get("cognitive_load"),
                "compatible":           meta.get("compatible"),
                "outcome":              meta.get("outcome"),
                "scouting_adaptation":  meta.get("scouting_adaptation"),
                "distance":             results["distances"][0][i] if results.get("distances") else None,
            })

    return techniques


def retrieve_for_meeting(
    theme: str,
    unit: str,
    total_content_minutes: int,
) -> dict:
    """
    Master retrieval function. Returns a structured set of activities and
    techniques for all required activity slots in the meeting.

    Args:
        theme:                 Meeting theme (e.g. 'friendship')
        unit:                  Scout unit
        total_content_minutes: Minutes available after removing fixed bookends

    Returns:
        Dict with 'activities' and 'techniques' for agent consumption
    """
    query = f"{theme} scouting activity {unit}"

    # Retrieve a broad set across all types
    all_activities = retrieve_activities(query, unit, n_results=25)

    # Categorise by type
    games      = [a for a in all_activities if a["type"] == "game"]
    skills     = [a for a in all_activities if a["type"] == "skill"]
    lectures   = [a for a in all_activities if a["type"] == "lecture"]
    songs      = [a for a in all_activities if a["type"] == "song"]
    stories    = [a for a in all_activities if a["type"] == "storytelling"]
    challenges = [a for a in all_activities if a["type"] == "team_challenge"]
    crafts     = [a for a in all_activities if a["type"] == "craft"]

    # Ensure energetic options for start and end
    high_energy = [a for a in all_activities if a["energy_level"] == "high"]

    # Retrieve relevant educational techniques
    techniques = retrieve_techniques(query, unit, n_results=5)

    return {
        "theme":                 theme,
        "unit":                  unit,
        "total_content_minutes": total_content_minutes,
        "activities": {
            "games":      games,
            "skills":     skills,
            "lectures":   lectures,
            "songs":      songs,
            "stories":    stories,
            "challenges": challenges,
            "crafts":     crafts,
            "high_energy": high_energy,
            "all":        all_activities,
        },
        "techniques": techniques,
    }