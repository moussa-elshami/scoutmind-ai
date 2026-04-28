#!/usr/bin/env python3
"""
Knowledge Base Generator for ScoutMind.
Generates additional scouting activities and educational techniques using Claude.

Usage:
    python rag/generate_kb.py              # generate activities + techniques
    python rag/generate_kb.py --rebuild    # also rebuild ChromaDB after generation
"""

import json
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "agents", ".env"))

import anthropic

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
KB_DIR          = os.path.join(BASE_DIR, "knowledge_base")
ACTIVITIES_FILE = os.path.join(KB_DIR, "scouting_activities.json")
TECHNIQUES_FILE = os.path.join(KB_DIR, "educational_techniques.json")

ALL_UNITS   = ["Beavers", "Cubs", "Girl Scouts", "Boy Scouts", "Pioneers", "Rovers"]
OLDER_UNITS = ["Cubs", "Girl Scouts", "Boy Scouts", "Pioneers", "Rovers"]
SENIOR_UNITS = ["Girl Scouts", "Boy Scouts", "Pioneers", "Rovers"]

# ── Batch definitions ─────────────────────────────────────────────────────────
# Each entry: (activity_type, themes_list, suitable_units, count)
ACTIVITY_BATCHES = [
    # Games — young units
    ("game", ["friendship", "listening", "energy", "fun", "belonging"],
     ["Beavers", "Cubs"], 12),

    # Games — older units
    ("game", ["leadership", "teamwork", "adventure", "competition", "trust"],
     OLDER_UNITS, 12),

    # Games — environment & outdoor
    ("game", ["nature", "environment", "exploration", "outdoor skills", "navigation"],
     ALL_UNITS, 10),

    # Skills — practical scouting
    ("skill", ["first aid", "knots", "navigation", "fire safety", "survival"],
     ["Cubs", "Girl Scouts", "Boy Scouts"], 12),

    # Skills — leadership & community
    ("skill", ["leadership", "communication", "service", "citizenship", "responsibility"],
     SENIOR_UNITS, 10),

    # Skills — health & environment
    ("skill", ["health", "environment", "sustainability", "outdoor cooking", "wilderness"],
     ["Boy Scouts", "Pioneers", "Rovers"], 8),

    # Lectures — values & scout law
    ("lecture", ["scout law", "values", "ethics", "courage", "honesty"],
     OLDER_UNITS, 10),

    # Lectures — community & society
    ("lecture", ["citizenship", "community service", "environment", "health", "resilience"],
     SENIOR_UNITS, 8),

    # Storytelling — young units
    ("storytelling", ["courage", "friendship", "kindness", "Lebanese heritage", "nature"],
     ["Beavers", "Cubs", "Girl Scouts", "Boy Scouts"], 10),

    # Storytelling — older units
    ("storytelling", ["leadership", "sacrifice", "community", "adventure", "identity"],
     ["Cubs", "Girl Scouts", "Boy Scouts", "Pioneers"], 8),

    # Team challenges
    ("team_challenge", ["teamwork", "problem-solving", "communication", "leadership", "trust"],
     OLDER_UNITS, 12),

    # Team challenges — outdoor / survival
    ("team_challenge", ["survival", "environment", "creativity", "discipline", "service"],
     SENIOR_UNITS, 8),

    # Crafts — young units
    ("craft", ["creativity", "nature", "friendship", "Lebanese heritage", "community"],
     ["Beavers", "Cubs", "Girl Scouts", "Boy Scouts"], 10),

    # Crafts — community & environment
    ("craft", ["environment", "service", "culture", "sustainability", "identity"],
     ["Cubs", "Girl Scouts", "Boy Scouts", "Pioneers"], 8),

    # Songs — all units
    ("song", ["community", "tradition", "belonging", "nature", "energy", "pride"],
     ALL_UNITS, 10),
]

TECHNIQUE_COUNT = 12  # additional techniques to generate (target: ~24 total)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: list):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def next_activity_id(existing: list) -> int:
    if not existing:
        return 1
    nums = []
    for a in existing:
        try:
            nums.append(int(a["id"].replace("ACT", "")))
        except Exception:
            pass
    return max(nums) + 1 if nums else 1


def next_technique_id(existing: list) -> int:
    if not existing:
        return 1
    nums = []
    for t in existing:
        try:
            nums.append(int(t["id"].replace("EDU", "")))
        except Exception:
            pass
    return max(nums) + 1 if nums else 1


