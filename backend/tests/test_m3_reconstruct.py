"""
tests/test_m3_reconstruct.py
==============================
Integration test for _reconstruct_prs_result().

What this tests:
  _reconstruct_prs_result() is load-bearing: every /career/simulate call
  computes its gap analysis and milestones against the PRSResult it returns.
  If ANY column is misread or ANY pillar_scores key is wrong, the gap engine
  silently returns 0.0 for that pillar (pillar_scores.get(pillar, 0.0)),
  making every pillar look maximally gapped and corrupting the milestone ROI sort.

Tests:
  1. All 5 pillar_scores keys match PILLAR_WEIGHTS exactly (no key mismatches)
  2. pillar_scores values equal the fixture column values (no zeroing, no swap)
  3. prs_score is the correct weighted sum of the fixture values
  4. A zero column value stays zero (not swapped or silently replaced)

Run:
  cd backend
  .\\venv\\Scripts\\python.exe -m pytest tests/test_m3_reconstruct.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock
from app.services.career.career_orchestrator import _reconstruct_prs_result
from app.services.prs.constants import PILLAR_WEIGHTS


def _make_eval_row(
    skill=55.0,
    projects=40.0,
    role=62.0,
    resume=70.0,
    cert=30.0,
    weak_areas=None,
    missing_skills=None,
):
    """
    Build a mock ReadinessEvaluation row with known column values.
    Using MagicMock avoids needing a real DB session in this test.
    """
    row = MagicMock()
    row.skill_readiness_score      = skill
    row.projects_experience_score  = projects
    row.role_alignment_score       = role
    row.resume_quality_score       = resume
    row.certificate_quality_score  = cert
    row.weak_areas                 = weak_areas or []
    row.missing_skills             = missing_skills or []
    return row


# ---------------------------------------------------------------------------
# Test 1: All 5 pillar_scores keys exactly match PILLAR_WEIGHTS
# ---------------------------------------------------------------------------

def test_pillar_scores_keys_match_pillar_weights():
    """
    If any key is wrong (e.g. 'skills' vs 'skill_readiness'), gap_engine's
    prs_result.pillar_scores.get(pillar, 0.0) silently returns 0.0.
    This test ensures the key set is identical to PILLAR_WEIGHTS.
    """
    row    = _make_eval_row()
    result = _reconstruct_prs_result(row, "AI Engineer")

    assert set(result.pillar_scores.keys()) == set(PILLAR_WEIGHTS.keys()), (
        f"Key mismatch.\n"
        f"  Expected: {sorted(PILLAR_WEIGHTS.keys())}\n"
        f"  Got:      {sorted(result.pillar_scores.keys())}"
    )


# ---------------------------------------------------------------------------
# Test 2: pillar_scores values equal fixture column values (no column swap)
# ---------------------------------------------------------------------------

def test_pillar_scores_values_match_eval_columns():
    """
    Verifies that each pillar_scores[key] equals the corresponding eval_row
    column value. If columns are swapped (e.g. skill↔role) milestones are
    prioritised against the wrong pillar scores.
    """
    row    = _make_eval_row(skill=55.0, projects=40.0, role=62.0, resume=70.0, cert=30.0)
    result = _reconstruct_prs_result(row, "AI Engineer")

    assert result.pillar_scores["skill_readiness"]     == 55.0, "skill_readiness mismatch"
    assert result.pillar_scores["projects_experience"] == 40.0, "projects_experience mismatch"
    assert result.pillar_scores["role_alignment"]      == 62.0, "role_alignment mismatch"
    assert result.pillar_scores["resume_quality"]      == 70.0, "resume_quality mismatch"
    assert result.pillar_scores["certificate_quality"] == 30.0, "certificate_quality mismatch"


# ---------------------------------------------------------------------------
# Test 3: prs_score equals the correct weighted sum of fixture values
# ---------------------------------------------------------------------------

def test_prs_score_is_correct_weighted_sum():
    """
    Verifies the reconstructed prs_score matches the manually computed
    weighted sum. Catches off-by-weight bugs in orchestrate_prs() when
    called via _reconstruct_prs_result().
    """
    skill, projects, role, resume, cert = 55.0, 40.0, 62.0, 70.0, 30.0
    row    = _make_eval_row(skill=skill, projects=projects, role=role, resume=resume, cert=cert)
    result = _reconstruct_prs_result(row, "AI Engineer")

    expected = sum([
        skill    * PILLAR_WEIGHTS["skill_readiness"],
        projects * PILLAR_WEIGHTS["projects_experience"],
        role     * PILLAR_WEIGHTS["role_alignment"],
        resume   * PILLAR_WEIGHTS["resume_quality"],
        cert     * PILLAR_WEIGHTS["certificate_quality"],
    ])

    assert abs(result.prs_score - expected) < 0.1, (
        f"prs_score wrong: expected ~{expected:.2f}, got {result.prs_score:.2f}"
    )


# ---------------------------------------------------------------------------
# Test 4: A zero column stays zero (None → 0.0, not swapped to another pillar)
# ---------------------------------------------------------------------------

def test_zero_column_stays_zero_not_swapped():
    """
    When certificate_quality_score is 0.0 (user has no certs), the
    reconstructed pillar_scores["certificate_quality"] must also be 0.0.
    It must NOT receive another pillar's value (column swap bug).
    And skill_readiness must remain its correct value.
    """
    row    = _make_eval_row(skill=75.0, projects=60.0, role=65.0, resume=70.0, cert=0.0)
    result = _reconstruct_prs_result(row, "AI Engineer")

    assert result.pillar_scores["certificate_quality"] == 0.0, \
        "Zero cert score must stay zero — not replaced by another pillar"
    assert result.pillar_scores["skill_readiness"] == 75.0, \
        "skill_readiness must not be affected by zero cert score"
