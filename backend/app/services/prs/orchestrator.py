"""
Phase 11 -- PRS Orchestrator
==============================
Combines the five pillar scores into a final, deterministic PRS score
and assigns a readiness level label.

Formula (spec-defined):
    prs_score =
        (skill_readiness_score      x 0.30)
      + (projects_experience_score  x 0.25)
      + (role_alignment_score       x 0.20)
      + (resume_quality_score       x 0.15)
      + (certificate_quality_score  x 0.10)

Readiness levels (spec-defined):
    85-100  Highly Placement Ready
    70-84   Industry Ready
    55-69   Developing Readiness
    40-54   Needs Improvement
    0-39    Early Preparation Stage

Phase 11 completion criterion:
    PRS can be manually reproduced exactly from the five component scores.

Design rules:
    - No hard-coded weak area strings that reference specific scores.
    - All weak areas come from actual pillar scores and missing skills.
    - Score clamped to [0, 100] before storing.
    - Safe even when a pillar returns None (treats it as 0 with a warning).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Import shared constants from single source of truth (Phase M3-0)
from app.services.prs.constants import (
    PILLAR_WEIGHTS,
    INDUSTRY_READY_THRESHOLD,
    WEAK_PILLAR_THRESHOLD,
    HINT_PILLAR_THRESHOLD,
    STRONG_PILLAR_THRESHOLD,
    READINESS_LEVELS,
)

# Backward-compatible alias: existing code that imports PRS_WEIGHTS from orchestrator still works
PRS_WEIGHTS: dict[str, float] = PILLAR_WEIGHTS


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class PRSResult:
    """Complete PRS orchestrator output — every field maps to a DB column."""
    prs_score: float
    readiness_level: str
    pillar_scores: dict[str, float]       # name -> actual score used in formula
    weighted_contributions: dict[str, float]  # name -> contribution to prs_score
    weak_areas: list[str]                  # merged, de-duplicated, score-derived
    missing_skills: list[str]              # from skill engine
    recommendations: list[str]            # high-level text hints (Phase 12 will replace)
    warnings: list[str]                   # data quality alerts (None pillar etc.)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prs_score":               round(self.prs_score, 2),
            "readiness_level":         self.readiness_level,
            "pillar_scores":           {k: round(v, 2) for k, v in self.pillar_scores.items()},
            "weighted_contributions":  {k: round(v, 2) for k, v in self.weighted_contributions.items()},
            "weak_areas":              self.weak_areas,
            "missing_skills":          self.missing_skills,
            "recommendations":         self.recommendations,
            "warnings":                self.warnings,
            "formula": {
                "skill_readiness":     "x 0.30",
                "projects_experience": "x 0.25",
                "role_alignment":      "x 0.20",
                "resume_quality":      "x 0.15",
                "certificate_quality": "x 0.10",
            },
        }


# ---------------------------------------------------------------------------
# Readiness level
# ---------------------------------------------------------------------------

def _assign_readiness_level(score: float) -> str:
    """Return the spec-defined readiness label for a given PRS score."""
    for threshold, label in READINESS_LEVELS:
        if score >= threshold:
            return label
    return "Early Preparation Stage"


# ---------------------------------------------------------------------------
# Pillar score normalization
# ---------------------------------------------------------------------------

def _safe_score(value: float | None, pillar_name: str, warnings: list[str]) -> float:
    """
    Coerce a pillar score to a valid float in [0, 100].
    Treats None as 0 and appends a warning so the caller can surface the issue.
    """
    if value is None:
        warnings.append(
            f"Pillar '{pillar_name}' returned None -- treated as 0.0 in PRS formula."
        )
        return 0.0
    return max(0.0, min(100.0, float(value)))


# ---------------------------------------------------------------------------
# Weak area synthesis (score-derived, no hard-coded strings)
# ---------------------------------------------------------------------------

def _pillar_display_name(key: str) -> str:
    return {
        "skill_readiness":     "Skill Readiness",
        "projects_experience": "Projects & Experience",
        "role_alignment":      "Role Alignment",
        "resume_quality":      "Resume Quality",
        "certificate_quality": "Certificate Quality",
    }.get(key, key.replace("_", " ").title())


def _synthesize_weak_areas(
    pillar_scores: dict[str, float],
    engine_weak_areas: list[str],
    missing_skills: list[str],
    target_role: str,
) -> list[str]:
    """
    Build the final merged weak_areas list from:
      1. Score-derived pillar weakness detection (no hard-coding).
      2. Engine-specific weak areas (already scored-derived in each engine).
      3. Missing skills for the target role.

    De-duplicates and caps at a reasonable length.
    """
    weak: list[str] = []

    # 1. Pillar-level weaknesses
    sorted_pillars = sorted(pillar_scores.items(), key=lambda x: x[1])
    for pillar_key, score in sorted_pillars:
        if score < WEAK_PILLAR_THRESHOLD:
            display = _pillar_display_name(pillar_key)
            if score < 25.0:
                weak.append(
                    f"{display} score is critically low ({score:.0f}/100) -- needs immediate attention"
                )
            else:
                weak.append(
                    f"{display} score is below average ({score:.0f}/100)"
                )

    # 2. Engine-level weak areas (already guaranteed score-derived)
    for area in engine_weak_areas:
        area_stripped = area.strip()
        if area_stripped and area_stripped not in weak:
            weak.append(area_stripped)

    # 3. Top missing skills for the role
    for skill in missing_skills[:3]:
        hint = f"Missing critical skill for {target_role}: {skill}"
        if hint not in weak:
            weak.append(hint)

    return weak[:15]  # cap to avoid overwhelming the user


# ---------------------------------------------------------------------------
# Recommendations (high-level, Phase 12 will replace with rich dataset-backed)
# ---------------------------------------------------------------------------

def _generate_recommendations(
    pillar_scores: dict[str, float],
    missing_skills: list[str],
    target_role: str,
) -> list[str]:
    """
    Simple score-driven recommendations as placeholder until Phase 12.
    Each recommendation explains *what* to do without hard-coding specific
    skill names or scores.
    """
    recs: list[str] = []

    # Find the two weakest pillars
    sorted_pillars = sorted(pillar_scores.items(), key=lambda x: x[1])
    weakest_pillars = [k for k, s in sorted_pillars if s < 60.0][:2]

    for pillar in weakest_pillars:
        if pillar == "skill_readiness":
            recs.append(
                f"Focus on learning the core technical skills required for {target_role} "
                "to raise your Skill Readiness score."
            )
        elif pillar == "projects_experience":
            recs.append(
                f"Build or improve 1-2 end-to-end projects relevant to {target_role}, "
                "ideally with deployment and real-world data."
            )
        elif pillar == "role_alignment":
            recs.append(
                f"Your current skill set is not strongly aligned to {target_role}. "
                "Study the role's required technologies and add them to your profile."
            )
        elif pillar == "resume_quality":
            recs.append(
                "Improve your resume: add GitHub and LinkedIn links, use strong action "
                "verbs, quantify achievements with numbers, and ensure all key sections are present."
            )
        elif pillar == "certificate_quality":
            recs.append(
                f"Earn a recognized certification aligned to {target_role} from a "
                "credible provider (e.g., Google, AWS, Coursera, or edX)."
            )

    # Add top missing skills as a recommendation
    if missing_skills:
        skill_list = ", ".join(missing_skills[:3])
        recs.append(
            f"Priority skills to acquire for {target_role}: {skill_list}."
        )

    return recs[:5]


# ---------------------------------------------------------------------------
# Public orchestrator function
# ---------------------------------------------------------------------------

def orchestrate_prs(
    target_role: str,
    skill_readiness_score: float | None,
    projects_experience_score: float | None,
    role_alignment_score: float | None,
    resume_quality_score: float | None,
    certificate_quality_score: float | None,
    # Diagnostic inputs from individual engines
    engine_weak_areas: list[str] | None = None,
    missing_skills: list[str] | None = None,
) -> PRSResult:
    """
    Combine five pillar scores into a final PRS score and readiness level.

    Parameters
    ----------
    target_role : str
        The role the user is evaluating for.
    skill_readiness_score : float | None
        Phase 6 output (0-100).
    projects_experience_score : float | None
        Phase 7 output (0-100).
    role_alignment_score : float | None
        Phase 10 output (0-100).
    resume_quality_score : float | None
        Phase 9 output (0-100).
    certificate_quality_score : float | None
        Phase 8 output (0-100).
    engine_weak_areas : list[str] | None
        Pre-computed weak area strings from individual engines.
    missing_skills : list[str] | None
        Skills the user is missing for the role (from Phase 6).

    Returns
    -------
    PRSResult
        Complete PRS result with score, level, breakdown, and diagnostics.
    """
    warnings: list[str] = []
    engine_weak_areas = engine_weak_areas or []
    missing_skills    = missing_skills or []

    # ---- 1. Normalize all pillar scores ----
    raw = {
        "skill_readiness":     skill_readiness_score,
        "projects_experience": projects_experience_score,
        "role_alignment":      role_alignment_score,
        "resume_quality":      resume_quality_score,
        "certificate_quality": certificate_quality_score,
    }
    pillar_scores: dict[str, float] = {
        key: _safe_score(val, key, warnings)
        for key, val in raw.items()
    }

    # ---- 2. Apply PRS formula ----
    weighted_contributions: dict[str, float] = {
        key: pillar_scores[key] * weight
        for key, weight in PRS_WEIGHTS.items()
    }
    prs_score = sum(weighted_contributions.values())
    prs_score = max(0.0, min(100.0, prs_score))

    # ---- 3. Readiness level ----
    readiness_level = _assign_readiness_level(prs_score)

    # ---- 4. Weak areas (score-derived, no hard-coding) ----
    weak_areas = _synthesize_weak_areas(
        pillar_scores, engine_weak_areas, missing_skills, target_role
    )

    # ---- 5. Recommendations (Phase 12 placeholder) ----
    recommendations = _generate_recommendations(
        pillar_scores, missing_skills, target_role
    )

    return PRSResult(
        prs_score=round(prs_score, 2),
        readiness_level=readiness_level,
        pillar_scores=pillar_scores,
        weighted_contributions=weighted_contributions,
        weak_areas=weak_areas,
        missing_skills=missing_skills,
        recommendations=recommendations,
        warnings=warnings,
    )
