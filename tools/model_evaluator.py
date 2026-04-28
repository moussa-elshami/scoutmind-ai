"""
Model Evaluation Script - ScoutMind
=====================================
Part 1: Full Pipeline Evaluation
  - Runs the 6-agent pipeline on 10 varied unit/theme inputs
  - Measures: quality score, timing accuracy, validation pass rate, grade distribution

Part 2: Conversation Extraction Accuracy
  - Tests the conversation agent on 15 varied natural-language inputs
  - Measures: ready-to-generate rate, unit extraction accuracy, theme detection accuracy

Usage:
    python tools/model_evaluator.py           # run both
    python tools/model_evaluator.py --pipe    # pipeline only (expensive - uses API credits)
    python tools/model_evaluator.py --conv    # conversation only (cheap)
"""

import os
import sys
import json
import time
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv()

from agents.orchestrator import run_pipeline, run_conversation_agent


# ── Pipeline test cases (10 varied unit/theme combinations) ──────────────────

PIPELINE_TESTS = [
    {"id": "P01", "unit": "Cubs",        "theme": "Nature and Wildlife",     "date": "28/04/2026"},
    {"id": "P02", "unit": "Boy Scouts",  "theme": "Leadership",              "date": "28/04/2026"},
    {"id": "P03", "unit": "Girl Scouts", "theme": "Friendship",              "date": "28/04/2026"},
    {"id": "P04", "unit": "Rovers",      "theme": "Community Service",       "date": "28/04/2026"},
    {"id": "P05", "unit": "Beavers",     "theme": "Animals",                 "date": "28/04/2026"},
    {"id": "P06", "unit": "Pioneers",    "theme": "Environmental Awareness", "date": "28/04/2026"},
    {"id": "P07", "unit": "Cubs",        "theme": "Sports and Fitness",      "date": "28/04/2026"},
    {"id": "P08", "unit": "Boy Scouts",  "theme": "First Aid and Safety",    "date": "28/04/2026"},
    {"id": "P09", "unit": "Girl Scouts", "theme": "Creativity and Arts",     "date": "28/04/2026"},
    {"id": "P10", "unit": "Rovers",      "theme": "Adventure and Survival",  "date": "28/04/2026"},
]


# ── Conversation test cases (15 varied phrasings) ────────────────────────────

