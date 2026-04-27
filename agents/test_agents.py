"""
Step 4 Test — Individual Agent Tests
Run from scoutmind/ directory:
    python agents/test_agents.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def separator(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


# ── Test 1: Context Awareness Agent (no API key needed) ───────────────────────
separator("TEST 1: Context Awareness Agent")
try:
    from agents.context_awareness import run_context_awareness_agent
    result = run_context_awareness_agent("22/04/2026")
    print(f"  Date:     {result['meeting_date']}")
    print(f"  Occasion: {result['occasion']['name'] or 'None'}")
    print(f"  Weather:  {result['weather']['description']}")
    print(f"  Advisories: {len(result['advisories'])}")
    for a in result["advisories"]:
        print(f"    - {a[:80]}...")
    print("  PASSED")
except Exception as e:
    print(f"  FAILED: {e}")


# ── Test 2: Validation Agent (no API key needed) ──────────────────────────────
separator("TEST 2: Validation Agent")
try:
    from agents.validation import run_validation_agent
    test_activities = [
        {"slot": 1, "activity_name": "Zip Zap Boing",        "activity_type": "game",    "duration_minutes": 10, "energy_level": "high",  "objective": "x", "instructions": ["s"], "materials": ["none"]},
        {"slot": 2, "activity_name": "Friendship Discussion", "activity_type": "lecture", "duration_minutes": 20, "energy_level": "low",   "objective": "x", "instructions": ["s"], "materials": ["board"]},
        {"slot": 3, "activity_name": "Knot Tying",           "activity_type": "skill",   "duration_minutes": 15, "energy_level": "low",   "objective": "x", "instructions": ["s"], "materials": ["rope"]},
        {"slot": 4, "activity_name": "Team Challenge",       "activity_type": "team_challenge", "duration_minutes": 20, "energy_level": "medium", "objective": "x", "instructions": ["s"], "materials": ["sticks"]},
        {"slot": 5, "activity_name": "Story Circle",         "activity_type": "storytelling", "duration_minutes": 15, "energy_level": "low", "objective": "x", "instructions": ["s"], "materials": ["none"]},
        {"slot": 6, "activity_name": "Scout Song",           "activity_type": "song",    "duration_minutes": 10, "energy_level": "medium","objective": "x", "instructions": ["s"], "materials": ["none"]},
        {"slot": 7, "activity_name": "Craft Activity",       "activity_type": "craft",   "duration_minutes": 20, "energy_level": "low",   "objective": "x", "instructions": ["s"], "materials": ["paper"]},
        {"slot": 8, "activity_name": "Relay Race",           "activity_type": "game",    "duration_minutes": 15, "energy_level": "high",  "objective": "x", "instructions": ["s"], "materials": ["cones"]},
        {"slot": 9, "activity_name": "Nature Sound Map",     "activity_type": "game",    "duration_minutes": 10, "energy_level": "low",   "objective": "x", "instructions": ["s"], "materials": ["paper"]},
        {"slot":10, "activity_name": "Capture the Flag",     "activity_type": "game",    "duration_minutes": 15, "energy_level": "high",  "objective": "x", "instructions": ["s"], "materials": ["flags"]},
    ]
    result = run_validation_agent("Cubs", "Friendship", test_activities, 150)
    print(f"  Valid:          {result['is_valid']}")
    print(f"  Total minutes:  {result['total_content_minutes']}")
    print(f"  Activities:     {result['activity_count']}")
    print(f"  Passed checks:  {len(result['passed'])}")
    print(f"  Warnings:       {len(result['warnings'])}")
    print(f"  Issues:         {len(result['issues'])}")
    print(f"  Summary: {result['summary']}")
    print("  PASSED")
except Exception as e:
    print(f"  FAILED: {e}")


# ── Test 3: Formatting Agent (no API key needed) ──────────────────────────────
separator("TEST 3: Formatting Agent")
try:
    from agents.formatting import run_formatting_agent, plan_to_text
    test_activities = [
        {
            "slot": 1, "activity_name": "Zip Zap Boing", "activity_type": "game",
            "duration_minutes": 10, "energy_level": "high",
            "objective": "Energise the group and build focus and reaction speed.",
            "instructions": ["Stand in a circle.", "Pass zip left, zap right, boing reflects."],
            "materials": ["None required"],
            "educational_technique": {"name": "Energiser Break", "application": "Resets attention."},
            "leader_tips": "Keep energy high. Play 2-3 rounds.",
            "theme_connection": "Builds the group connection central to friendship.",
        },
        {
            "slot": 2, "activity_name": "Friendship Discussion", "activity_type": "lecture",
            "duration_minutes": 20, "energy_level": "low",
            "objective": "Explore the qualities of true friendship.",
            "instructions": ["Open with a story.", "Facilitate discussion.", "Think-Pair-Share."],
            "materials": ["Whiteboard", "Markers", "Notebooks"],
            "educational_technique": {"name": "Think-Pair-Share", "application": "Used in discussion phase."},
            "leader_tips": "Encourage quiet members to share.",
            "theme_connection": "Directly explores the meeting theme.",
        },
    ]
    plan = run_formatting_agent(
        unit="Cubs",
        theme="Friendship",
        meeting_date="27/04/2026",
        activities=test_activities,
        master_materials=["Whiteboard", "Markers", "Notebooks and pens"],
    )
    text = plan_to_text(plan)
    print(f"  Plan sections:  {len(plan['schedule'])}")
    print(f"  Materials:      {len(plan['master_materials_list'])}")
    print(f"  Text length:    {len(text)} characters")
    print()
    print(text[:800] + "\n  ...")
    print("  PASSED")
except Exception as e:
    print(f"  FAILED: {e}")


# ── Test 4: LLM Agents (requires ANTHROPIC_API_KEY) ───────────────────────────
separator("TEST 4: LLM Agents (requires API key)")

api_key = os.getenv("ANTHROPIC_API_KEY", "")
if not api_key or api_key.startswith("[INSERT"):
    print("  SKIPPED — No ANTHROPIC_API_KEY found in .env")
    print("  Add your API key to .env and re-run to test LLM agents.")
else:
    # Test Educational Design Agent
    print("  Testing Educational Design Agent...")
    try:
        from agents.educational_design import run_educational_design_agent
        result = run_educational_design_agent("Cubs", "Friendship", 150)
        seq    = result.get("sequence", [])
        print(f"    Sequence slots generated: {len(seq)}")
        print(f"    First activity type: {seq[0]['activity_type'] if seq else 'N/A'}")
        print(f"    Last activity type:  {seq[-1]['activity_type'] if seq else 'N/A'}")
        print("    Educational Design Agent: PASSED")
    except Exception as e:
        print(f"    Educational Design Agent: FAILED — {e}")

    # Test Scouting Context Agent
    print("  Testing Scouting Context Agent...")
    try:
        from agents.scouting_context import run_scouting_context_agent
        test_seq = [
            {"slot": 1, "activity_type": "game",    "energy_level": "high", "duration_minutes": 15, "theme_focus": "energise"},
            {"slot": 2, "activity_type": "lecture",  "energy_level": "low",  "duration_minutes": 20, "theme_focus": "friendship values"},
            {"slot": 3, "activity_type": "game",     "energy_level": "high", "duration_minutes": 10, "theme_focus": "close with energy"},
        ]
        result = run_scouting_context_agent("Cubs", "Friendship", test_seq)
        selected = result.get("selected_activities", [])
        print(f"    Activities selected: {len(selected)}")
        print(f"    RAG pool size used: {result.get('rag_pool_size', 0)}")
        print("    Scouting Context Agent: PASSED")
    except Exception as e:
        print(f"    Scouting Context Agent: FAILED — {e}")

    # Test Activity Generator Agent
    print("  Testing Activity Generator Agent...")
    try:
        from agents.activity_generator import run_activity_generator_agent
        test_selected = [
            {"slot": 1, "activity_id": "ACT021", "activity_name": "Zip Zap Boing",
             "activity_type": "game", "duration_minutes": 10, "energy_level": "high", "source": "knowledge_base"},
            {"slot": 2, "activity_id": "ACT011", "activity_name": "Friendship Web Discussion",
             "activity_type": "lecture", "duration_minutes": 20, "energy_level": "low", "source": "knowledge_base"},
        ]
        result = run_activity_generator_agent("Cubs", "Friendship", test_selected)
        acts   = result.get("activities", [])
        print(f"    Activities generated: {len(acts)}")
        if acts:
            print(f"    First activity: {acts[0].get('activity_name', 'N/A')}")
            print(f"    Materials in first: {len(acts[0].get('materials', []))}")
        print(f"    Master materials: {len(result.get('master_materials_list', []))}")
        print("    Activity Generator Agent: PASSED")
    except Exception as e:
        print(f"    Activity Generator Agent: FAILED — {e}")

separator("ALL TESTS COMPLETE")