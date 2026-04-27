import os
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.utils import embedding_functions

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
KB_DIR     = os.path.join(BASE_DIR, "knowledge_base")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

ACTIVITIES_FILE  = os.path.join(KB_DIR, "scouting_activities.json")
TECHNIQUES_FILE  = os.path.join(KB_DIR, "educational_techniques.json")

# ── Collections ───────────────────────────────────────────────────────────────
ACTIVITIES_COLLECTION  = "scouting_activities"
TECHNIQUES_COLLECTION  = "educational_techniques"


def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_DIR)


def get_embedding_function():
    """
    Uses OpenAI text-embedding-3-small when API key is available.
    Falls back to a simple TF-IDF style embedding for offline/dev use.
    """
    from dotenv import load_dotenv
    load_dotenv()
    print("  Using simple keyword embeddings.")
    return SimpleKeywordEmbeddingFunction()


class SimpleKeywordEmbeddingFunction:
    """
    Lightweight fallback embedding function using TF-style word hashing.
    Works fully offline. Replaced by OpenAI embeddings in production.
    """
    VOCAB_SIZE = 512

    def name(self) -> str:
        return "simple_keyword"

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self.__call__(input)

    def __call__(self, input: list[str]) -> list[list[float]]:
        import math
        results = []
        for text in input:
            vec = [0.0] * self.VOCAB_SIZE
            words = text.lower().split()
            for word in words:
                idx = hash(word) % self.VOCAB_SIZE
                vec[idx] += 1.0
            # L2 normalise
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            results.append([v / norm for v in vec])
        return results


def build_activity_document(activity: dict) -> str:
    """Converts an activity dict into a rich text document for embedding."""
    return (
        f"Activity: {activity['activity_name']}. "
        f"Type: {activity['type']}. "
        f"Duration: {activity['duration_minutes']} minutes. "
        f"Suitable for: {', '.join(activity['suitable_units'])}. "
        f"Themes: {', '.join(activity['theme_tags'])}. "
        f"Location: {activity['location']}. "
        f"Energy level: {activity['energy_level']}. "
        f"Objective: {activity['objective']} "
        f"Instructions: {activity['instructions']} "
        f"Materials: {', '.join(activity['materials'])}."
    )


def build_technique_document(technique: dict) -> str:
    """Converts a technique dict into a rich text document for embedding."""
    return (
        f"Technique: {technique['technique_name']}. "
        f"Age range: {technique['age_range'][0]}-{technique['age_range'][1]} years. "
        f"Cognitive load: {technique['cognitive_load']}. "
        f"Compatible with: {', '.join(technique['activity_types_compatible'])}. "
        f"Description: {technique['description']} "
        f"Implementation: {technique['implementation_guide']} "
        f"Scouting adaptation: {technique['scouting_adaptation']} "
        f"Learning outcome: {technique['learning_outcome']}."
    )


def embed_activities(client, ef, force: bool = False):
    """Embeds all scouting activities into ChromaDB."""
    collection = client.get_or_create_collection(
        name=ACTIVITIES_COLLECTION,
        embedding_function=ef,
        metadata={"description": "Lebanese Scouts activity knowledge base"},
    )

    existing = collection.count()
    if existing > 0 and not force:
        print(f"  Activities collection already has {existing} documents. Skipping.")
        return existing

    with open(ACTIVITIES_FILE, "r", encoding="utf-8") as f:
        activities = json.load(f)

    documents = []
    metadatas = []
    ids       = []

    for activity in activities:
        doc = build_activity_document(activity)
        meta = {
            "id":            activity["id"],
            "name":          activity["activity_name"],
            "type":          activity["type"],
            "duration":      activity["duration_minutes"],
            "energy_level":  activity["energy_level"],
            "location":      activity["location"],
            "units":         ", ".join(activity["suitable_units"]),
            "themes":        ", ".join(activity["theme_tags"]),
            "materials":     json.dumps(activity["materials"]),
            "instructions":  activity["instructions"],
            "objective":     activity["objective"],
        }
        documents.append(doc)
        metadatas.append(meta)
        ids.append(activity["id"])

    # Upsert to handle re-runs cleanly
    collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
    print(f"  Embedded {len(documents)} scouting activities.")
    return len(documents)


def embed_techniques(client, ef, force: bool = False):
    """Embeds all educational techniques into ChromaDB."""
    collection = client.get_or_create_collection(
        name=TECHNIQUES_COLLECTION,
        embedding_function=ef,
        metadata={"description": "Educational therapy techniques knowledge base"},
    )

    existing = collection.count()
    if existing > 0 and not force:
        print(f"  Techniques collection already has {existing} documents. Skipping.")
        return existing

    with open(TECHNIQUES_FILE, "r", encoding="utf-8") as f:
        techniques = json.load(f)

    documents = []
    metadatas = []
    ids       = []

    for technique in techniques:
        doc = build_technique_document(technique)
        meta = {
            "id":             technique["id"],
            "name":           technique["technique_name"],
            "age_min":        technique["age_range"][0],
            "age_max":        technique["age_range"][1],
            "cognitive_load": technique["cognitive_load"],
            "compatible":     ", ".join(technique["activity_types_compatible"]),
            "outcome":        technique["learning_outcome"],
            "scouting_adaptation": technique["scouting_adaptation"],
        }
        documents.append(doc)
        metadatas.append(meta)
        ids.append(technique["id"])

    collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
    print(f"  Embedded {len(documents)} educational techniques.")
    return len(documents)


def build_knowledge_base(force: bool = False):
    """Main function to build or rebuild the full knowledge base."""
    print("Building ScoutMind knowledge base...")
    os.makedirs(CHROMA_DIR, exist_ok=True)

    client = get_chroma_client()
    ef     = get_embedding_function()

    n_activities = embed_activities(client, ef, force=force)
    n_techniques = embed_techniques(client, ef, force=force)

    print(f"Knowledge base ready: {n_activities} activities, {n_techniques} techniques.")
    return {"activities": n_activities, "techniques": n_techniques}


if __name__ == "__main__":
    force = "--force" in sys.argv
    build_knowledge_base(force=force)