CONV_TESTS = [
    {
        "id": "C01",
        "message": "I need a Cubs meeting about nature, no specific date needed",
        "expected_unit": "Cubs",
        "expected_theme_kw": "nature",
        "description": "Direct: Cubs + nature + no date",
    },
    {
        "id": "C02",
        "message": "Can you plan a Boy Scouts meeting on leadership for 05/05/2026?",
        "expected_unit": "Boy Scouts",
        "expected_theme_kw": "leadership",
        "description": "Direct: Boy Scouts + leadership + date",
    },
    {
        "id": "C03",
        "message": "I lead Girl Scouts and want a friendship-themed meeting today",
        "expected_unit": "Girl Scouts",
        "expected_theme_kw": "friendship",
        "description": "Natural: Girl Scouts + friendship + today",
    },
    {
        "id": "C04",
        "message": "Make a Rovers meeting plan about community service, use today's date",
        "expected_unit": "Rovers",
        "expected_theme_kw": "community",
        "description": "Natural: Rovers + community service + today",
    },
    {
        "id": "C05",
        "message": "My beavers group needs a fun meeting about animals, any date is fine",
        "expected_unit": "Beavers",
        "expected_theme_kw": "animals",
        "description": "Lowercase unit: Beavers + animals + any date",
    },
    {
        "id": "C06",
        "message": "Generate a Pioneers meeting focused on the environment for 10/05/2026",
        "expected_unit": "Pioneers",
        "expected_theme_kw": "environment",
        "description": "Direct: Pioneers + environment + date",
    },
    {
        "id": "C07",
        "message": "I want to plan a cubs meeting about sports and fitness, no date necessary",
        "expected_unit": "Cubs",
        "expected_theme_kw": "sports",
        "description": "Lowercase unit: Cubs + sports + no date",
    },
    {
        "id": "C08",
        "message": "Create a first aid meeting plan for my boy scout troop, date doesn't matter",
        "expected_unit": "Boy Scouts",
        "expected_theme_kw": "first aid",
        "description": "Alias 'boy scout': Boy Scouts + first aid",
    },
    {
        "id": "C09",
        "message": "I'm a Girl Scouts leader, please generate a creativity and arts meeting for 15/05/2026",
        "expected_unit": "Girl Scouts",
        "expected_theme_kw": "creativity",
        "description": "Full sentence: Girl Scouts + creativity + date",
    },
    {
        "id": "C10",
        "message": "Plan an adventure and survival themed meeting for Rovers, no specific date",
        "expected_unit": "Rovers",
        "expected_theme_kw": "adventure",
        "description": "Direct: Rovers + adventure + no date",
    },
    {
        "id": "C11",
        "message": "Our pioneers unit wants a meeting on personal development and leadership, no date",
        "expected_unit": "Pioneers",
        "expected_theme_kw": "leadership",
        "description": "Natural: Pioneers + leadership + no date",
    },
    {
        "id": "C12",
        "message": "Please make a scouting meeting for my rover scouts about citizenship for 20/05/2026",
        "expected_unit": "Rovers",
        "expected_theme_kw": "citizenship",
        "description": "Alias 'rover scouts': Rovers + citizenship + date",
    },
    {
        "id": "C13",
        "message": "Can you help me plan a meeting for my girl scouts on cooking and life skills for 25/05/2026?",
        "expected_unit": "Girl Scouts",
        "expected_theme_kw": "life",
        "description": "Natural: Girl Scouts + life skills + date",
    },
    {
        "id": "C14",
        "message": "I need a meeting for my boy scouts on knots and camping skills, any date works",
        "expected_unit": "Boy Scouts",
        "expected_theme_kw": "knot",
        "description": "Natural: Boy Scouts + knots + any date",
    },
    {
        "id": "C15",
        "message": "My cubs want a meeting about the environment and recycling, no date needed",
        "expected_unit": "Cubs",
        "expected_theme_kw": "environment",
        "description": "Natural: Cubs + environment + no date",
    },
]


# ── Pipeline evaluation ───────────────────────────────────────────────────────

def run_pipeline_evaluation() -> list:
    results = []
    n = len(PIPELINE_TESTS)

    print(f"\n  Running {n} pipeline tests (each takes ~30-60s)...")
    print(f"  {'ID':<5}  {'Unit':<14}  {'Theme':<28}  {'Score':>6}  {'Grade':>5}  {'Timing':>7}  {'Valid':>6}  {'Fixes':>5}")
    print(f"  {'-' * 82}")

    for i, test in enumerate(PIPELINE_TESTS):
        print(f"  {test['id']}  Running {test['unit']} / {test['theme'][:20]}... ({i+1}/{n})", end="\r", flush=True)
        t0 = time.time()

        try:
            state   = run_pipeline(unit=test["unit"], theme=test["theme"], meeting_date=test["date"])
            elapsed = round(time.time() - t0, 1)

            if state.get("error"):
                row = {
                    "id": test["id"], "unit": test["unit"], "theme": test["theme"],
                    "status": "error", "error": state["error"],
                    "score": None, "grade": None, "timing_ok": False,
                    "validation_passed": False, "n_corrections": 0,
                    "n_warnings": 0, "n_activities": 0, "elapsed": elapsed,
                }
            else:
                quality     = state["plan"]["quality_score"]
                validation  = state.get("validation", {})
                corrections = validation.get("time_corrections", [])
                timing_ok   = quality.get("scores", {}).get("timing", 0) >= 20  # >=20/25 = within 5 min

                row = {
                    "id":                test["id"],
                    "unit":              test["unit"],
                    "theme":             test["theme"],
                    "status":            "ok",
                    "score":             quality["total"],
                    "grade":             quality["grade"],
                    "timing_ok":         timing_ok,
                    "validation_passed": validation.get("is_valid", False),
                    "n_corrections":     len(corrections),
                    "n_warnings":        len(validation.get("warnings", [])),
                    "n_activities":      len(state.get("generated", {}).get("activities", [])),
                    "elapsed":           elapsed,
                }

            results.append(row)

            if row["status"] == "error":
                print(f"  {row['id']:<5}  {row['unit']:<14}  {row['theme'][:26]:<28}  ERROR")
            else:
                t_mark = "OK  " if row["timing_ok"] else "FAIL"
                v_mark = "OK  " if row["validation_passed"] else "FAIL"
                print(f"  {row['id']:<5}  {row['unit']:<14}  {row['theme'][:26]:<28}  "
                      f"{row['score']:>6}  {row['grade']:>5}  {t_mark:>7}  {v_mark:>6}  "
                      f"{row['n_corrections']:>5}")

        except Exception as e:
            elapsed = round(time.time() - t0, 1)
            row = {
                "id": test["id"], "unit": test["unit"], "theme": test["theme"],
                "status": "exception", "error": str(e),
                "score": None, "grade": None, "timing_ok": False,
                "validation_passed": False, "n_corrections": 0,
                "n_warnings": 0, "n_activities": 0, "elapsed": elapsed,
            }
            results.append(row)
            print(f"  {test['id']:<5}  {test['unit']:<14}  {test['theme'][:26]:<28}  "
                  f"EXCEPTION: {str(e)[:35]}")

    return results


