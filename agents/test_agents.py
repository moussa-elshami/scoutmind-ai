"""
ScoutMind test suite — pure-logic agents and tools (no API key required).
LLM-dependent agents are skipped automatically when no key is present.

Run all tests:
    python -m unittest agents/test_agents.py -v

Run only no-key tests:
    python -m unittest agents/test_agents.py -v -k "not LLM" (pytest)
    python agents/test_agents.py                              (standalone)
"""
import os
import json
import unittest
from unittest.mock import MagicMock, patch

from dotenv import load_dotenv
load_dotenv()

_HAS_API_KEY = bool(os.getenv("ANTHROPIC_API_KEY", "").strip()) and \
               not os.getenv("ANTHROPIC_API_KEY", "").startswith("[INSERT")


# ── Shared fixtures ────────────────────────────────────────────────────────────

def _make_valid_activities(total_minutes: int = 150):
    """Returns a structurally valid activity list summing to total_minutes."""
    return [
        {"slot": 1, "activity_name": "Zip Zap",         "activity_type": "game",         "duration_minutes": 10, "energy_level": "high",   "objective": "x", "instructions": ["s"], "materials": ["none"]},
        {"slot": 2, "activity_name": "Values Chat",      "activity_type": "lecture",      "duration_minutes": 20, "energy_level": "low",    "objective": "x", "instructions": ["s"], "materials": ["board"]},
        {"slot": 3, "activity_name": "Scout Song",       "activity_type": "song",         "duration_minutes": 10, "energy_level": "medium", "objective": "x", "instructions": ["s"], "materials": ["none"]},
        {"slot": 4, "activity_name": "Knot Tying",       "activity_type": "skill",        "duration_minutes": 20, "energy_level": "low",    "objective": "x", "instructions": ["s"], "materials": ["rope"]},
        {"slot": 5, "activity_name": "Bridge Builder",   "activity_type": "team_challenge","duration_minutes": 20,"energy_level": "medium", "objective": "x", "instructions": ["s"], "materials": ["sticks"]},
        {"slot": 6, "activity_name": "Story Circle",     "activity_type": "storytelling", "duration_minutes": 15, "energy_level": "low",    "objective": "x", "instructions": ["s"], "materials": ["none"]},
        {"slot": 7, "activity_name": "Friendship Craft", "activity_type": "craft",        "duration_minutes": 20, "energy_level": "low",    "objective": "x", "instructions": ["s"], "materials": ["paper"]},
        {"slot": 8, "activity_name": "Relay Race",       "activity_type": "game",         "duration_minutes": total_minutes - 115, "energy_level": "high", "objective": "x", "instructions": ["s"], "materials": ["cones"]},
    ]


def _make_formatting_activities():
    """Returns richer activities suitable for run_formatting_agent."""
    return [
        {
            "slot": 1, "activity_name": "Zip Zap Boing", "activity_type": "game",
            "duration_minutes": 10, "energy_level": "high",
            "objective": "Warm up and build focus.",
            "instructions": ["Stand in a circle.", "Pass zip left, zap right, boing reflects."],
            "materials": ["None required"],
            "educational_technique": {"name": "Energiser Break", "application": "Resets attention."},
            "leader_tips": "Keep energy high.", "theme_connection": "Builds group cohesion.",
            "source": "knowledge_base", "activity_id": "ACT001",
        },
        {
            "slot": 2, "activity_name": "Friendship Discussion", "activity_type": "lecture",
            "duration_minutes": 20, "energy_level": "low",
            "objective": "Explore qualities of friendship.",
            "instructions": ["Open with a short story.", "Facilitate discussion.", "Think-Pair-Share."],
            "materials": ["Whiteboard", "Markers"],
            "educational_technique": {"name": "Think-Pair-Share", "application": "Includes all voices."},
            "leader_tips": "Encourage quiet members.", "theme_connection": "Core theme of meeting.",
            "source": "generated", "activity_id": "NEW",
        },
    ]


# ══════════════════════════════════════════════════════════════════════════════
# 1. Lebanese Calendar
# ══════════════════════════════════════════════════════════════════════════════

