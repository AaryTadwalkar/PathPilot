"""
app/services/career/eta_engine.py
====================================
Module 3 - M3-6: ETA (Estimated Time to Achievement) Engine.

What this file does:
  Converts an ordered list of Milestones into a week-by-week study plan
  and computes the total ETA (weeks + hours) to reach the target PRS.

Overall design:
  Pure math — no DB, no engine calls, no I/O.
  Takes MilestoneResult + study_hours_per_week as inputs.
  Assigns milestones to weeks based on effort, then labels each week
  with a goal bucket (Immediate / Short-Term / Medium-Term / Long-Term).

Elements:
  WeeklyEntry      dataclass  One week in the plan
  ETAResult        dataclass  Return type of compute_eta()
  compute_eta()               Main public function
  _assign_bucket()            Maps week number -> goal bucket label

Final output:
  ETAResult with eta_weeks, eta_hours, weekly_plan list, projected_final_prs
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.services.career.milestone_engine import Milestone, MilestoneResult
from app.services.prs.constants import GOAL_BUCKET_LABELS, GOAL_BUCKET_DEFAULT


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class WeeklyEntry:
    """
    Use:
      One row in the week-by-week study plan shown to the student.

    Contains:
      week_number    1-indexed week
      goal_bucket    "Immediate" | "Short-Term" | "Medium-Term" | "Long-Term"
      milestones     list of milestone IDs scheduled this week
      hours_this_week total study hours allocated to this week
    """
    week_number:     int
    goal_bucket:     str
    milestones:      list[str]    # milestone IDs
    hours_this_week: int

    def to_dict(self) -> dict:
        return {
            "week_number":     self.week_number,
            "goal_bucket":     self.goal_bucket,
            "milestones":      self.milestones,
            "hours_this_week": self.hours_this_week,
        }


@dataclass
class ETAResult:
    """
    Use:
      Return type of compute_eta(). Consumed by career_orchestrator (M3-8)
      and stored in career_paths.eta_weeks / career_paths.weekly_plan.

    Contains:
      eta_weeks             total weeks to complete all milestones
      eta_hours             total study hours
      projected_final_prs   baseline_prs + sum of all milestone deltas (capped 100)
      weekly_plan           list of WeeklyEntry objects (week-by-week schedule)
      study_hours_per_week  the input hours/week used for this calculation
    """
    eta_weeks:            int
    eta_hours:            int
    projected_final_prs:  float
    weekly_plan:          list[WeeklyEntry]
    study_hours_per_week: int

    def to_dict(self) -> dict:
        return {
            "eta_weeks":            self.eta_weeks,
            "eta_hours":            self.eta_hours,
            "projected_final_prs":  self.projected_final_prs,
            "study_hours_per_week": self.study_hours_per_week,
            "weekly_plan":          [w.to_dict() for w in self.weekly_plan],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assign_bucket(week_number: int) -> str:
    """
    Use:
      Map a 1-indexed week number to a goal bucket label string.

    How it works:
      Iterates GOAL_BUCKET_LABELS (a list of (threshold_week, label) tuples
      from constants.py). Returns the label for the first threshold >= week.
      Falls back to GOAL_BUCKET_DEFAULT ("Long-Term") if no threshold matches.

    Concepts:
      GOAL_BUCKET_LABELS from constants.py:
        [(2, "Immediate"), (6, "Short-Term"), (12, "Medium-Term")]
      Week 1-2  -> Immediate
      Week 3-6  -> Short-Term
      Week 7-12 -> Medium-Term
      Week 13+  -> Long-Term

    Used by: compute_eta() only.

    Output: "Immediate" | "Short-Term" | "Medium-Term" | "Long-Term"
    """
    for threshold, label in GOAL_BUCKET_LABELS:
        if week_number <= threshold:
            return label
    return GOAL_BUCKET_DEFAULT


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_eta(
    milestone_result:     MilestoneResult,
    baseline_prs_score:   float,
    study_hours_per_week: int = 10,
) -> ETAResult:
    """
    Use:
      Compute week-by-week study plan and overall ETA from an ordered
      milestone list. Called by career_orchestrator (M3-8) after
      generate_milestones().

    How it works:
      1. Accumulate milestones into bins: fill a bin until the effort hours
         would exceed study_hours_per_week, then start a new bin.
         Milestones larger than one week's budget get their own bin.
      2. Each WeeklyEntry.week_number is the CALENDAR week that bin STARTS on.
         A bin with 20h effort at 10h/week spans 2 calendar weeks, so the
         next bin starts at calendar week 3 (not week 2).
         This is computed as: calendar_week += ceil(bin_hours / capacity)
      3. Assign a goal_bucket label using the calendar start week.
      4. eta_weeks = ceil(total_hours / capacity) — total calendar weeks.

    Concepts:
      Bin-packing (greedy first-fit) with correct calendar week tracking.
      Previously used a bin counter which labelled all bins 1,2,3… regardless
      of how many calendar weeks each bin actually occupies.

    Imports used by: career_orchestrator.py (M3-8).

    Parameters:
      milestone_result      MilestoneResult from generate_milestones()
      baseline_prs_score    float  current PRS (before any milestones)
      study_hours_per_week  int    hours per week the student plans to study

    Output:
      Before: unscheduled milestone list
      After:  ETAResult with weekly_plan (calendar-week-labelled), eta_weeks,
              eta_hours, projected PRS
    """
    if not milestone_result.milestones:
        return ETAResult(
            eta_weeks=0,
            eta_hours=0,
            projected_final_prs=round(baseline_prs_score, 2),
            weekly_plan=[],
            study_hours_per_week=study_hours_per_week,
        )

    weekly_plan:              list[WeeklyEntry] = []
    current_bin_milestones:   list[str] = []
    current_bin_hours:        int = 0
    calendar_week:            int = 1   # calendar week this bin STARTS on
    total_hours:              int = 0
    hours_cap:                int = max(study_hours_per_week, 1)

    for ms in milestone_result.milestones:
        total_hours += ms.effort_hours

        if current_bin_hours + ms.effort_hours > hours_cap and current_bin_milestones:
            # Close the current bin and emit a WeeklyEntry
            weekly_plan.append(WeeklyEntry(
                week_number=calendar_week,
                goal_bucket=_assign_bucket(calendar_week),
                milestones=current_bin_milestones,
                hours_this_week=current_bin_hours,
            ))
            # Advance calendar_week by the number of calendar weeks this bin spans
            calendar_week += math.ceil(current_bin_hours / hours_cap)
            current_bin_milestones = []
            current_bin_hours = 0

        current_bin_milestones.append(ms.id)
        current_bin_hours += ms.effort_hours

    # Flush the last bin
    if current_bin_milestones:
        weekly_plan.append(WeeklyEntry(
            week_number=calendar_week,
            goal_bucket=_assign_bucket(calendar_week),
            milestones=current_bin_milestones,
            hours_this_week=current_bin_hours,
        ))

    # eta_weeks = total effort hours / weekly capacity (ceiling)
    eta_weeks = math.ceil(total_hours / hours_cap) if total_hours > 0 else 0
    projected = round(min(100.0, baseline_prs_score + milestone_result.total_delta), 2)

    return ETAResult(
        eta_weeks=eta_weeks,
        eta_hours=total_hours,
        projected_final_prs=projected,
        weekly_plan=weekly_plan,
        study_hours_per_week=study_hours_per_week,
    )