def summarize_pipeline(results: list) -> dict:
    ok = [r for r in results if r["status"] == "ok"]
    n  = len(results)
    if not ok:
        return {"n_total": n, "n_ok": 0}

    scores     = [r["score"] for r in ok]
    timing_ok  = [r for r in ok if r["timing_ok"]]
    valid      = [r for r in ok if r["validation_passed"]]
    corrected  = [r for r in ok if r["n_corrections"] > 0]
    grade_dist: dict = {}
    for r in ok:
        grade_dist[r["grade"]] = grade_dist.get(r["grade"], 0) + 1

    return {
        "n_total":          n,
        "n_ok":             len(ok),
        "mean_score":       round(sum(scores) / len(scores), 1),
        "min_score":        min(scores),
        "max_score":        max(scores),
        "timing_accuracy":  round(len(timing_ok) / len(ok) * 100, 1),
        "validation_rate":  round(len(valid)     / len(ok) * 100, 1),
        "correction_rate":  round(len(corrected) / len(ok) * 100, 1),
        "grade_dist":       grade_dist,
    }


def print_pipeline_summary(summary: dict):
    print(f"\n  Pipeline Summary")
    print(f"  {'-' * 52}")
    print(f"  Runs completed       : {summary['n_ok']}/{summary['n_total']}")
    if summary["n_ok"] == 0:
        return
    print(f"  Mean quality score   : {summary['mean_score']}/100")
    print(f"  Score range          : {summary['min_score']} - {summary['max_score']}")
    print(f"  Timing accuracy      : {summary['timing_accuracy']}%")
    print(f"  Validation pass rate : {summary['validation_rate']}%")
    print(f"  Plans needing fixes  : {summary['correction_rate']}%")
    dist   = summary["grade_dist"]
    grades = "  ".join(f"{g}={dist[g]}" for g in sorted(dist))
    print(f"  Grade distribution   : {grades}")


# ── Conversation evaluation ───────────────────────────────────────────────────