class TestLebanesCalendar(unittest.TestCase):

    def setUp(self):
        from tools.lebanese_calendar import get_occasion, get_upcoming_occasions, get_calendar_context
        self.get_occasion          = get_occasion
        self.get_upcoming_occasions = get_upcoming_occasions
        self.get_calendar_context  = get_calendar_context

    def test_earth_day_detected(self):
        result = self.get_occasion("22/04/2026")
        self.assertTrue(result["found"])
        self.assertIn("Earth", result["name"])
        self.assertIn("theme_suggestion", result)
        self.assertTrue(len(result["theme_suggestion"]) > 0)

    def test_independence_day_detected(self):
        result = self.get_occasion("22/11/2026")
        self.assertTrue(result["found"])
        self.assertIn("Independence", result["name"])

    def test_scouts_day_detected(self):
        result = self.get_occasion("01/09/2026")
        self.assertTrue(result["found"])
        self.assertIn("Scout", result["name"])

    def test_generic_date_returns_not_found(self):
        result = self.get_occasion("14/06/2026")
        self.assertFalse(result["found"])
        self.assertIsNone(result["name"])

    def test_invalid_date_does_not_crash(self):
        result = self.get_occasion("not-a-date")
        self.assertIn("found", result)

    def test_none_date_does_not_crash(self):
        result = self.get_occasion(None)
        self.assertIn("found", result)

    def test_upcoming_occasions_returns_list(self):
        result = self.get_upcoming_occasions("15/04/2026", days=14)
        self.assertIsInstance(result, list)
        # Earth Day (22/04) is 7 days after 15/04 — must appear
        names = [o["name"] for o in result]
        self.assertTrue(any("Earth" in n for n in names))

    def test_upcoming_occasions_days_away_correct(self):
        result = self.get_upcoming_occasions("15/04/2026", days=14)
        for occ in result:
            self.assertGreater(occ["days_away"], 0)
            self.assertLessEqual(occ["days_away"], 14)

    def test_calendar_context_structure(self):
        ctx = self.get_calendar_context("22/04/2026")
        self.assertIn("meeting_date",       ctx)
        self.assertIn("current_occasion",   ctx)
        self.assertIn("upcoming_occasions", ctx)
        self.assertIn("has_any_occasion",   ctx)
        self.assertTrue(ctx["has_any_occasion"])


# ══════════════════════════════════════════════════════════════════════════════
# 2. Time Validator
# ══════════════════════════════════════════════════════════════════════════════

class TestTimeValidator(unittest.TestCase):

    def setUp(self):
        from tools.time_validator import validate_timing
        self.validate = validate_timing

    def _activities(self, total: int):
        """8-activity list summing to total. Middle 6 use types with max≥20 min so
        the validator has room to both extend and shorten them."""
        types = ["game", "lecture", "skill", "lecture", "team_challenge", "craft", "skill", "game"]
        base  = total // 8
        rem   = total % 8
        return [
            {
                "slot":            i + 1,
                "activity_name":   f"{t.title()} {i + 1}",
                "activity_type":   t,
                "duration_minutes": base + (1 if i < rem else 0),
            }
            for i, t in enumerate(types)
        ]

    def test_exact_timing_status_ok(self):
        result = self.validate("Cubs", self._activities(150))
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["within_tolerance"])
        self.assertEqual(result["adjustments_made"], [])

    def test_within_tolerance_unchanged(self):
        # 148 min instead of 150 — within the 5-min tolerance
        result = self.validate("Cubs", self._activities(148))
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["within_tolerance"])

    def test_over_timing_shortened(self):
        result = self.validate("Cubs", self._activities(180))
        self.assertEqual(result["status"], "adjusted_shorter")
        adjusted_total = sum(a["duration_minutes"] for a in result["activities"])
        self.assertLessEqual(adjusted_total, 155)
        self.assertGreater(len(result["adjustments_made"]), 0)

    def test_under_timing_extended(self):
        result = self.validate("Cubs", self._activities(100))
        self.assertEqual(result["status"], "adjusted_longer")
        adjusted_total = sum(a["duration_minutes"] for a in result["activities"])
        self.assertGreater(adjusted_total, 100)
        self.assertGreater(len(result["adjustments_made"]), 0)

    def test_custom_duration_respected(self):
        # 4-hour meeting → content = 240-30 = 210 min
        result = self.validate("Girl Scouts", self._activities(210), custom_duration=240)
        self.assertEqual(result["content_minutes"], 210)

    def test_output_always_has_activities(self):
        result = self.validate("Cubs", self._activities(150))
        self.assertIn("activities", result)
        self.assertGreater(len(result["activities"]), 0)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Plan Evaluator
