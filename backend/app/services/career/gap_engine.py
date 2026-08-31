"""
app/services/career/gap_engine.py
===================================
Module 3 — M3-3: Gap Analysis Engine.

What this file does:
  Computes per-pillar gaps between a student's current PRS scores and the
  career path target (flat 70.0 per pillar). Returns a ranked list of
  pillars by priority so downstream engines know which gaps to address first.

Overall design:
  Pure deterministic math. No I/O, no DB calls, no imports from M2 engines.
  Reads only PRSResult (from orchestrator) and constants. Safe to call many
  times per request without side effects.

Elements:
  GapAnalysisResult  dataclass  Return type of compute_gap_analysis()
  compute_gap_analysis()        Main public function
  _priority_label()             Internal helper: maps a priority float to a label string

Final output:
  GapAnalysisResult with per-pillar gaps, weighted priorities, ordered pillar
  list (highest priority first), and total_gap scalar.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from app.services.prs.orchestrator import PRSResult
from app.services.prs.constants import (
    PILLAR_WEIGHTS,
    INDUSTRY_READY_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class GapAnalysisResult:
    """
    Output of compute_gap_analysis().

    Use:
      Consumed by MilestoneEngine to decide which pillar to attack first
      and how many milestones to allocate per pillar.

    Contains:
      gaps             per-pillar raw gap (target - current, floored at 0)
      priorities       per-pillar weighted gap (gap * pillar_weight)
      ordered_pillars  pillar names sorted by priority descending
      total_gap        sum of all raw gaps (overall effort indicator)
      target_prs       the target used (always INDUSTRY_READY_THRESHOLD by default)
      pillar_labels    human-readable priority label per pillar

    Technologies:
      Pure Python dataclass. No ORM, no JSON serialisation here — callers
      serialise to JSON when persisting to career_paths.gap_analysis.
    """
    gaps:            dict[str, float]         # pillar -> raw gap
    priorities:      dict[str, float]         # pillar -> weighted gap
    ordered_pillars: list[str]                # sorted by priority desc
    total_gap:       float
    target_prs:      float
    pillar_labels:   dict[str, str] = field(default_factory=dict)   # pillar -> "High/Medium/Low"
    pillar_scores:   dict[str, float] = field(default_factory=dict) # pillar -> actual current score (for UI)

    def to_dict(self) -> dict:
        """Serialise to plain dict for JSON storage in career_paths.gap_analysis."""
        return {
            "target_prs":      self.target_prs,
            "total_gap":       self.total_gap,
            "gaps":            self.gaps,
            "priorities":      self.priorities,
            "ordered_pillars": self.ordered_pillars,
            "pillar_labels":   self.pillar_labels,
            "pillar_scores":   self.pillar_scores,  # actual scores for ring chart UI
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _priority_label(priority: float) -> str:
    """
    Use:
      Map a numeric weighted-priority value to a human-readable urgency label.

    How it works:
      Thresholds chosen so that a pillar with weight 0.30 and a 20-point gap
      (0.30 * 20 = 6.0) is "High", and a pillar with weight 0.10 and a 10-point
      gap (0.10 * 10 = 1.0) is "Low".

    Concepts:
      The priority value is gap * pillar_weight. A higher-weight pillar with
      a smaller gap can outrank a lower-weight pillar with a larger gap.

    Used by: compute_gap_analysis() only.

    Output: "High" | "Medium" | "Low"
    """
    if priority >= 5.0:
        return "High"
    if priority >= 2.0:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_gap_analysis(
    prs_result: PRSResult,
    target_prs: float = INDUSTRY_READY_THRESHOLD,
) -> GapAnalysisResult:
    """
    Use:
      Compute per-pillar gaps between current PRS scores and target.
      Entry point for M3-3. Called by career_orchestrator before
      MilestoneEngine runs.

    How it works:
      For each pillar:
        gap[pillar]      = max(0, target_prs - current_score)
        priority[pillar] = gap[pillar] * PILLAR_WEIGHTS[pillar]
      Pillars are sorted by priority descending so the most impactful
      gap is always addressed first in the milestone roadmap.

    Concepts:
      Weighted gap prioritisation — a 20-point gap in skill_readiness
      (weight 0.30) ranks higher than a 20-point gap in certificate_quality
      (weight 0.10) even though the raw gaps are equal, because fixing
      skills moves the overall PRS score more.

    Imports used by: career_orchestrator.py (M3-8).

    Parameters:
      prs_result  PRSResult from orchestrate_prs() or reconstructed from DB
      target_prs  flat per-pillar target (default: INDUSTRY_READY_THRESHOLD = 70.0)

    Output:
      Before: raw PRSResult with pillar_scores
      After:  GapAnalysisResult with gaps, priorities, ordered_pillars, labels
    """
    gaps: dict[str, float] = {}
    priorities: dict[str, float] = {}

    for pillar, weight in PILLAR_WEIGHTS.items():
        current = prs_result.pillar_scores.get(pillar, 0.0)
        gap = max(0.0, target_prs - current)
        gaps[pillar]      = round(gap, 2)
        priorities[pillar] = round(gap * weight, 3)

    ordered = sorted(priorities, key=priorities.__getitem__, reverse=True)
    pillar_labels = {p: _priority_label(priorities[p]) for p in priorities}
    pillar_scores = {p: round(prs_result.pillar_scores.get(p, 0.0), 2) for p in PILLAR_WEIGHTS}

    return GapAnalysisResult(
        gaps=gaps,
        priorities=priorities,
        ordered_pillars=ordered,
        total_gap=round(sum(gaps.values()), 2),
        target_prs=target_prs,
        pillar_labels=pillar_labels,
        pillar_scores=pillar_scores,
    )
