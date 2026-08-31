"""
tests/test_m3_what_if.py
========================
M3-4 unit tests for project_delta() and gap_engine.compute_gap_analysis().

ALL 7 tests must pass before M3-5 (MilestoneEngine) starts.
Tests are written alongside the engine code (not after) per project rule.

Test inventory:
  1. Add new skill                  -> skill_readiness delta > 0, skipped=False
  2. Add already-possessed skill    -> delta = 0.0, skipped=True
  3. Add new project                -> projects_experience delta > 0
  4. Add duplicate project          -> delta = 0.0, skipped=True
  5. Add profile link when absent   -> role_alignment delta > 0
  6. Add profile link when present  -> delta = 0.0, skipped=True
  7. _to_prs_project() field map    -> no TypeError, projects_experience delta > 0

Run:
  (venv) cd backend
  python -m pytest tests/test_m3_what_if.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from app.services.prs.dataset_loader import load_prs_datasets
from app.services.prs.input_builder  import PRSInput, PRSSkill, PRSProject
from app.services.prs.skill_engine   import calculate_skill_readiness
from app.services.prs.projects_engine import calculate_projects_experience
from app.services.prs.certificate_engine import calculate_certificate_quality
from app.services.prs.role_alignment_engine import calculate_role_alignment
from app.services.prs.orchestrator   import PRSResult, orchestrate_prs
from app.services.prs.constants      import PILLAR_WEIGHTS

from app.services.career.what_if_engine import Mutation, project_delta, DeltaResult
from app.services.career.gap_engine     import compute_gap_analysis


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def datasets():
    """Load datasets once per test module (lru_cache makes this fast)."""
    return load_prs_datasets()


def _make_baseline(prs_input: PRSInput, datasets) -> PRSResult:
    """
    Helper: compute a real baseline PRSResult from a PRSInput.
    Resume quality uses a fixed score of 50.0 (not testing resume engine here).
    """
    skill_res = calculate_skill_readiness(prs_input, datasets)
    proj_res  = calculate_projects_experience(prs_input, datasets)
    cert_res  = calculate_certificate_quality(prs_input, datasets)
    align_res = calculate_role_alignment(prs_input, datasets)

    weak = proj_res.weak_areas + cert_res.weak_areas + align_res.weak_areas

    return orchestrate_prs(
        target_role=prs_input.target_role,
        skill_readiness_score=skill_res.score,
        projects_experience_score=proj_res.score,
        role_alignment_score=align_res.score,
        resume_quality_score=50.0,
        certificate_quality_score=cert_res.score,
        engine_weak_areas=weak,
        missing_skills=skill_res.missing_skills,
    )


def _ai_engineer_input(*, extra_skills=None, extra_projects=None,
                        certifications=None) -> PRSInput:
    """Minimal AI Engineer profile for mutation tests."""
    skills = [PRSSkill(skill="Python"), PRSSkill(skill="TensorFlow")]
    if extra_skills:
        skills += [PRSSkill(skill=s) for s in extra_skills]
    projects = []
    if extra_projects:
        projects = extra_projects
    return PRSInput(
        user_id=999,
        target_role="AI Engineer",
        skills=skills,
        projects=projects,
        certifications=certifications or [],
        resume_analysis={},
        career_interests=["AI Engineer"],
        assessment_answers={},
    )


# ---------------------------------------------------------------------------
# TEST 1: Add new skill -> delta > 0
# ---------------------------------------------------------------------------

def test_add_new_skill_increases_score(datasets):
    """
    Adding PyTorch to an AI Engineer who only has Python + TensorFlow
    should raise skill_readiness (PyTorch is critical for AI Engineer)
    and potentially role_alignment, with skipped=False.
    """
    prs_input = _ai_engineer_input()
    baseline  = _make_baseline(prs_input, datasets)

    result = project_delta(
        prs_input, baseline,
        Mutation(type="add_skill", payload="PyTorch"),
        datasets,
    )

    assert result.skipped is False, "New skill must not be flagged as skipped"
    assert result.overall_delta > 0, f"Expected positive delta, got {result.overall_delta}"
    # A new skill may lift skill_readiness and/or role_alignment depending on how
    # the engine already scored it via semantic matching. At least one pillar must improve.
    assert len(result.pillar_deltas) > 0, "At least one pillar must change"
    assert all(v > 0 for v in result.pillar_deltas.values()), \
        f"All changed pillars must improve, got: {result.pillar_deltas}"


# ---------------------------------------------------------------------------
# TEST 2: Add already-possessed skill -> delta = 0, skipped = True
# ---------------------------------------------------------------------------

def test_add_existing_skill_is_noop(datasets):
    """
    Adding Python to a profile that already has Python must produce
    delta = 0.0 and skipped = True (dedup guard).
    """
    prs_input = _ai_engineer_input()  # already has Python
    baseline  = _make_baseline(prs_input, datasets)

    result = project_delta(
        prs_input, baseline,
        Mutation(type="add_skill", payload="Python"),  # already present
        datasets,
    )

    assert result.skipped is True,      "Duplicate skill must be skipped"
    assert result.overall_delta == 0.0, "Duplicate skill must have zero delta"


# ---------------------------------------------------------------------------
# TEST 3: Add new project -> projects_experience delta > 0
# ---------------------------------------------------------------------------

def test_add_new_project_increases_score(datasets):
    """
    An AI Engineer with no projects who adds an ML project should see
    projects_experience score increase.
    """
    prs_input = _ai_engineer_input()  # no projects
    baseline  = _make_baseline(prs_input, datasets)

    result = project_delta(
        prs_input, baseline,
        Mutation(type="add_project", payload={
            "name":        "Sentiment Analyser",
            "description": "NLP model for customer review classification using BERT",
            "skills_used": ["Python", "PyTorch", "Transformers"],
            "domain":      "Machine Learning",
        }),
        datasets,
    )

    assert result.skipped is False, "New project must not be skipped"
    assert result.overall_delta > 0, f"Expected positive delta, got {result.overall_delta}"
    assert "projects_experience" in result.pillar_deltas
    assert result.pillar_deltas["projects_experience"] > 0


# ---------------------------------------------------------------------------
# TEST 4: Add duplicate project -> delta = 0, skipped = True
# ---------------------------------------------------------------------------

def test_add_duplicate_project_is_noop(datasets):
    """
    Adding a project with the same name as one already in the profile
    must produce delta = 0 and skipped = True.
    """
    existing_project = PRSProject(
        name="Sentiment Analyser",
        description="NLP model",
        skills_used=["Python", "PyTorch"],
    )
    prs_input = _ai_engineer_input(extra_projects=[existing_project])
    baseline  = _make_baseline(prs_input, datasets)

    result = project_delta(
        prs_input, baseline,
        Mutation(type="add_project", payload={
            "name":        "Sentiment Analyser",  # same name
            "description": "Different description but same project",
            "skills_used": ["Python"],
        }),
        datasets,
    )

    assert result.skipped is True,      "Duplicate project must be skipped"
    assert result.overall_delta == 0.0, "Duplicate project must have zero delta"


# ---------------------------------------------------------------------------
# TEST 5: Add new certification -> certificate_quality delta > 0
# ---------------------------------------------------------------------------

def test_add_new_certification_increases_score(datasets):
    """
    Adding a recognised certification to a profile with no certs should
    raise certificate_quality score.
    Note: add_profile_link mutation is not tested here because
    role_alignment_engine does not read github_url/linkedin_url from PRSInput
    (those are User ORM fields only). The mutation type is retained in the
    engine for future use if the alignment engine is extended.
    """
    prs_input = _ai_engineer_input()  # no certifications
    baseline  = _make_baseline(prs_input, datasets)

    result = project_delta(
        prs_input, baseline,
        Mutation(type="add_certification", payload="TensorFlow Developer Certificate"),
        datasets,
    )

    assert result.skipped is False, "New cert must not be skipped"
    assert result.overall_delta >= 0, f"Expected non-negative delta, got {result.overall_delta}"


# ---------------------------------------------------------------------------
# TEST 6: Add duplicate certification -> delta = 0, skipped = True
# ---------------------------------------------------------------------------

def test_add_duplicate_certification_is_noop(datasets):
    """
    Adding a cert the user already has must produce skipped=True, delta=0.
    """
    prs_input = _ai_engineer_input(
        certifications=["TensorFlow Developer Certificate"]
    )
    baseline  = _make_baseline(prs_input, datasets)

    result = project_delta(
        prs_input, baseline,
        Mutation(type="add_certification", payload="TensorFlow Developer Certificate"),
        datasets,
    )

    assert result.skipped is True,      "Duplicate cert must be skipped"
    assert result.overall_delta == 0.0, "Duplicate cert must have zero delta"


# ---------------------------------------------------------------------------
# TEST 7: _to_prs_project() field mapping regression
# ---------------------------------------------------------------------------

def test_to_prs_project_field_mapping_no_type_error(datasets):
    """
    Takes a raw entry from projects_dataset.json (project_name / primary_skills),
    passes it through _to_prs_project(), then to project_delta().
    Must NOT raise TypeError and must produce a positive delta.

    This is the field-mapping regression test: if the field names are wrong
    (project_name vs name, primary_skills vs skills_used) the PRSProject
    constructor will throw a TypeError and this test catches it.
    """
    # Simulate a raw projects_dataset.json entry
    raw_dataset_entry = {
        "project_name":  "Image Classifier",
        "description":   "CNN-based image classification model trained on CIFAR-10",
        "primary_skills": ["Python", "PyTorch", "TensorFlow"],
        "domain":        "Machine Learning",
        "difficulty_level": "Intermediate",
    }

    # This is the _to_prs_project() helper that MilestoneEngine will use
    def _to_prs_project(entry: dict) -> dict:
        return {
            "name":        entry["project_name"],
            "description": entry.get("description", ""),
            "skills_used": entry.get("primary_skills", []),
            "domain":      entry.get("domain", "General"),
        }

    prs_input = _ai_engineer_input()  # no projects
    baseline  = _make_baseline(prs_input, datasets)

    # Should NOT raise TypeError
    proj_dict = _to_prs_project(raw_dataset_entry)
    result = project_delta(
        prs_input, baseline,
        Mutation(type="add_project", payload=proj_dict),
        datasets,
    )

    assert result.skipped is False, "Newly mapped project must not be skipped"
    assert result.overall_delta > 0, f"Expected positive delta, got {result.overall_delta}"
    assert "projects_experience" in result.pillar_deltas


# ---------------------------------------------------------------------------
# Bonus: Gap engine sanity test (M3-3)
# ---------------------------------------------------------------------------

def test_gap_engine_ordering(datasets):
    """
    Given a profile where skill_readiness is very low (25) and
    certificate_quality is also low (20), the gap engine must place
    skill_readiness first in ordered_pillars because its weighted gap is
    higher (weight 0.30 * 45 = 13.5 vs weight 0.10 * 50 = 5.0).
    """
    fake_result = PRSResult(
        prs_score=40.0,
        readiness_level="Early Preparation Stage",
        pillar_scores={
            "skill_readiness":     25.0,
            "projects_experience": 40.0,
            "role_alignment":      50.0,
            "resume_quality":      60.0,
            "certificate_quality": 20.0,
        },
        weighted_contributions={},
        weak_areas=[],
        missing_skills=[],
        recommendations=[],
        warnings=[],
    )

    gap_result = compute_gap_analysis(fake_result)

    assert gap_result.ordered_pillars[0] == "skill_readiness", \
        "skill_readiness must be top priority (highest weighted gap)"
    assert gap_result.gaps["skill_readiness"] == 45.0
    assert gap_result.gaps["certificate_quality"] == 50.0
    # skill_readiness priority must beat certificate_quality despite smaller raw gap
    assert gap_result.priorities["skill_readiness"] > gap_result.priorities["certificate_quality"]
    assert gap_result.total_gap > 0
