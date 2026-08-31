"""
app/services/career/what_if_engine.py
=======================================
Module 3 - M3-4: What-If Engine.

What this file does:
  Provides project_delta() - the single canonical delta function used by
  BOTH the MilestoneEngine (M3-5) and the WhatIfEngine (this file).
  Also provides run_what_if() for the /career/what-if API endpoint.

Overall design:
  Selective re-evaluation: only re-runs the 1-2 PRS engines affected by a
  given mutation, takes all other pillar scores from baseline unchanged.
  This keeps latency under 300ms even for 5-mutation what-if requests.

  ALL delta calculations in Module 3 go through project_delta().
  No separate estimate functions. No ad-hoc math.

Elements:
  Mutation         dataclass  One hypothetical change to apply
  DeltaResult      dataclass  Score change produced by project_delta()
  WhatIfRequest    dataclass  Input to run_what_if()
  WhatIfResult     dataclass  Output of run_what_if()
  project_delta()             Core primitive - used by M3-5 milestone engine too
  run_what_if()               Applies multiple mutations, returns combined result

Final output:
  project_delta(): DeltaResult with overall_delta, per-pillar deltas, new scores
  run_what_if():   WhatIfResult with combined delta and per-mutation breakdown
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from app.services.prs.input_builder import PRSInput, PRSSkill, PRSProject
from app.services.prs.orchestrator import PRSResult
from app.services.prs.dataset_loader import PRSDatasets
from app.services.prs.skill_engine import calculate_skill_readiness
from app.services.prs.projects_engine import calculate_projects_experience
from app.services.prs.certificate_engine import calculate_certificate_quality
from app.services.prs.role_alignment_engine import calculate_role_alignment
from app.services.prs.constants import PILLAR_WEIGHTS


# ---------------------------------------------------------------------------
# Input / output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Mutation:
    """
    Use:
      Represents one hypothetical change to apply to a PRSInput clone.
      Used as input to project_delta().

    Contains:
      type     one of: "add_skill" | "add_project" | "add_certification" |
                       "add_profile_link"
      payload  varies by type:
               add_skill:        str  (skill name)
               add_project:      dict with keys name, description, skills_used, domain
               add_certification: str (cert name)
               add_profile_link: str (PRSInput attr name: "github_url" | "linkedin_url")

    Technologies: Python dataclass. No serialisation needed - only used in memory.
    """
    type: str
    payload: Any


@dataclass
class DeltaResult:
    """
    Use:
      Return value of project_delta(). Describes the score change caused by
      applying ONE mutation to the baseline.

    Contains:
      overall_delta      float   change to prs_score (positive = improvement)
      pillar_deltas      dict    per-pillar score changes (only affected pillars included)
      new_pillar_scores  dict    all 5 pillar scores after mutation
      new_prs_score      float   new overall PRS after mutation
      skipped            bool    True when the mutation was a no-op (item already present)
                                 If True all numeric fields are 0.0 / unchanged.

    Key design:
      skipped=True is the dedup guard outcome. MilestoneEngine checks this
      and skips generating a milestone for something the student already has.
    """
    overall_delta:     float
    pillar_deltas:     dict[str, float]
    new_pillar_scores: dict[str, float]
    new_prs_score:     float
    skipped:           bool = False


@dataclass
class WhatIfRequest:
    """
    Use:
      Input payload for run_what_if(). Maps directly to the POST /career/what-if
      request body (Pydantic schema in M3-9 mirrors these fields).

    Contains:
      target_role              str   role the student is evaluating for
      hypothetical_skills      list  skill names to add hypothetically
      hypothetical_project     dict  a single project to add (or None)
      hypothetical_certifications list  cert names to add
      hypothetical_profile_links  list  field names to mark as present
    """
    target_role: str
    hypothetical_skills:         list[str]       = field(default_factory=list)
    hypothetical_project:        dict | None      = None
    hypothetical_certifications: list[str]       = field(default_factory=list)
    hypothetical_profile_links:  list[str]       = field(default_factory=list)


@dataclass
class WhatIfResult:
    """
    Use:
      Return value of run_what_if(). Returned by POST /career/what-if endpoint.

    Contains:
      original_prs_score    float  baseline PRS before any mutations
      simulated_prs_score   float  PRS after all mutations applied
      overall_delta         float  net change (simulated - original)
      mutations_applied     int    how many mutations actually changed scores
      mutations_skipped     int    how many were no-ops (dedup guard triggered)
      per_mutation          list   DeltaResult-like dict per mutation
      summary               str    human-readable "Your PRS could improve by X points"
    """
    original_prs_score:  float
    simulated_prs_score: float
    overall_delta:       float
    mutations_applied:   int
    mutations_skipped:   int
    per_mutation:        list[dict]
    summary:             str


# ---------------------------------------------------------------------------
# Core primitive: project_delta()
# ---------------------------------------------------------------------------

def project_delta(
    prs_input:    PRSInput,
    baseline_prs: PRSResult,
    mutation:     Mutation,
    datasets:     PRSDatasets,
) -> DeltaResult:
    """
    Use:
      The ONE canonical delta function for all of Module 3.
      Called by MilestoneEngine (once per candidate milestone to get ROI)
      and by run_what_if() (once per mutation in the what-if request).
      No other code in Module 3 computes score deltas differently.

    How it works:
      1. Check dedup guard - if item already exists in prs_input, return skipped.
      2. deepcopy prs_input (never mutate the original).
      3. Apply the mutation to the copy.
      4. Re-run ONLY the affected engine(s):
           add_skill        -> skill_engine + role_alignment_engine  (2 engines)
           add_project      -> projects_engine                        (1 engine)
           add_certification-> certificate_engine                     (1 engine)
           add_profile_link -> role_alignment_engine                  (1 engine)
      5. Merge new engine scores with baseline scores for other pillars.
      6. Recompute weighted PRS from merged scores.
      7. Return DeltaResult with the change.

    Concepts:
      Selective re-evaluation: avoids running all 5 engines per mutation.
      deepcopy: prevents the mutation from contaminating subsequent deltas
      when run_what_if() applies multiple mutations in sequence.
      Dedup guard: adding a skill the student already has must produce delta=0.

    Imports used by:
      - milestone_engine.py (M3-5): called in _score_milestone()
      - what_if_engine.py (this file): called in run_what_if()

    Parameters:
      prs_input    PRSInput  the student's current state (NEVER modified)
      baseline_prs PRSResult already-computed result to diff against
      mutation     Mutation  the hypothetical change to apply
      datasets     PRSDatasets  loaded dataset cache

    Output:
      Before: baseline_prs.prs_score e.g. 52.0
      After:  DeltaResult(overall_delta=+3.4, new_prs_score=55.4, skipped=False)
      If already present: DeltaResult(overall_delta=0.0, skipped=True)
    """
    _ZERO = DeltaResult(
        overall_delta=0.0,
        pillar_deltas={},
        new_pillar_scores=dict(baseline_prs.pillar_scores),
        new_prs_score=baseline_prs.prs_score,
        skipped=True,
    )

    modified = deepcopy(prs_input)

    # --- DEDUP GUARD + MUTATION APPLICATION ---
    if mutation.type == "add_skill":
        skill_name: str = mutation.payload
        existing = {s.skill.lower() for s in prs_input.skills}
        if skill_name.lower() in existing:
            return _ZERO
        modified.skills.append(PRSSkill(skill=skill_name))

        new_skill = calculate_skill_readiness(modified, datasets)
        new_align = calculate_role_alignment(modified, datasets)
        new_scores = {
            **baseline_prs.pillar_scores,
            "skill_readiness": new_skill.score,
            "role_alignment":  new_align.score,
        }

    elif mutation.type == "add_project":
        proj_dict: dict = mutation.payload
        existing_names = {p.name.lower() for p in prs_input.projects}
        if proj_dict.get("name", "").lower() in existing_names:
            return _ZERO
        modified.projects.append(PRSProject(
            name=proj_dict["name"],
            description=proj_dict.get("description", ""),
            skills_used=proj_dict.get("skills_used", []),
            domain=proj_dict.get("domain"),
        ))

        new_proj = calculate_projects_experience(modified, datasets)
        new_scores = {
            **baseline_prs.pillar_scores,
            "projects_experience": new_proj.score,
        }

    elif mutation.type == "add_certification":
        cert_name: str = mutation.payload
        existing_certs = {c.lower() for c in prs_input.certifications}
        if cert_name.lower() in existing_certs:
            return _ZERO
        modified.certifications.append(cert_name)

        new_cert = calculate_certificate_quality(modified, datasets)
        new_scores = {
            **baseline_prs.pillar_scores,
            "certificate_quality": new_cert.score,
        }

    elif mutation.type == "add_profile_link":
        field_name: str = mutation.payload   # e.g. "github_url", "linkedin_url"
        if getattr(prs_input, field_name, None):
            return _ZERO
        setattr(modified, field_name, "https://placeholder.example.com")

        new_align = calculate_role_alignment(modified, datasets)
        new_scores = {
            **baseline_prs.pillar_scores,
            "role_alignment": new_align.score,
        }

    else:
        return _ZERO

    # --- RECOMPUTE WEIGHTED PRS ---
    new_prs = sum(new_scores.get(p, 0.0) * w for p, w in PILLAR_WEIGHTS.items())
    new_prs = round(min(100.0, max(0.0, new_prs)), 2)

    pillar_deltas = {
        p: round(new_scores[p] - baseline_prs.pillar_scores.get(p, 0.0), 2)
        for p in new_scores
        if round(new_scores[p] - baseline_prs.pillar_scores.get(p, 0.0), 2) != 0.0
    }

    return DeltaResult(
        overall_delta=round(new_prs - baseline_prs.prs_score, 2),
        pillar_deltas=pillar_deltas,
        new_pillar_scores=new_scores,
        new_prs_score=new_prs,
        skipped=False,
    )


# ---------------------------------------------------------------------------
# What-If runner: applies multiple mutations in sequence
# ---------------------------------------------------------------------------

def run_what_if(
    prs_input:    PRSInput,
    baseline_prs: PRSResult,
    request:      WhatIfRequest,
    datasets:     PRSDatasets,
) -> WhatIfResult:
    """
    Use:
      Applies all hypothetical mutations from a WhatIfRequest in sequence,
      accumulating the new pillar scores as each mutation is applied.
      Called by POST /career/what-if endpoint in M3-9.

    How it works:
      1. Build a flat list of Mutations from the request fields.
      2. Start from a working baseline = baseline_prs.
      3. For each mutation: call project_delta(current_input, current_baseline, mutation, datasets).
         If skipped, record it but don't update the working baseline.
         If applied, update working_input with the mutation and update working_baseline
         so the next mutation's delta is computed against the already-mutated state.
      4. Compute final simulated PRS and summary string.

    Concepts:
      Sequential accumulation: skill A might enable skill B to have a higher
      role_alignment delta. If we ran all mutations against the same original
      baseline we'd miss this compounding effect.

    Imports used by: app/main.py router in M3-9.

    Output:
      WhatIfResult with combined delta, per-mutation breakdown, and summary.
    """
    # Build flat mutation list
    mutations: list[Mutation] = []
    for skill in request.hypothetical_skills:
        mutations.append(Mutation(type="add_skill", payload=skill))
    if request.hypothetical_project:
        mutations.append(Mutation(type="add_project", payload=request.hypothetical_project))
    for cert in request.hypothetical_certifications:
        mutations.append(Mutation(type="add_certification", payload=cert))
    for link in request.hypothetical_profile_links:
        mutations.append(Mutation(type="add_profile_link", payload=link))

    if not mutations:
        return WhatIfResult(
            original_prs_score=round(baseline_prs.prs_score, 2),
            simulated_prs_score=round(baseline_prs.prs_score, 2),
            overall_delta=0.0,
            mutations_applied=0,
            mutations_skipped=0,
            per_mutation=[],
            summary="No hypothetical changes provided.",
        )

    # Sequential accumulation
    current_input    = prs_input
    current_baseline = baseline_prs
    per_mutation_results: list[dict] = []
    applied = 0
    skipped = 0

    for mut in mutations:
        delta = project_delta(current_input, current_baseline, mut, datasets)
        per_mutation_results.append({
            "mutation_type": mut.type,
            "payload":       mut.payload if isinstance(mut.payload, str) else str(mut.payload.get("name", "")),
            "delta":         delta.overall_delta,
            "skipped":       delta.skipped,
            "new_prs_score": delta.new_prs_score,
        })
        if delta.skipped:
            skipped += 1
        else:
            applied += 1
            # Build a synthetic PRSResult from the new scores for the next iteration
            current_baseline = PRSResult(
                prs_score=delta.new_prs_score,
                readiness_level=current_baseline.readiness_level,
                pillar_scores=delta.new_pillar_scores,
                weighted_contributions={
                    p: delta.new_pillar_scores.get(p, 0.0) * w
                    for p, w in PILLAR_WEIGHTS.items()
                },
                weak_areas=current_baseline.weak_areas,
                missing_skills=current_baseline.missing_skills,
                recommendations=current_baseline.recommendations,
                warnings=current_baseline.warnings,
            )
            # Apply mutation to the working input so subsequent deltas are sequential
            working = deepcopy(current_input)
            if mut.type == "add_skill":
                working.skills.append(PRSSkill(skill=mut.payload))
            elif mut.type == "add_project":
                p = mut.payload
                working.projects.append(PRSProject(
                    name=p["name"], description=p.get("description", ""),
                    skills_used=p.get("skills_used", []), domain=p.get("domain"),
                ))
            elif mut.type == "add_certification":
                working.certifications.append(mut.payload)
            elif mut.type == "add_profile_link":
                setattr(working, mut.payload, "https://placeholder.example.com")
            current_input = working

    original = round(baseline_prs.prs_score, 2)
    simulated = round(current_baseline.prs_score, 2)
    net_delta = round(simulated - original, 2)

    if net_delta > 0:
        summary = f"These changes could improve your PRS by {net_delta} points ({original} -> {simulated})."
    elif net_delta == 0:
        summary = "You already have all of these skills/projects. No score change."
    else:
        summary = f"Unexpected delta of {net_delta}. Check inputs."

    return WhatIfResult(
        original_prs_score=original,
        simulated_prs_score=simulated,
        overall_delta=net_delta,
        mutations_applied=applied,
        mutations_skipped=skipped,
        per_mutation=per_mutation_results,
        summary=summary,
    )
