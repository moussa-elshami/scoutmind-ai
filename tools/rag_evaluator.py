"""
RAG Evaluation Script — ScoutMind
==================================
Computes Precision@K, Recall@K, and Mean Reciprocal Rank (MRR) across two
configuration axes:

  1. Retrieval depth  : K = 3, 5, 10
  2. Embedding model  : all-MiniLM-L6-v2  (384-dim, fast)
                        all-mpnet-base-v2  (768-dim, higher quality)

Embeddings are computed directly via sentence-transformers (no ChromaDB
dependency) so the evaluation is fully reproducible and self-contained.

Ground truth: for each test query, "relevant" = activity whose theme_tags
contain at least one of the specified tags, whose suitable_units include the
target unit, and (when specified) whose type matches the expected type(s).

Usage:
    python tools/rag_evaluator.py
"""

import os
import sys
import json

os.environ.setdefault("USE_TF",    "0")
os.environ.setdefault("USE_KERAS", "0")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np
from sentence_transformers import SentenceTransformer

KB_PATH = os.path.join(ROOT, "rag", "knowledge_base", "scouting_activities.json")

# ── Embedding models under comparison ────────────────────────────────────────
MODELS = {
    "MiniLM-L6-v2  (384-dim)": "all-MiniLM-L6-v2",
    "mpnet-base-v2 (768-dim)": "all-mpnet-base-v2",
}

K_VALUES = [3, 5, 10]

