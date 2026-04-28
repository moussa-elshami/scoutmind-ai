import os
import json
import sys

import chromadb

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


class SentenceTransformerEF:
    """
    Neural embedding function using sentence-transformers all-MiniLM-L6-v2.
    Produces 384-dimensional semantic embeddings. Runs fully offline after the
    first download (~80 MB, cached automatically by sentence-transformers).
    """
    _model = None  # shared across instances to avoid reloading

    def _get_model(self):
        if SentenceTransformerEF._model is None:
            # Tell transformers/sentence-transformers to use PyTorch only.
            # Keras 3 (if installed) is not supported by transformers, so we
            # must suppress TF before the first import of sentence_transformers.
            os.environ.setdefault("USE_TF", "0")
            os.environ.setdefault("USE_KERAS", "0")
            from sentence_transformers import SentenceTransformer
            SentenceTransformerEF._model = SentenceTransformer("all-MiniLM-L6-v2")
        return SentenceTransformerEF._model

    def __call__(self, input: list) -> list:
        model = self._get_model()
        return model.encode(input, convert_to_numpy=True).tolist()

    def embed_query(self, input: list) -> list:
        """ChromaDB 1.x calls this on the query path instead of __call__."""
        return self.__call__(input)

    def name(self) -> str:
        return "sentence-transformer-all-MiniLM-L6-v2"


def get_embedding_function():
    """Returns the shared SentenceTransformer embedding function instance."""
    return SentenceTransformerEF()


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