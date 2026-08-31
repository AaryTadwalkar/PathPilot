"""
app/services/prs/constants.py
==============================
Single source of truth for all PRS and Career Path shared constants.

Design:
  All threshold values, weights, and labels that cross module boundaries
  are defined here exactly once. Importing from this file prevents the
  BUG-013 pattern where two files define the same constant with different values.

Elements:
  PILLAR_WEIGHTS           dict  PRS formula weights (sum to 1.0)
  INDUSTRY_READY_THRESHOLD float Target score for a career path goal
  WEAK_PILLAR_THRESHOLD    float Orchestrator: flag pillar as weak in PRS output
  HINT_PILLAR_THRESHOLD    float Rec engine: show score hints when pillar < this
  STRONG_PILLAR_THRESHOLD  float Rec engine: deprioritise pillar when > this
  READINESS_LEVELS         list  PRS label thresholds (inclusive lower bound)
  GOAL_BUCKET_LABELS       list  Module 3 ETA week-range to label mapping

Used by:
  orchestrator.py, recommendation_engine.py, gap_engine.py,
  what_if_engine.py, milestone_engine.py, eta_engine.py
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# PRS pillar weights (spec-defined, must sum to 1.0)
# ---------------------------------------------------------------------------

PILLAR_WEIGHTS: dict[str, float] = {
    "skill_readiness":     0.30,
    "projects_experience": 0.25,
    "role_alignment":      0.20,
    "resume_quality":      0.15,
    "certificate_quality": 0.10,
}

assert abs(sum(PILLAR_WEIGHTS.values()) - 1.0) < 1e-9, "PILLAR_WEIGHTS must sum to 1.0"

# ---------------------------------------------------------------------------
# Score thresholds
# ---------------------------------------------------------------------------

# Module 3: default career path target (flat 70 per pillar, per design decision D2)
INDUSTRY_READY_THRESHOLD: float = 70.0

# Module 2 orchestrator: pillar below this is flagged as a weak area in PRS output
WEAK_PILLAR_THRESHOLD: float = 50.0

# Module 2 recommendation engine: pillar below this gets score hints in recommendations
# Slightly higher than WEAK_PILLAR_THRESHOLD to surface borderline pillars early
HINT_PILLAR_THRESHOLD: float = 55.0

# Module 2 recommendation engine: pillar above this is deprioritised in recommendations
STRONG_PILLAR_THRESHOLD: float = 75.0

# ---------------------------------------------------------------------------
# Readiness levels (spec-defined, inclusive lower bound)
# ---------------------------------------------------------------------------

READINESS_LEVELS: list[tuple[float, str]] = [
    (85.0, "Highly Placement Ready"),
    (70.0, "Industry Ready"),
    (55.0, "Developing Readiness"),
    (40.0, "Needs Improvement"),
    (0.0,  "Early Preparation Stage"),
]

# ---------------------------------------------------------------------------
# Module 3: goal bucket labels (inclusive upper-bound week thresholds)
# ---------------------------------------------------------------------------

GOAL_BUCKET_LABELS: list[tuple[int, str]] = [
    (2,  "Immediate"),
    (6,  "Short-Term"),
    (12, "Medium-Term"),
]
GOAL_BUCKET_DEFAULT: str = "Long-Term"
