"""
app/services/career/career_orchestrator.py
============================================
Module 3 — M3-8: Career Path Orchestrator.

What this file does:
  The single entry point for the full career simulation pipeline.
  Coordinates all 5 M3 engines in the correct order and returns a single
  CareerPathResult dataclass that the API router (M3-9) persists to DB.

Overall design:
  Engines called in order:
    1. load_prs_datasets()           shared cached datasets
    2. _get_fresh_prs_eval()         Option B freshness check (400 if no eval)
    3. _reconstruct_prs_result()     rebuild PRSResult from stored eval scores
    4. compute_gap_analysis()        M3-3
    5. generate_milestones()         M3-5 (calls project_delta() internally)
    6. compute_eta()                 M3-6
    7. get_role_progression()        M3-7

  What-if runs separately through run_what_if() — NOT called here.

Elements:
  CareerPathResult     dataclass  Full pipeline output for one simulate request
  orchestrate_career() function   Main public entry point called by M3-9 router
  _get_fresh_prs_eval()           Option B freshness gate
  _reconstruct_prs_result()       Rebuild PRSResult from DB stored column values

Final output:
  CareerPathResult ready to be serialised and written to career_paths table.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.services.prs.dataset_loader   import load_prs_datasets, DatasetValidationError
from app.services.prs.input_builder    import build_prs_input, PRSInput
from app.services.prs.orchestrator     import PRSResult, orchestrate_prs
from app.services.prs.constants        import PILLAR_WEIGHTS

from app.services.career.gap_engine         import compute_gap_analysis, GapAnalysisResult
from app.services.career.milestone_engine   import generate_milestones,  MilestoneResult
from app.services.career.eta_engine         import compute_eta,           ETAResult
from app.services.career.progression_engine import get_role_progression,  ProgressionResult


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class CareerPathResult:
    """
    Use:
      Full pipeline output for one POST /career/simulate request.
      The M3-9 router maps this directly to a models.CareerPath ORM row.

    Contains:
      prs_input        PRSInput  input used (for debugging/snapshot if needed)
      baseline_prs     PRSResult baseline before any milestones
      gap_result       GapAnalysisResult  per-pillar gap analysis
      milestone_result MilestoneResult    ordered milestone list
      eta_result       ETAResult          weekly plan + ETA
      progression      ProgressionResult  role progression chain
      prs_eval_id      int  FK to the readiness_evaluations row that was used
    """
    prs_input:        PRSInput
    baseline_prs:     PRSResult
    gap_result:       GapAnalysisResult
    milestone_result: MilestoneResult
    eta_result:       ETAResult
    progression:      ProgressionResult
    prs_eval_id:      int | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_fresh_prs_eval(
    user_id:     int,
    target_role: str,
    db:          Session,
) -> models.ReadinessEvaluation:
    """
    Use:
      Option B freshness gate: Module 3 requires an existing PRS evaluation.
      Returns the most recent eval for (user_id, target_role).
      Raises HTTP 400 with a hint if none found.

    How it works:
      Queries readiness_evaluations ordered by created_at DESC, takes first.
      If result is None, raises 400 with a message telling the client to run
      /prs/evaluate first — never silently re-runs the PRS pipeline here.

    Concepts:
      Option B (Design Decision D3): keeps Module 3 stateless on the hot path.
      The PRS eval is the freshness contract. The student runs /prs/evaluate
      whenever they update their profile, then /career/simulate uses that result.

    Used by: orchestrate_career() only.

    Output:
      models.ReadinessEvaluation ORM row, or raises HTTPException(400).
    """
    eval_row = (
        db.query(models.ReadinessEvaluation)
        .filter(
            models.ReadinessEvaluation.user_id    == user_id,
            models.ReadinessEvaluation.target_role == target_role,
        )
        .order_by(models.ReadinessEvaluation.created_at.desc())
        .first()
    )
    if not eval_row:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"No PRS evaluation found for role '{target_role}'.",
                "hint":  "Run POST /prs/evaluate for this role first, then retry /career/simulate.",
            },
        )
    return eval_row


def _reconstruct_prs_result(
    eval_row:    models.ReadinessEvaluation,
    target_role: str,
) -> PRSResult:
    """
    Use:
      Rebuild a PRSResult dataclass from stored column values in a
      ReadinessEvaluation row. Avoids re-running all 5 PRS engines.

    How it works:
      Reads the 5 pillar score columns. Calls orchestrate_prs() with those
      exact values to get the correct weighted_contributions + readiness_level.
      weak_areas, missing_skills, recommendations are read from the stored JSON
      columns (they were persisted at evaluation time).

    Concepts:
      Deterministic re-orchestration: given the same 5 pillar scores,
      orchestrate_prs() always produces the same result. So we can safely
      call it here without re-running the expensive embedding engines.

    Used by: orchestrate_career() only.

    Output:
      PRSResult equivalent to what /prs/evaluate produced for this eval.
    """
    return orchestrate_prs(
        target_role=target_role,
        skill_readiness_score=eval_row.skill_readiness_score    or 0.0,
        projects_experience_score=eval_row.projects_experience_score or 0.0,
        role_alignment_score=eval_row.role_alignment_score      or 0.0,
        resume_quality_score=eval_row.resume_quality_score      or 0.0,
        certificate_quality_score=eval_row.certificate_quality_score or 0.0,
        engine_weak_areas=eval_row.weak_areas    or [],
        missing_skills=eval_row.missing_skills   or [],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def orchestrate_career(
    user:                 models.User,
    target_role:          str,
    study_hours_per_week: int,
    target_prs_score:     float,
    db:                   Session,
) -> CareerPathResult:
    """
    Use:
      Full career path simulation pipeline. Called by POST /career/simulate.
      Runs all 5 M3 engines in order and returns a CareerPathResult.

    How it works:
      1. Load datasets (cached — no I/O if already loaded)
      2. Validate target_role against datasets.roles
      3. Option B freshness gate: get most recent PRS eval for this user+role
      4. Reconstruct PRSResult from stored pillar scores (no engine re-run)
      5. Build PRSInput from user ORM (for mutation engine inputs)
      6. compute_gap_analysis()  — per-pillar weighted gap
      7. generate_milestones()   — ROI-sorted milestones (calls project_delta())
      8. compute_eta()           — week-by-week plan + total weeks
      9. get_role_progression()  — career chain lookup
      10. Return CareerPathResult

    Concepts:
      Selective re-evaluation: steps 7 re-runs only 1-2 affected engines per
      milestone candidate via project_delta(). All other pillars use baseline.
      This keeps the full simulate call under 3s even with 10+ milestones.

    Imports used by: main.py M3-9 endpoint.

    Parameters:
      user                 models.User  authenticated user with skills+projects loaded
      target_role          str          role to simulate for
      study_hours_per_week int          hours/week from request (or user default)
      target_prs_score     float        target PRS threshold (default 70.0)
      db                   Session      DB session

    Output:
      CareerPathResult with all engine outputs populated.
    """
    # 1. Load datasets
    try:
        datasets = load_prs_datasets()
    except DatasetValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": "Career datasets unavailable.", "errors": exc.errors},
        )

    # 2. Validate role
    available_roles = {r.lower() for r in datasets.roles}
    if target_role.strip().lower() not in available_roles:
        raise HTTPException(
            status_code=422,
            detail=f"Role '{target_role}' is not supported. Available roles: {sorted(datasets.roles)}",
        )
    target_role = target_role.strip()

    # 3. Option B freshness gate
    eval_row = _get_fresh_prs_eval(user.id, target_role, db)

    # 4. Reconstruct PRSResult from stored scores
    baseline_prs = _reconstruct_prs_result(eval_row, target_role)

    # 5. Build PRSInput from user ORM (needed by milestone engine for dedup)
    prs_input = build_prs_input(
        user=user,
        target_role=target_role,
        assessment_answers=eval_row.assessment_answers or {},
    )

    # 6. Gap Analysis
    gap_result = compute_gap_analysis(baseline_prs, target_prs=target_prs_score)

    # 7. Milestone Generation
    milestone_result = generate_milestones(
        prs_input=prs_input,
        baseline_prs=baseline_prs,
        gap_result=gap_result,
        datasets=datasets,
        max_milestones=10,
    )

    # 8. ETA
    eta_result = compute_eta(
        milestone_result=milestone_result,
        baseline_prs_score=baseline_prs.prs_score,
        study_hours_per_week=study_hours_per_week,
    )

    # 9. Role Progression
    progression = get_role_progression(target_role, datasets)

    return CareerPathResult(
        prs_input=prs_input,
        baseline_prs=baseline_prs,
        gap_result=gap_result,
        milestone_result=milestone_result,
        eta_result=eta_result,
        progression=progression,
        prs_eval_id=eval_row.id,
    )