# ══════════════════════════════════════════════════════════════════════════════

class TestPlanEvaluator(unittest.TestCase):

    def setUp(self):
        from tools.plan_evaluator import evaluate_plan
        self.evaluate = evaluate_plan

    def _context(self, has_weather=True, has_occasion=True):
        return {
            "weather":   {"description": "Clear", "temp_c": 22, "advisory": "Good weather."} if has_weather else {},
            "occasion":  {"found": has_occasion, "name": "Earth Day"}                        if has_occasion else {"found": False},
            "advisories": ["Advisory 1"] if (has_weather or has_occasion) else [],
        }

    def test_exact_timing_scores_25(self):
        acts = _make_valid_activities(150)
        result = self.evaluate("Cubs", acts)
        self.assertEqual(result["scores"]["timing"], 25)

    def test_poor_timing_scores_low(self):
        acts = _make_valid_activities(150)
        # Inflate one activity by 40 min to create severe timing mismatch
        acts[0]["duration_minutes"] += 40
        result = self.evaluate("Cubs", acts)
        self.assertLess(result["scores"]["timing"], 15)

    def test_missing_bookends_penalized(self):
        acts = _make_valid_activities(150)
        # Replace high-energy first/last with low-energy activities
        acts[0]["energy_level"]  = "low"
        acts[0]["activity_type"] = "lecture"
        acts[-1]["energy_level"] = "low"
        acts[-1]["activity_type"] = "lecture"
        result = self.evaluate("Cubs", acts)
        self.assertLess(result["scores"]["structure"], 25)

    def test_good_structure_scores_25(self):
        acts = _make_valid_activities(150)
        result = self.evaluate("Cubs", acts)
        self.assertEqual(result["scores"]["structure"], 25)

    def test_high_variety_scores_well(self):
        # _make_valid_activities uses 7 distinct types
        acts = _make_valid_activities(150)
        result = self.evaluate("Cubs", acts)
        self.assertGreaterEqual(result["scores"]["variety"], 22)

    def test_low_variety_scores_low(self):
        acts = [
            {"slot": i, "activity_name": f"Game {i}", "activity_type": "game",
             "duration_minutes": 19, "energy_level": "high", "objective": "x",
             "instructions": ["s"], "materials": ["none"]}
            for i in range(1, 9)
        ]
        result = self.evaluate("Cubs", acts)
        self.assertLessEqual(result["scores"]["variety"], 8)

    def test_no_context_scores_zero(self):
        acts = _make_valid_activities(150)
        result = self.evaluate("Cubs", acts, context=None)
        self.assertEqual(result["scores"]["context_awareness"], 0)

    def test_full_context_scores_25(self):
        acts = _make_valid_activities(150)
        result = self.evaluate("Cubs", acts, context=self._context(True, True))
        self.assertEqual(result["scores"]["context_awareness"], 25)

    def test_total_is_sum_of_scores(self):
        acts = _make_valid_activities(150)
        result = self.evaluate("Cubs", acts, context=self._context())
        expected = sum(result["scores"].values())
        self.assertEqual(result["total"], expected)

    def test_grade_A(self):
        acts = _make_valid_activities(150)
        result = self.evaluate("Cubs", acts, context=self._context())
        if result["total"] >= 90:
            self.assertEqual(result["grade"], "A")

    def test_grade_F_for_terrible_plan(self):
        acts = [{"slot": 1, "activity_name": "One Lecture", "activity_type": "lecture",
                 "duration_minutes": 1, "energy_level": "low",
                 "objective": "x", "instructions": ["s"], "materials": ["none"]}]
        result = self.evaluate("Cubs", acts)
        self.assertLessEqual(result["total"], 50)
        self.assertIn(result["grade"], ("D", "F"))


# ══════════════════════════════════════════════════════════════════════════════
# 4. Validation Agent
# ══════════════════════════════════════════════════════════════════════════════