# ── Test query set ────────────────────────────────────────────────────────────
# Each entry defines:
#   query          : free-text retrieval query
#   unit           : scout unit — activity must list this in suitable_units
#   relevant_tags  : activity must contain AT LEAST ONE of these theme_tags
#   relevant_types : activity type must be one of these (None = any type)
#   description    : short label for the report table
TEST_QUERIES = [
    {
        "id": "Q01",
        "query": "teamwork communication game Cubs",
        "unit": "Cubs",
        "relevant_tags":  ["teamwork", "communication", "problem-solving"],
        "relevant_types": ["game"],
        "description": "Teamwork game — Cubs",
    },
    {
        "id": "Q02",
        "query": "nature outdoor environment awareness activity",
        "unit": "Cubs",
        "relevant_tags":  ["nature", "environment", "awareness", "mindfulness"],
        "relevant_types": None,
        "description": "Nature/environment — any type",
    },
    {
        "id": "Q03",
        "query": "first aid safety skill health training",
        "unit": "Boy Scouts",
        "relevant_tags":  ["first aid", "safety", "health", "emergency"],
        "relevant_types": ["skill"],
        "description": "First aid skill — Boy Scouts",
    },
    {
        "id": "Q04",
        "query": "knot tying rope camping survival skill",
        "unit": "Boy Scouts",
        "relevant_tags":  ["knots", "survival", "camping", "skills"],
        "relevant_types": ["skill"],
        "description": "Knot skills — Boy Scouts",
    },
    {
        "id": "Q05",
        "query": "friendship empathy values discussion",
        "unit": "Cubs",
        "relevant_tags":  ["friendship", "values", "empathy", "community"],
        "relevant_types": None,
        "description": "Friendship/values — Cubs",
    },
    {
        "id": "Q06",
        "query": "high energy fun outdoor game young scouts",
        "unit": "Beavers",
        "relevant_tags":  ["energy", "fun", "fitness"],
        "relevant_types": ["game"],
        "description": "High-energy game — Beavers",
    },
    {
        "id": "Q07",
        "query": "environmental responsibility Lebanon nature conservation",
        "unit": "Pioneers",
        "relevant_tags":  ["environment", "nature", "responsibility", "Lebanon"],
        "relevant_types": None,
        "description": "Environment/responsibility — Pioneers",
    },
    {
        "id": "Q08",
        "query": "leadership team challenge problem solving cooperation",
        "unit": "Rovers",
        "relevant_tags":  ["leadership", "teamwork", "problem-solving", "cooperation"],
        "relevant_types": ["team_challenge", "game"],
        "description": "Leadership challenge — Rovers",
    },
    {
        "id": "Q09",
        "query": "navigation map reading outdoor adventure exploration",
        "unit": "Boy Scouts",
        "relevant_tags":  ["navigation", "adventure", "nature"],
        "relevant_types": ["game", "skill"],
        "description": "Navigation — Boy Scouts",
    },
    {
        "id": "Q10",
        "query": "community song tradition belonging group identity",
        "unit": "Cubs",
        "relevant_tags":  ["community", "belonging", "tradition", "energy"],
        "relevant_types": ["song"],
        "description": "Song/community — Cubs",
    },
    {
        "id": "Q11",
        "query": "scout law values character integrity honour",
        "unit": "Boy Scouts",
        "relevant_tags":  ["scout law", "values", "character", "integrity"],
        "relevant_types": ["lecture"],
        "description": "Scout law values — Boy Scouts",
    },
    {
        "id": "Q12",
        "query": "creative craft art making handcraft activity",
        "unit": "Girl Scouts",
        "relevant_tags":  ["creativity", "craft", "art", "expression"],
        "relevant_types": ["craft"],
        "description": "Creative craft — Girl Scouts",
    },
    {
        "id": "Q13",
        "query": "storytelling heritage scouting tradition culture",
        "unit": "Cubs",
        "relevant_tags":  ["storytelling", "heritage", "tradition", "culture"],
        "relevant_types": ["storytelling"],
        "description": "Storytelling — Cubs",
    },
    {
        "id": "Q14",
        "query": "mindfulness awareness sensory calm reflection",
        "unit": "Girl Scouts",
        "relevant_tags":  ["mindfulness", "awareness", "nature", "reflection"],
        "relevant_types": None,
        "description": "Mindfulness/awareness — Girl Scouts",
    },
    {
        "id": "Q15",
        "query": "cooperation build together challenge team Pioneers",
        "unit": "Pioneers",
        "relevant_tags":  ["teamwork", "cooperation", "problem-solving", "communication"],
        "relevant_types": ["team_challenge", "game"],
        "description": "Cooperative challenge — Pioneers",
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_activities() -> list:
    with open(KB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_document(activity: dict) -> str:
    """Rich text representation used for embedding — matches the production pipeline."""
    return (
        f"Activity: {activity['activity_name']}. "
        f"Type: {activity['type']}. "
        f"Themes: {', '.join(activity.get('theme_tags', []))}. "
        f"Suitable for: {', '.join(activity.get('suitable_units', []))}. "
        f"Location: {activity.get('location', '')}. "
        f"Energy: {activity.get('energy_level', '')}. "
        f"Objective: {activity.get('objective', '')}"
    )


def is_relevant(activity: dict, relevant_tags: list, unit: str,
                relevant_types: list | None) -> bool:
    tag_match  = any(t in activity.get("theme_tags", [])    for t in relevant_tags)
    unit_match = unit in activity.get("suitable_units", [])
    type_match = relevant_types is None or activity.get("type") in relevant_types
    return tag_match and unit_match and type_match


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def precision_at_k(ranked: list, relevant: set, k: int) -> float:
    hits = sum(1 for _id in ranked[:k] if _id in relevant)
    return hits / k


def recall_at_k(ranked: list, relevant: set, k: int) -> float:
    if not relevant:
        return 0.0
    hits = sum(1 for _id in ranked[:k] if _id in relevant)
    return hits / len(relevant)


def reciprocal_rank(ranked: list, relevant: set, k: int) -> float:
    for i, _id in enumerate(ranked[:k]):
        if _id in relevant:
            return 1.0 / (i + 1)
    return 0.0


# ── Core evaluation ───────────────────────────────────────────────────────────

def evaluate(model_name: str, activities: list) -> dict:
    """
    Embeds all activities and queries using model_name, ranks by cosine
    similarity, and returns aggregated P@K / R@K / MRR for each K.
    """
    print(f"    Loading '{model_name}' ...", flush=True)
    model = SentenceTransformer(model_name)

    docs           = [build_document(a) for a in activities]
    doc_embeddings = model.encode(docs, convert_to_numpy=True,
                                  show_progress_bar=False, batch_size=32)

    buckets = {k: {"P": [], "R": [], "RR": []} for k in K_VALUES}
    skipped = 0

    for q in TEST_QUERIES:
        relevant_ids = {
            a["id"] for a in activities
            if is_relevant(a, q["relevant_tags"], q["unit"], q.get("relevant_types"))
        }
        if not relevant_ids:
            skipped += 1
            continue

        q_emb  = model.encode([q["query"]], convert_to_numpy=True,
                               show_progress_bar=False)[0]
        ranked = sorted(
            enumerate(activities),
            key=lambda x: cosine_sim(q_emb, doc_embeddings[x[0]]),
            reverse=True,
        )
        ranked_ids = [activities[i]["id"] for i, _ in ranked]

        for k in K_VALUES:
            buckets[k]["P"].append( precision_at_k(ranked_ids, relevant_ids, k))
            buckets[k]["R"].append( recall_at_k(   ranked_ids, relevant_ids, k))
            buckets[k]["RR"].append(reciprocal_rank(ranked_ids, relevant_ids, k))

    if skipped:
        print(f"    WARNING: {skipped} query/queries skipped (no relevant activities found).")

    n = len(TEST_QUERIES) - skipped
    return {
        k: {
            "P@K": round(sum(buckets[k]["P"])  / n, 3) if n else 0.0,
            "R@K": round(sum(buckets[k]["R"])  / n, 3) if n else 0.0,
            "MRR": round(sum(buckets[k]["RR"]) / n, 3) if n else 0.0,
            "n":   n,
        }
        for k in K_VALUES
    }


# ── Printing helpers ──────────────────────────────────────────────────────────

def print_results(label: str, results: dict):
    print(f"\n  {label}")
    print(f"  {'K':<6}  {'P@K':>7}  {'R@K':>7}  {'MRR':>7}")
    print(f"  {'-'*34}")
    for k in K_VALUES:
        r = results[k]
        print(f"  K={k:<4}  {r['P@K']:>7.3f}  {r['R@K']:>7.3f}  {r['MRR']:>7.3f}")


def print_comparison(all_results: dict):
    labels  = list(all_results.keys())
    l1, l2  = labels[0], labels[1]
    r1, r2  = all_results[l1], all_results[l2]

    col = 22
    print(f"\n  {'':6}  {'Metric':5}  {l1:>{col}}  {l2:>{col}}  {'Better':>12}")
    print(f"  {'-' * (6 + 5 + col * 2 + 20)}")
    for k in K_VALUES:
        for metric in ["P@K", "R@K", "MRR"]:
            v1 = r1[k][metric]
            v2 = r2[k][metric]
            winner = l1 if v1 > v2 else (l2 if v2 > v1 else "tie")
            print(f"  K={k:<4}  {metric:5}  {v1:>{col}.3f}  {v2:>{col}.3f}  {winner:>12}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    SEP = "=" * 65

    print(SEP)
    print("  ScoutMind — RAG Retrieval Evaluation")
    print(SEP)

    activities = load_activities()
    print(f"  Knowledge base: {len(activities)} activities loaded.")

    # Ground-truth coverage report
    print(f"\n  Test set: {len(TEST_QUERIES)} queries")
    print(f"  {'ID':<5}  {'Description':<45}  {'Relevant':>8}")
    print(f"  {'-' * 63}")
    for q in TEST_QUERIES:
        rel = [a for a in activities
               if is_relevant(a, q["relevant_tags"], q["unit"], q.get("relevant_types"))]
        print(f"  {q['id']:<5}  {q['description']:<45}  {len(rel):>8}")

    all_results = {}
    for label, model_id in MODELS.items():
        print(f"\n{SEP}")
        print(f"  Configuration: {label}")
        print(SEP)
        all_results[label] = evaluate(model_id, activities)
        print_results(label, all_results[label])

    print(f"\n{SEP}")
    print("  COMPARISON  (all K values, all metrics)")
    print(SEP)
    print_comparison(all_results)

    print(f"\n{SEP}")
    print("  Evaluation complete.")
    print(SEP)


if __name__ == "__main__":
    main()