def existing_names(items: list, key: str) -> set:
    return {item.get(key, "").lower() for item in items}


# ── Activity generation ───────────────────────────────────────────────────────

ACTIVITY_SYSTEM = """You are a specialist in Lebanese Scouts Association meeting design.
Generate scouting activities in strict JSON format only — no explanation, no markdown.

Each activity must include ALL these fields:
- id: string placeholder (will be replaced — use "PLACEHOLDER")
- activity_name: unique, specific, creative name
- type: exactly as specified
- duration_minutes: integer within type's range
- suitable_units: list of unit names from the provided list
- gender: "mixed", "female", or "male"
- location: "indoors", "outdoors", or "indoors/outdoors"
- theme_tags: list of 3-5 relevant theme strings
- objective: one clear sentence stating what members will achieve
- instructions: numbered step-by-step string (at least 5 steps, use \\n between steps)
- materials: list of specific items with quantities
- energy_level: "high", "medium", or "low"
- indoor_outdoor: "indoors", "outdoors", or "both"

Respond with ONLY a valid JSON array of activity objects."""


def generate_activities_batch(
    client: anthropic.Anthropic,
    activity_type: str,
    themes: list,
    suitable_units: list,
    count: int,
    existing_names_set: set,
) -> list:
    duration_map = {
        "game": "10-15", "song": "10", "skill": "15-20",
        "lecture": "15-20", "storytelling": "15",
        "team_challenge": "15-20", "craft": "15-20",
    }
    duration_range = duration_map.get(activity_type, "15")

    prompt = f"""Generate {count} scouting activities with these specifications:

Activity type: {activity_type}
Duration: {duration_range} minutes
Themes to cover (spread across activities): {', '.join(themes)}
Suitable units: {', '.join(suitable_units)}
Context: Lebanese Scouts Association — activities should be culturally appropriate for Lebanon,
          practical for a weekly meeting, and aligned with scouting values.

Requirements:
- Every activity name must be unique and not in this existing list: {list(existing_names_set)[:30]}
- Instructions must have at least 5 numbered steps
- Materials must list specific items with quantities
- Vary energy_level appropriately for the activity type
- For 'game': energy_level should be "high" or "medium"
- For 'song': energy_level should be "medium"
- For 'skill', 'lecture', 'craft': energy_level should be "low" or "medium"
- For 'team_challenge': energy_level should be "high" or "medium"
- For 'storytelling': energy_level should be "low"
- Set gender to "mixed" unless the activity is specifically designed for one gender
- Make each activity genuinely useful, specific, and professionally described

Return a JSON array of {count} activity objects."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[
            {"role": "user", "content": prompt}
        ],
        system=ACTIVITY_SYSTEM,
    )

    content = response.content[0].text.strip()

    # Strip markdown fences
    if content.startswith("```"):
        parts = content.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                content = part
                break

    activities = json.loads(content)

    # Filter duplicates by name
    filtered = []
    for act in activities:
        name = act.get("activity_name", "").lower()
        if name and name not in existing_names_set:
            filtered.append(act)
            existing_names_set.add(name)

    return filtered


# ── Technique generation ──────────────────────────────────────────────────────

TECHNIQUE_SYSTEM = """You are an expert in educational therapy and scout leader training.
Generate educational techniques for the Lebanese Scouts Association in strict JSON format only.

Each technique must include ALL these fields:
- id: string placeholder (will be replaced — use "PLACEHOLDER")
- technique_name: unique, specific name
- age_range: [min_age, max_age] integer list
- cognitive_load: "low", "medium", or "high"
- activity_types_compatible: list of activity types from: game, song, skill, lecture, storytelling, team_challenge, craft
- description: 2-3 sentence explanation of the technique
- implementation_guide: numbered step-by-step string (at least 5 steps, use \\n between steps)
- scouting_adaptation: specific explanation of how to apply this in a Lebanese scouts context
- learning_outcome: one clear sentence stating the measurable benefit

Respond with ONLY a valid JSON array of technique objects."""


def generate_techniques_batch(
    client: anthropic.Anthropic,
    count: int,
    existing_names_set: set,
) -> list:
    prompt = f"""Generate {count} educational therapy techniques suitable for scout meeting facilitation.