def run_conv_evaluation() -> list:
    results = []
    n = len(CONV_TESTS)

    print(f"\n  Running {n} conversation extraction tests...")
    print(f"  {'ID':<5}  {'Description':<45}  {'Ready':>6}  {'Unit':>6}  {'Theme':>6}")
    print(f"  {'-' * 73}")

    for test in CONV_TESTS:
        try:
            result = run_conversation_agent(
                user_message=test["message"],
                conversation_history=[],
            )

            ready           = bool(result.get("ready_to_generate", False))
            extracted_unit  = result.get("unit",  "") or ""
            extracted_theme = result.get("theme", "") or ""
            response_text   = result.get("response", "") or ""

            # Unit correct: explicit field (when ready=True) OR keyword in response
            unit_in_field    = extracted_unit.lower() == test["expected_unit"].lower()
            unit_in_response = test["expected_unit"].lower() in response_text.lower()
            unit_ok          = unit_in_field or unit_in_response

            # Theme correct: explicit field (when ready=True) OR keyword in response
            theme_kw          = test["expected_theme_kw"].lower()
            theme_in_field    = theme_kw in extracted_theme.lower()
            theme_in_response = theme_kw in response_text.lower()
            theme_ok          = theme_in_field or theme_in_response

            row = {
                "id":             test["id"],
                "description":    test["description"],
                "expected_unit":  test["expected_unit"],
                "expected_theme": test["expected_theme_kw"],
                "ready":          ready,
                "unit_ok":        unit_ok,
                "theme_ok":       theme_ok,
                "extracted_unit": extracted_unit,
                "extracted_theme": extracted_theme[:80],
                "response":       response_text[:120],
            }
            results.append(row)

            r_mark = "YES" if ready    else "NO "
            u_mark = "OK " if unit_ok  else "FAIL"
            t_mark = "OK " if theme_ok else "FAIL"
            print(f"  {row['id']:<5}  {test['description'][:43]:<45}  "
                  f"{r_mark:>6}  {u_mark:>6}  {t_mark:>6}")

        except Exception as e:
            row = {
                "id": test["id"], "description": test["description"],
                "ready": False, "unit_ok": False, "theme_ok": False,
                "error": str(e),
            }
            results.append(row)
            print(f"  {test['id']:<5}  {test['description'][:43]:<45}  "
                  f"EXCEPTION: {str(e)[:30]}")

    return results


def summarize_conv(results: list) -> dict:
    n         = len(results)
    ready     = [r for r in results if r.get("ready")]
    unit_ok   = [r for r in results if r.get("unit_ok")]
    theme_ok  = [r for r in results if r.get("theme_ok")]
    both_ok   = [r for r in results if r.get("unit_ok") and r.get("theme_ok")]

    return {
        "n_total":          n,
        "ready_rate":       round(len(ready)    / n * 100, 1),
        "unit_accuracy":    round(len(unit_ok)  / n * 100, 1),
        "theme_accuracy":   round(len(theme_ok) / n * 100, 1),
        "overall_accuracy": round(len(both_ok)  / n * 100, 1),
    }


def print_conv_summary(summary: dict):
    print(f"\n  Conversation Extraction Summary")
    print(f"  {'-' * 52}")
    print(f"  Tests run            : {summary['n_total']}")
    print(f"  Ready-to-generate    : {summary['ready_rate']}%")
    print(f"  Unit accuracy        : {summary['unit_accuracy']}%")
    print(f"  Theme accuracy       : {summary['theme_accuracy']}%")
    print(f"  Overall accuracy     : {summary['overall_accuracy']}%")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ScoutMind model evaluation")
    parser.add_argument("--pipe", action="store_true", help="Pipeline evaluation only")
    parser.add_argument("--conv", action="store_true", help="Conversation evaluation only")
    args = parser.parse_args()
    run_both = not args.pipe and not args.conv

    SEP = "=" * 65
    print(SEP)
    print("  ScoutMind - Full Model Evaluation")
    print(SEP)

    all_results: dict = {}

    if args.pipe or run_both:
        print(f"\n{SEP}")
        print("  PART 1: Full Pipeline Evaluation")
        print(SEP)
        pipe_results     = run_pipeline_evaluation()
        pipeline_summary = summarize_pipeline(pipe_results)
        print_pipeline_summary(pipeline_summary)
        all_results["pipeline"] = {"results": pipe_results, "summary": pipeline_summary}

    if args.conv or run_both:
        print(f"\n{SEP}")
        print("  PART 2: Conversation Extraction Accuracy")
        print(SEP)
        conv_results = run_conv_evaluation()
        conv_summary = summarize_conv(conv_results)
        print_conv_summary(conv_summary)
        all_results["conversation"] = {"results": conv_results, "summary": conv_summary}

    out_path = os.path.join(ROOT, "tools", "model_eval_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Results saved to: tools/model_eval_results.json")

    print(f"\n{SEP}")
    print("  Evaluation complete.")
    print(SEP)


if __name__ == "__main__":
    main()