class TestValidationAgent(unittest.TestCase):

    def setUp(self):
        from agents.validation import run_validation_agent
        self.validate = run_validation_agent

    def test_valid_plan_passes(self):
        acts = _make_valid_activities(150)
        result = self.validate("Cubs", "Friendship", acts, 150)
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["issues"], [])

    def test_timing_mismatch_fails(self):
        acts = _make_valid_activities(150)
        acts[0]["duration_minutes"] = 99  # blows the total
        result = self.validate("Cubs", "Friendship", acts, 150)
        self.assertFalse(result["is_valid"])
        timing_issues = [i for i in result["issues"] if "time" in i.lower()]
        self.assertGreater(len(timing_issues), 0)

    def test_low_energy_first_activity_fails(self):
        acts = _make_valid_activities(150)
        acts[0]["energy_level"]  = "low"
        acts[0]["activity_type"] = "lecture"
        result = self.validate("Cubs", "Friendship", acts, 150)
        self.assertFalse(result["is_valid"])
        self.assertTrue(any("first" in i.lower() for i in result["issues"]))

    def test_low_energy_last_activity_fails(self):
        acts = _make_valid_activities(150)
        acts[-1]["energy_level"]  = "low"
        acts[-1]["activity_type"] = "lecture"
        result = self.validate("Cubs", "Friendship", acts, 150)
        self.assertFalse(result["is_valid"])
        self.assertTrue(any("last" in i.lower() for i in result["issues"]))

    def test_consecutive_cognitive_activities_warns(self):
        acts = _make_valid_activities(150)
        # Place two cognitive types back-to-back in middle slots
        acts[2]["activity_type"] = "lecture"
        acts[3]["activity_type"] = "skill"
        result = self.validate("Cubs", "Friendship", acts, 150)
        self.assertGreater(len(result["warnings"]), 0)

    def test_missing_objective_fails(self):
        acts = _make_valid_activities(150)
        del acts[3]["objective"]
        result = self.validate("Cubs", "Friendship", acts, 150)
        self.assertFalse(result["is_valid"])
        self.assertTrue(any("objective" in i for i in result["issues"]))

    def test_missing_materials_fails(self):
        acts = _make_valid_activities(150)
        del acts[2]["materials"]
        result = self.validate("Cubs", "Friendship", acts, 150)
        self.assertFalse(result["is_valid"])

    def test_custom_duration_changes_target(self):
        # 4-hour meeting → 210 content minutes
        acts = _make_valid_activities(210)
        result = self.validate("Girl Scouts", "Nature", acts, 210, custom_duration=240)
        self.assertEqual(result["expected_minutes"], 210)

    def test_beavers_long_activity_warns(self):
        acts = _make_valid_activities(150)
        acts[3]["duration_minutes"] = 25  # over the 20-min threshold for Beavers
        result = self.validate("Beavers", "Play", acts, 150)
        self.assertGreater(len(result["warnings"]), 0)

    def test_result_has_all_required_keys(self):
        acts = _make_valid_activities(150)
        result = self.validate("Cubs", "Friendship", acts, 150)
        for key in ("is_valid", "passed", "warnings", "issues", "summary", "activity_count"):
            self.assertIn(key, result)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Formatting Agent
# ══════════════════════════════════════════════════════════════════════════════