These techniques should:
- Be evidence-based and used in educational therapy / educational psychology
- Be practical for scout leaders without formal teaching training
- Cover a range of ages (from 3 to 19 years)
- Complement the existing techniques (do not duplicate): {list(existing_names_set)}
- Include techniques suitable for outdoor learning, group dynamics, emotional regulation,
  memory retention, leadership development, and physical/kinesthetic learning

Examples of categories NOT already covered that you could include:
active recall, spaced repetition, inquiry-based learning, project-based learning,
growth mindset activities, mindfulness for young scouts, cooperative learning structures,
outdoor experiential learning, kinesthetic anchoring, storytelling frameworks,
conflict resolution techniques, metacognitive strategies

Return a JSON array of {count} technique objects."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        messages=[
            {"role": "user", "content": prompt}
        ],
        system=TECHNIQUE_SYSTEM,
    )

    content = response.content[0].text.strip()

    if content.startswith("```"):
        parts = content.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                content = part
                break

    techniques = json.loads(content)

    filtered = []
    for tech in techniques:
        name = tech.get("technique_name", "").lower()
        if name and name not in existing_names_set:
            filtered.append(tech)
            existing_names_set.add(name)

    return filtered


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    rebuild = "--rebuild" in sys.argv

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("[INSERT"):
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # ── Generate Activities ───────────────────────────────────────────────────
    print("\n=== Generating Scouting Activities ===")
    activities   = load_json(ACTIVITIES_FILE)
    names_set    = existing_names(activities, "activity_name")
    start_id     = next_activity_id(activities)
    total_added  = 0

    print(f"  Existing activities: {len(activities)}")
    print(f"  Next ID: ACT{start_id:03d}")
    print(f"  Batches to run: {len(ACTIVITY_BATCHES)}\n")

    for i, (act_type, themes, units, count) in enumerate(ACTIVITY_BATCHES, 1):
        print(f"  Batch {i}/{len(ACTIVITY_BATCHES)}: {count}x {act_type} "
              f"[{', '.join(themes[:2])}...] ...", end=" ", flush=True)
        try:
            batch = generate_activities_batch(client, act_type, themes, units, count, names_set)

            # Assign real IDs
            for act in batch:
                act["id"] = f"ACT{start_id:03d}"
                act["type"] = act_type  # ensure type is correct
                start_id += 1

            activities.extend(batch)
            save_json(ACTIVITIES_FILE, activities)
            total_added += len(batch)
            print(f"got {len(batch)}, total now {len(activities)}")

        except Exception as e:
            print(f"FAILED — {e}")

        time.sleep(0.5)  # brief pause between calls

    print(f"\n  Activities complete: added {total_added}, total {len(activities)}")

    # ── Generate Techniques ───────────────────────────────────────────────────
    print("\n=== Generating Educational Techniques ===")
    techniques       = load_json(TECHNIQUES_FILE)
    tech_names_set   = existing_names(techniques, "technique_name")
    tech_start_id    = next_technique_id(techniques)
    tech_total_added = 0

    print(f"  Existing techniques: {len(techniques)}")
    print(f"  Generating: {TECHNIQUE_COUNT} more ...", end=" ", flush=True)

    try:
        batch = generate_techniques_batch(client, TECHNIQUE_COUNT, tech_names_set)

        for tech in batch:
            tech["id"] = f"EDU{tech_start_id:03d}"
            tech_start_id += 1

        techniques.extend(batch)
        save_json(TECHNIQUES_FILE, techniques)
        tech_total_added = len(batch)
        print(f"got {len(batch)}, total now {len(techniques)}")

    except Exception as e:
        print(f"FAILED — {e}")

    print(f"\n  Techniques complete: added {tech_total_added}, total {len(techniques)}")

    # ── Rebuild ChromaDB ──────────────────────────────────────────────────────
    if rebuild:
        print("\n=== Rebuilding ChromaDB ===")
        import shutil
        chroma_dir = os.path.join(BASE_DIR, "chroma_db")
        if os.path.exists(chroma_dir):
            shutil.rmtree(chroma_dir)
            print("  Deleted old chroma_db.")
        from rag.embeddings import build_knowledge_base
        build_knowledge_base(force=True)
    else:
        print("\n  Tip: run with --rebuild to also rebuild ChromaDB automatically.")

    print("\nDone.")


if __name__ == "__main__":
    main()
