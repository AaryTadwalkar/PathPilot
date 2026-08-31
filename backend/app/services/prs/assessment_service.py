"""
assessment_service.py — Assessment questions, validation, and scoring for Module 2 PRS.

Overall Design:
  Provides two question layers for the Placement Readiness System (PRS):

  Layer 1 — 5 Generic Questions (same for every role):
    These measure universal engineering maturity: deployment, project ownership,
    engineering workflow practices, practical experience duration, and problem-solving
    independence. These 5 questions contribute to the projects_experience_score pillar
    via the existing SCORE_MAPS and projects_engine.py scoring logic.

  Layer 2 — 5 Role-Specific Questions (unique per role, never repeated across roles):
    Loaded from datasets/role_specific_questions.json. These probe depth in the
    specific target role domain. Each role has 5 unique questions with graduated
    answer options scored from 0 (beginner) to 100 (expert).
    These 5 questions contribute to a composite `role_depth_score` that is blended
    into the projects_experience_score (10% weight) to reflect domain-specific depth.

  Total per evaluation: 5 generic + 5 role-specific = 10 questions.

Elements:
  ASSESSMENT_QUESTIONS          list  — 5 generic question definitions
  SCORE_MAPS                    dict  — Scoring map for all generic + role-specific questions
  ROLE_SPECIFIC_QUESTION_PATH   Path  — Path to role_specific_questions.json
  get_assessment_questions()          — Returns the 5 generic questions
  get_role_specific_questions(role)   — Returns 5 role-specific questions for a role
  get_combined_questions(role)        — Returns the full 10-question list
  validate_assessment_answers(answers)— Validates generic answers (role-specific are optional-validated)
  validate_combined_answers(answers, role) — Validates all 10 answers for a role
  score_assessment_for_prototype(answers) — Bridge scorer for projects_engine
  score_role_specific(answers, role)  — Scores role-specific answers → 0-100

Final Output:
  get_combined_questions(role) returns a list[dict] with 10 questions, generic first.
  validate_combined_answers() returns a normalized dict of all 10 validated answers.
  score_role_specific() returns a float 0-100 representing role domain depth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# LAYER 1: Generic Questions (5) — same for all roles
# ---------------------------------------------------------------------------

ASSESSMENT_QUESTIONS = [
    {
        "id": "deployment_exposure",
        "question": "Have you deployed any of your projects so that other users can access them?",
        "type": "single_select",
        "options": [
            {"code": "no", "label": "No"},
            {"code": "local_only", "label": "Only locally"},
            {"code": "public_hosting", "label": "Yes, using public hosting"},
            {"code": "cloud_production", "label": "Yes, using a cloud/production platform"},
        ],
    },
    {
        "id": "project_ownership",
        "question": "What best describes your involvement in your strongest project?",
        "type": "single_select",
        "options": [
            {"code": "tutorial_minor_changes", "label": "Followed a tutorial or made minor changes"},
            {"code": "small_independent", "label": "Built a small project independently"},
            {"code": "multiple_components", "label": "Designed and implemented multiple major components"},
            {"code": "architecture_integrated_systems", "label": "Designed the architecture and integrated multiple systems/services"},
        ],
    },
    {
        "id": "engineering_practices",
        "question": "Which engineering practices have you used in projects, internships or work?",
        "type": "multi_select",
        "options": [
            {"code": "git", "label": "Git/version control"},
            {"code": "code_reviews", "label": "Code reviews or team collaboration"},
            {"code": "testing", "label": "Testing"},
            {"code": "ci_cd", "label": "CI/CD"},
            {"code": "cloud_deployment", "label": "Cloud deployment"},
            {"code": "issue_tracking", "label": "Issue/task tracking"},
            {"code": "agile", "label": "Agile/Scrum workflow"},
            {"code": "none", "label": "None"},
        ],
    },
    {
        "id": "relevant_experience_duration",
        "question": "How much practical experience do you have through projects, internships, freelance or professional work related to the selected role?",
        "type": "single_select",
        "options": [
            {"code": "none", "label": "No relevant experience"},
            {"code": "less_6_months", "label": "Less than 6 months"},
            {"code": "6_12_months", "label": "6-12 months"},
            {"code": "1_2_years", "label": "1-2 years"},
            {"code": "2_plus_years", "label": "2+ years"},
        ],
    },
    {
        "id": "problem_solving_independence",
        "question": "When you face a technical problem in a project, what usually describes your approach?",
        "type": "single_select",
        "options": [
            {"code": "tutorial_dependent", "label": "Mainly depend on step-by-step tutorials"},
            {"code": "adapt_existing_code", "label": "Search for solutions and adapt existing code"},
            {"code": "debug_and_implement", "label": "Debug, compare approaches and implement my own solution"},
            {"code": "root_cause_tradeoffs", "label": "Investigate root causes, design solutions and evaluate trade-offs independently"},
        ],
    },
]


# ---------------------------------------------------------------------------
# Score maps for all 5 generic questions
# ---------------------------------------------------------------------------

SCORE_MAPS: dict[str, dict[str, float]] = {
    "deployment_exposure": {
        "no": 0,
        "local_only": 40,
        "public_hosting": 85,
        "cloud_production": 100,
    },
    "project_ownership": {
        "tutorial_minor_changes": 20,
        "small_independent": 50,
        "multiple_components": 80,
        "architecture_integrated_systems": 100,
    },
    "engineering_practices": {
        "none": 0,
        "git": 20,
        "code_reviews": 15,
        "testing": 20,
        "ci_cd": 20,
        "cloud_deployment": 15,
        "issue_tracking": 5,
        "agile": 5,
    },
    "relevant_experience_duration": {
        "none": 0,
        "less_6_months": 35,
        "6_12_months": 65,
        "1_2_years": 85,
        "2_plus_years": 100,
    },
    "problem_solving_independence": {
        "tutorial_dependent": 20,
        "adapt_existing_code": 50,
        "debug_and_implement": 80,
        "root_cause_tradeoffs": 100,
    },
}

# Role-specific question options are scored linearly: option index × 33 (0/33/66/100)
_ROLE_SPECIFIC_OPTION_SCORES = [0.0, 33.0, 66.0, 100.0]


# ---------------------------------------------------------------------------
# Role-specific question loader
# ---------------------------------------------------------------------------

# Resolve path: this file lives in backend/app/services/prs/, dataset is at project_root/datasets/
ROLE_SPECIFIC_QUESTION_PATH: Path = (
    Path(__file__).resolve().parents[4] / "datasets" / "role_specific_questions.json"
)


def _load_role_specific_raw() -> dict[str, list[dict[str, Any]]]:
    """
    Load role_specific_questions.json from disk.

    How it works:
      Opens and parses the JSON file at ROLE_SPECIFIC_QUESTION_PATH.
      Returns a dict keyed by role name, value is list of question dicts.
      Returns empty dict on any IO or parse error — callers degrade gracefully
      to 5-question (generic-only) mode.

    Used by:
      get_role_specific_questions() — called per API request.

    Returns:
      dict[role_name, list[question_dict]]
    """
    try:
        return json.loads(ROLE_SPECIFIC_QUESTION_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[assessment_service] Could not load role_specific_questions.json: {exc}")
        return {}


def get_assessment_questions() -> list[dict[str, Any]]:
    """
    Return the 5 generic assessment questions (same for all roles).

    Used by:
      GET /prs/assessment endpoint in main.py (legacy compatibility — returns all 10 when role= is absent).
      get_combined_questions() as the first 5 items.

    Returns:
      list of 5 question dicts with id, question, type, options.
    """
    return ASSESSMENT_QUESTIONS


def get_role_specific_questions(role: str) -> list[dict[str, Any]]:
    """
    Return 5 role-specific questions for the given target role.

    How it works:
      Loads role_specific_questions.json, looks up the role name.
      Strips the options dict (which has code → score mapping in raw JSON)
      to the list[{code, label}] format expected by the API schema.
      If the role is not found or the file is missing, returns an empty list
      so the caller can degrade gracefully to 5-question mode.

    Concepts:
      The JSON stores options as a list of {code, label} dicts — no conversion needed.
      The score for role-specific questions is derived from option index order
      (0→0%, 1→33%, 2→66%, 3→100%) in score_role_specific().

    Used by:
      get_combined_questions() to get the last 5 questions.
      validate_combined_answers() to know which role-specific question IDs are valid.

    Returns:
      list of up to 5 question dicts, or empty list if role not in dataset.
    """
    raw = _load_role_specific_raw()
    questions = raw.get(role, [])
    return questions[:5]  # Enforce max 5


def get_combined_questions(role: str) -> list[dict[str, Any]]:
    """
    Return the full 10-question list: 5 generic + 5 role-specific.

    How it works:
      Concatenates get_assessment_questions() (5) with get_role_specific_questions(role) (5).
      If role is empty or not found in the dataset, only the 5 generic questions are returned.
      This ensures backward compatibility with any existing code that calls without a role.

    Used by:
      GET /prs/assessment?role=... endpoint in main.py.

    Returns:
      list of 10 question dicts (or 5 if role-specific questions not found).
    """
    generic = get_assessment_questions()
    role_specific = get_role_specific_questions(role) if role else []
    return generic + role_specific


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_assessment_answers(answers: dict[str, Any]) -> dict[str, Any]:
    """
    Validate and normalize answers for the 5 generic questions only.

    How it works:
      Iterates over ASSESSMENT_QUESTIONS and validates each answer:
        - single_select: must be a str matching one of the valid option codes.
        - multi_select: must be a list of valid codes; "none" cannot be combined.
      Returns a normalized dict of validated answers.
      Raises ValueError with a semicolon-joined list of all validation errors.

    Concepts:
      Fail-fast accumulation: collect all errors before raising so the caller
      sees all problems at once rather than fixing one at a time.

    Used by:
      POST /prs/evaluate endpoint (main.py) for backward compatibility.
      validate_combined_answers() delegates generic validation to this function.

    Returns:
      dict[question_id, validated_answer]
    Raises:
      ValueError if any generic answer is invalid or missing.
    """
    normalized: dict[str, Any] = {}
    errors: list[str] = []

    for question in ASSESSMENT_QUESTIONS:
        question_id = question["id"]
        question_type = question["type"]
        valid_codes = {option["code"] for option in question["options"]}
        value = answers.get(question_id)

        if value is None:
            errors.append(f"Missing assessment answer: {question_id}")
            continue

        if question_type == "single_select":
            if not isinstance(value, str) or value not in valid_codes:
                errors.append(f"Invalid assessment answer for {question_id}: {value}")
                continue
            normalized[question_id] = value
            continue

        if question_type == "multi_select":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"Invalid assessment answer list for {question_id}")
                continue
            deduped = list(dict.fromkeys(value))
            invalid = [item for item in deduped if item not in valid_codes]
            if invalid:
                errors.append(f"Invalid assessment options for {question_id}: {', '.join(invalid)}")
                continue
            if "none" in deduped and len(deduped) > 1:
                errors.append(f"Assessment option 'none' cannot be combined for {question_id}")
                continue
            normalized[question_id] = deduped

    if errors:
        raise ValueError("; ".join(errors))

    return normalized


def validate_combined_answers(answers: dict[str, Any], role: str) -> dict[str, Any]:
    """
    Validate and normalize all 10 answers (5 generic + 5 role-specific).

    How it works:
      Step 1: Delegates generic validation to validate_assessment_answers().
      Step 2: Loads role-specific questions for the role, validates each:
        - All role-specific questions are single_select.
        - If a role-specific answer is missing, it is silently skipped (optional).
        - If a role-specific answer is present but has an invalid code, an error is raised.
      Step 3: Returns the combined normalized dict.

    Concepts:
      Role-specific answers are optional — missing ones degrade to score 0 for that question.
      This prevents validation from blocking users if they somehow have only generic answers
      (e.g., legacy evaluations created before this feature was added).

    Used by:
      POST /prs/evaluate endpoint in main.py when role_specific mode is active.

    Returns:
      dict containing all validated generic answers + any valid role-specific answers.
    Raises:
      ValueError if any generic answer is invalid, or if an explicitly submitted
      role-specific answer is invalid.
    """
    # Step 1: Validate generic answers (raises on error)
    normalized = validate_assessment_answers(answers)

    # Step 2: Validate role-specific answers (optional, soft validation)
    role_questions = get_role_specific_questions(role)
    errors: list[str] = []
    for question in role_questions:
        question_id = question["id"]
        valid_codes = {opt["code"] for opt in question["options"]}
        value = answers.get(question_id)

        if value is None:
            continue  # Role-specific answers are optional — skip missing ones

        if not isinstance(value, str) or value not in valid_codes:
            errors.append(f"Invalid role-specific answer for {question_id}: {value}")
            continue

        normalized[question_id] = value

    if errors:
        raise ValueError("; ".join(errors))

    return normalized


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_assessment_for_prototype(answers: dict[str, Any]) -> dict[str, float]:
    """
    Bridge scorer for the projects_engine — scores the 5 generic questions only.

    How it works:
      Calls validate_assessment_answers() on the provided answers dict.
      Computes per-pillar scores using the existing SCORE_MAPS:
        - deployment: deployment_exposure answer
        - ownership: project_ownership answer
        - usage: real_world_usage answer (note: this question was removed in v2)
        - problem_solving: problem_solving_independence answer
        - workflow: sum of multi-select engineering_practices scores (capped at 100)
        - duration: relevant_experience_duration answer
      Aggregates into project_score, experience_score, and a combined score.

    Note:
      The real_world_usage question was in the old 6-question set but was removed
      to get to 5 generic questions. projects_engine.py uses _get_answer() with
      a default fallback of "no" for missing keys, so removal is backward-safe.

    Used by:
      projects_engine.py — calculate_projects_experience() passes answers to this
      indirectly via SCORE_MAPS lookups.

    Returns:
      dict with project_score, experience_score, projects_experience_score (all 0-100).
    """
    normalized = validate_assessment_answers(answers)

    deployment = _single_score("deployment_exposure", normalized)
    ownership = _single_score("project_ownership", normalized)
    problem_solving = _single_score("problem_solving_independence", normalized)
    workflow = _workflow_score(normalized)
    duration = _single_score("relevant_experience_duration", normalized)

    project_score = (
        deployment * 0.40
        + ownership * 0.35
        + problem_solving * 0.25
    )
    experience_score = duration * 0.55 + workflow * 0.45

    return {
        "project_score": round(project_score, 1),
        "experience_score": round(experience_score, 1),
        "projects_experience_score": round(project_score * 0.80 + experience_score * 0.20, 1),
    }


def score_role_specific(answers: dict[str, Any], role: str) -> float:
    """
    Score the 5 role-specific answers and return a composite 0-100 score.

    How it works:
      Loads role-specific questions for the given role.
      For each question, looks up the answer code in the question's options list
      to get its index (0–3). Maps index to score: [0, 33, 66, 100].
      Averages scores across all answered questions.
      If no role-specific answers are present (degraded mode), returns 0.0.

    Concepts:
      Linear 4-option scoring: each option represents a level of proficiency.
      Index 0 = no experience (0%), index 3 = expert (100%).
      Missing answers contribute 0 to the average without causing errors.

    Used by:
      projects_engine.py — calculate_projects_experience() blends this into the
      final score as a 10% weight (`role_depth_bonus`).

    Returns:
      float 0.0–100.0 representing average role-specific domain depth.
    """
    role_questions = get_role_specific_questions(role)
    if not role_questions:
        return 0.0

    total = 0.0
    answered = 0
    for question in role_questions:
        question_id = question["id"]
        option_codes = [opt["code"] for opt in question["options"]]
        answer = answers.get(question_id)
        if answer and answer in option_codes:
            idx = option_codes.index(answer)
            total += _ROLE_SPECIFIC_OPTION_SCORES[idx] if idx < len(_ROLE_SPECIFIC_OPTION_SCORES) else 100.0
            answered += 1

    return round(total / max(answered, 1), 2)


def _single_score(question_id: str, answers: dict[str, Any]) -> float:
    """
    Look up a single-select answer score from SCORE_MAPS.

    Used by: score_assessment_for_prototype().
    Returns: float score 0.0-100.0.
    """
    code = answers[question_id]
    return float(SCORE_MAPS[question_id][code])


def _workflow_score(answers: dict[str, Any]) -> float:
    """
    Compute multi-select engineering_practices score (additive, capped at 100).

    Used by: score_assessment_for_prototype().
    Returns: float 0.0-100.0.
    """
    values = answers["engineering_practices"]
    if "none" in values:
        return 0.0
    return float(min(100, sum(SCORE_MAPS["engineering_practices"][v] for v in values)))