class TestFormattingAgent(unittest.TestCase):

    def setUp(self):
        from agents.formatting import run_formatting_agent, plan_to_text, plan_to_markdown
        self.format   = run_formatting_agent
        self.to_text  = plan_to_text
        self.to_md    = plan_to_markdown
        self.acts     = _make_formatting_activities()

    def _build_plan(self, **kwargs):
        defaults = dict(
            unit="Cubs", theme="Friendship", meeting_date="27/04/2026",
            activities=self.acts, master_materials=["Whiteboard", "Markers"],
        )
        defaults.update(kwargs)
        return self.format(**defaults)

    def test_plan_has_required_top_level_keys(self):
        plan = self._build_plan()
        for key in ("header", "schedule", "master_materials_list", "context_advisories"):
            self.assertIn(key, plan)

    def test_header_has_required_fields(self):
        plan = self._build_plan()
        h = plan["header"]
        for field in ("unit", "theme", "date", "total_duration", "age_range", "gender"):
            self.assertIn(field, h)
        self.assertEqual(h["unit"],  "Cubs")
        self.assertEqual(h["theme"], "Friendship")
        self.assertEqual(h["date"],  "27/04/2026")

    def test_schedule_includes_opening_and_closing(self):
        plan = self._build_plan()
        types = [s["segment_type"] for s in plan["schedule"]]
        # First and last segments are the fixed bookends
        self.assertEqual(types[0],  "fixed")
        self.assertEqual(types[-1], "fixed")

    def test_schedule_length_equals_activities_plus_two(self):
        plan = self._build_plan()
        self.assertEqual(len(plan["schedule"]), len(self.acts) + 2)

    def test_timestamps_are_monotonically_increasing(self):
        plan = self._build_plan()
        prev_end = -1
        for seg in plan["schedule"]:
            start_min = int(seg["time_start"].split(":")[0]) * 60 + int(seg["time_start"].split(":")[1])
            end_min   = int(seg["time_end"].split(":")[0])   * 60 + int(seg["time_end"].split(":")[1])
            self.assertGreaterEqual(start_min, prev_end)
            self.assertGreater(end_min, start_min)
            prev_end = end_min

    def test_materials_list_passed_through(self):
        plan = self._build_plan(master_materials=["Rope (x10)", "Cones (x6)"])
        self.assertIn("Rope (x10)", plan["master_materials_list"])

    def test_context_advisories_included(self):
        ctx  = {"advisories": ["Bring sunscreen — hot day."]}
        plan = self._build_plan(context=ctx)
        self.assertIn("Bring sunscreen — hot day.", plan["context_advisories"])

    def test_validation_notes_included(self):
        val  = {"is_valid": True, "warnings": ["Note A"], "activity_count": 2, "time_corrections": []}
        plan = self._build_plan(validation=val)
        self.assertIn("warnings", plan["validation"])

    def test_to_text_non_empty_and_has_header(self):
        plan = self._build_plan()
        text = self.to_text(plan)
        self.assertGreater(len(text), 200)
        self.assertIn("SCOUT MEETING PLAN", text)
        self.assertIn("Friendship",         text)

    def test_to_markdown_non_empty_and_has_header(self):
        plan = self._build_plan()
        md = self.to_md(plan)
        self.assertGreater(len(md), 200)
        self.assertIn("# Scout Meeting Plan", md)
        self.assertIn("Friendship",           md)

    def test_to_markdown_includes_all_activities(self):
        plan = self._build_plan()
        md   = self.to_md(plan)
        for act in self.acts:
            self.assertIn(act["activity_name"].upper(), md.upper())


# ══════════════════════════════════════════════════════════════════════════════
# 6. Conversation Agent JSON Parsing (mocked LLM)
# ══════════════════════════════════════════════════════════════════════════════

class TestConversationParsing(unittest.TestCase):
    """Tests the JSON parsing and fallback logic without hitting the real API."""

    def _run(self, raw_content: str) -> dict:
        mock_resp = MagicMock()
        mock_resp.content = raw_content
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_resp
        with patch("agents.orchestrator.get_llm", return_value=mock_llm):
            from agents.orchestrator import run_conversation_agent
            return run_conversation_agent("I want a Cubs meeting about friendship", [], "Cubs")

    def test_clean_json_parsed(self):
        result = self._run('{"ready_to_generate": false, "response": "Which date?"}')
        self.assertFalse(result["ready_to_generate"])
        self.assertEqual(result["response"], "Which date?")

    def test_generate_signal_parsed(self):
        payload = json.dumps({
            "ready_to_generate": True,
            "unit": "Cubs", "theme": "Friendship",
            "meeting_date": "27/04/2026", "custom_duration": None,
            "response": "Generating now.",
        })
        result = self._run(payload)
        self.assertTrue(result["ready_to_generate"])
        self.assertEqual(result["unit"],  "Cubs")
        self.assertEqual(result["theme"], "Friendship")

    def test_markdown_fenced_json_parsed(self):
        result = self._run('```json\n{"ready_to_generate": false, "response": "Hello"}\n```')
        self.assertFalse(result["ready_to_generate"])
        self.assertEqual(result["response"], "Hello")

    def test_json_embedded_in_prose_parsed(self):
        result = self._run('Sure! {"ready_to_generate": false, "response": "Tell me the unit."}')
        self.assertFalse(result["ready_to_generate"])
        self.assertEqual(result["response"], "Tell me the unit.")

    def test_broken_json_returns_non_empty_string(self):
        result = self._run('{"ready_to_generate": broken JSON !!!}')
        response = result.get("response", "")
        self.assertGreater(len(response), 0,   "Fallback must not be empty")
        self.assertFalse(response.strip().startswith("{"),
                         "Fallback must not return raw broken JSON to the user")

    def test_empty_response_returns_non_empty_string(self):
        result = self._run("")
        response = result.get("response", "")
        self.assertGreater(len(response), 0, "Fallback response must not be empty")

    def test_json_at_position_zero_with_missing_brace_returns_safe_default(self):
        # Starts with { but is broken — content[:0] == "" in the old code,
        # which caused `prose or content` to return the raw broken JSON.
        result = self._run('{"ready_to_generate": true, "unit": "Cubs"')  # missing closing }
        response = result.get("response", "")
        self.assertGreater(len(response), 0)
        self.assertFalse(response.strip().startswith("{"),
                         "Must not return truncated JSON as a user-visible response")

    def test_ready_to_generate_always_present(self):
        result = self._run("")
        self.assertIn("ready_to_generate", result)

    def test_response_always_present(self):
        for content in ["", "{}", '{"bad": json', "plain prose with no JSON"]:
            with self.subTest(content=content):
                result = self._run(content)
                self.assertIn("response", result)


# ══════════════════════════════════════════════════════════════════════════════
# 7. LLM-dependent integration tests (skipped if no API key)
# ══════════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(_HAS_API_KEY, "ANTHROPIC_API_KEY not set — skipping LLM tests")
class TestLLMAgents(unittest.TestCase):

    def test_educational_design_sequence_structure(self):
        from agents.educational_design import run_educational_design_agent
        result = run_educational_design_agent("Cubs", "Friendship", 150)
        seq = result.get("sequence", [])
        self.assertGreater(len(seq), 0)
        self.assertEqual(seq[0]["activity_type"],  "game",   "First slot must be a game")
        self.assertEqual(seq[-1]["activity_type"], "game",   "Last slot must be a game")
        total = sum(s["duration_minutes"] for s in seq)
        self.assertAlmostEqual(total, 150, delta=5)

    def test_educational_design_required_keys(self):
        from agents.educational_design import run_educational_design_agent
        result = run_educational_design_agent("Cubs", "Friendship", 150)
        for key in ("sequence", "educational_notes", "unit", "theme"):
            self.assertIn(key, result)
        for slot in result["sequence"]:
            for field in ("slot", "activity_type", "energy_level", "duration_minutes"):
                self.assertIn(field, slot)

    def test_scouting_context_returns_selections(self):
        from agents.scouting_context import run_scouting_context_agent
        seq = [
            {"slot": 1, "activity_type": "game",    "energy_level": "high", "duration_minutes": 15, "theme_focus": "energise"},
            {"slot": 2, "activity_type": "lecture",  "energy_level": "low",  "duration_minutes": 20, "theme_focus": "values"},
            {"slot": 3, "activity_type": "game",     "energy_level": "high", "duration_minutes": 10, "theme_focus": "close"},
        ]
        result = run_scouting_context_agent("Cubs", "Friendship", seq)
        selected = result.get("selected_activities", [])
        self.assertEqual(len(selected), len(seq))
        for act in selected:
            for field in ("slot", "activity_name", "activity_type", "duration_minutes"):
                self.assertIn(field, act)

    def test_activity_generator_produces_full_descriptions(self):
        from agents.activity_generator import run_activity_generator_agent
        selected = [
            {"slot": 1, "activity_id": "NEW", "activity_name": "Zip Zap Boing",
             "activity_type": "game", "duration_minutes": 10, "energy_level": "high", "source": "generated"},
        ]
        result = run_activity_generator_agent("Cubs", "Friendship", selected)
        acts = result.get("activities", [])
        self.assertEqual(len(acts), 1)
        act = acts[0]
        for field in ("activity_name", "objective", "instructions", "materials", "leader_tips"):
            self.assertIn(field, act)
        self.assertIsInstance(act["instructions"], list)
        self.assertGreater(len(act["instructions"]), 0)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
