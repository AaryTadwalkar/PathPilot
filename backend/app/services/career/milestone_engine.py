"""
app/services/career/milestone_engine.py
=========================================
Module 3 - M3-5: Milestone Engine.

What this file does:
  Generates a prioritised list of actionable milestones for a student's
  career path. Each milestone is a concrete action (learn a skill, build a
  project, earn a cert) with an estimated projected score delta and effort.

Overall design:
  - Reads missing skills from GapAnalysisResult + datasets
  - Reads candidate projects + certs from datasets
  - For each candidate: calls project_delta() to get real projected delta
  - Orders by ROI = delta / effort_hours (descending)
  - Prerequisite pass: skill milestones that a project depends on are sorted
    to appear before that project milestone
  - _to_prs_project() maps dataset field names to PRSProject field names
  - _skill_effort() looks up effort from milestone_effort_map.json

Elements:
  Milestone           dataclass  One actionable step with delta + effort
  MilestoneResult     dataclass  Return type: ordered list + stats
  generate_milestones()          Main public function
  _to_prs_project()              Field-name mapping helper (dataset -> PRSProject)
  _skill_effort()                Effort lookup from milestone_effort_map.json
  _cert_effort()                 Effort lookup for certifications
  _prerequisite_sort()           Topological reorder: skills before dependent projects

Final output:
  MilestoneResult with ordered milestones list ready for ETA engine input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.prs.input_builder  import PRSInput
from app.services.prs.orchestrator   import PRSResult
from app.services.prs.dataset_loader import PRSDatasets, load_prs_datasets
from app.services.career.gap_engine  import GapAnalysisResult
from app.services.career.what_if_engine import Mutation, project_delta


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Milestone:
    """
    Use:
      One actionable step in the student's career roadmap.

    Contains:
      id                  short unique string e.g. "SKILL_Python", "PROJ_Sentim"
      type                "skill" | "project" | "certification" | "resume"
      title               human-readable action title
      description         one-sentence explanation of why this matters
      projected_delta     expected PRS score improvement (from project_delta())
      effort_hours        estimated hours to complete this milestone
      roi                 projected_delta / effort_hours (ordering key)
      primary_skills      skills covered (for prerequisite pass)
      pillar              which PRS pillar this milestone primarily addresses
      priority_label      "High" | "Medium" | "Low" (from gap priority)
    """
    id:               str
    type:             str
    title:            str
    description:      str
    projected_delta:  float
    effort_hours:     int
    roi:              float
    primary_skills:   list[str] = field(default_factory=list)
    pillar:           str = ""
    priority_label:   str = "Medium"

    def to_dict(self) -> dict:
        """Serialise for JSON storage in career_paths.milestones."""
        return {
            "id":              self.id,
            "type":            self.type,
            "title":           self.title,
            "description":     self.description,
            "projected_delta": self.projected_delta,
            "effort_hours":    self.effort_hours,
            "roi":             self.roi,
            "primary_skills":  self.primary_skills,
            "pillar":          self.pillar,
            "priority_label":  self.priority_label,
        }


@dataclass
class MilestoneResult:
    """
    Use:
      Return type of generate_milestones(). Consumed by ETA Engine (M3-6).

    Contains:
      milestones        ordered list of Milestone objects (ROI desc, prereqs respected)
      total_delta       sum of all projected_delta values
      total_hours       sum of all effort_hours values
      skipped_count     how many candidates were skipped by dedup guard
    """
    milestones:    list[Milestone]
    total_delta:   float
    total_hours:   int
    skipped_count: int

    def to_dict_list(self) -> list[dict]:
        return [m.to_dict() for m in self.milestones]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_effort_map(dataset_dir: Path) -> dict:
    """
    Use:
      Load milestone_effort_map.json from the datasets directory.

    How it works:
      Simple JSON read. Not cached — called once per generate_milestones() call.
      The file is small (< 1KB) so no caching needed.

    Used by: generate_milestones() only.

    Output: parsed dict with keys skill_effort, project_effort, cert_effort, defaults
    """
    path = dataset_dir / "milestone_effort_map.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _to_prs_project(dataset_entry: dict) -> dict:
    """
    Use:
      Translate a projects_dataset.json entry into the dict shape that
      project_delta(Mutation(type='add_project', payload=...)) expects.

    How it works:
      Direct field rename mapping. No computation.
        project_name   -> name          (RENAMED)
        description    -> description   (same)
        primary_skills -> skills_used   (RENAMED)
        domain / role_alignment[0] -> domain

    Concepts:
      This is the field-mapping regression fix from Review Round 4 Finding 2.
      Without this helper, PRSProject(**dataset_entry) throws TypeError.

    Used by: _generate_project_milestones() inside generate_milestones().

    Output:
      Before: {'project_name': 'X', 'primary_skills': [...], ...}
      After:  {'name': 'X', 'skills_used': [...], ...}
    """
    domain = "General"
    if dataset_entry.get("role_alignment"):
        domain = dataset_entry["role_alignment"][0]
    return {
        "name":        dataset_entry["project_name"],
        "description": dataset_entry.get("description", ""),
        "skills_used": dataset_entry.get("primary_skills", []),
        "domain":      domain,
    }


def _skill_effort(skill: dict, effort_map: dict) -> int:
    """
    Use:
      Look up estimated learning hours for a skill from the effort map.

    How it works:
      Constructs key = role_criticality + "_" + foundational_type.
      Falls back to effort_map['defaults']['skill_effort_hours'] if key missing.
      All 4 real combinations are present in milestone_effort_map.json so the
      fallback should never trigger in normal operation.

    Concepts:
      The effort_map key space covers:
        critical_foundational (40h), critical_specialized (60h),
        important_foundational (20h), important_specialized (35h),
        nice_to_have_foundational (10h), nice_to_have_specialized (15h)

    Used by: _generate_skill_milestones() inside generate_milestones().

    Output: int hours (e.g. 40)
    """
    crit = skill.get("role_criticality", "important")
    tier = skill.get("foundational_type", "foundational")
    key  = f"{crit}_{tier}"
    return effort_map["skill_effort"].get(key, effort_map["defaults"]["skill_effort_hours"])


def _cert_effort(cert: dict, effort_map: dict) -> int:
    """
    Use:
      Look up estimated study hours for a certification.

    How it works:
      Reads certificate_level from the cert dataset entry, matches against
      effort_map['cert_effort']. Falls back to defaults['cert_effort_hours'].

    Used by: _generate_cert_milestones() inside generate_milestones().

    Output: int hours (e.g. 40 for Intermediate)
    """
    level = cert.get("certificate_level", "Intermediate")
    return effort_map["cert_effort"].get(level, effort_map["defaults"]["cert_effort_hours"])


def _experience_factor(skill_name: str, skill_category: str | None, prs_input: PRSInput) -> float:
    """
    Use:
      Reduce effort hours when the student already has overlapping skills in
      the same category as the milestone skill.

    How it works:
      Checks prs_input.skills for any existing skill whose category matches
      skill_category (case-insensitive). If at least one overlap found,
      returns 0.6 (40% discount). Otherwise returns 1.0 (no discount).

      Special cases:
        - If skill_category is None, compares skill name substrings for common
          framework families (e.g. Flask → FastAPI discount).
        - Discount is capped at 0.6 — never below that regardless of overlap count.

    Concepts:
      Learning a related technology costs less when you already know the ecosystem.
      Example: Flask + Python → FastAPI costs 40% less than starting cold.

    Used by: generate_milestones() for skill effort only (not projects/certs).

    Output: float factor in [0.6, 1.0]. Multiply base hours by this factor.
    """
    if not prs_input.skills:
        return 1.0

    target_cat = (skill_category or "").strip().lower()
    if target_cat:
        for existing in prs_input.skills:
            existing_cat = (existing.category or "").strip().lower()
            if existing_cat and existing_cat == target_cat:
                return 0.6  # 40% discount — familiar ecosystem

    # Fallback: common framework family keyword overlap
    FRAMEWORK_FAMILIES = [
        {"fastapi", "flask", "django", "starlette"},
        {"react", "next.js", "vue", "angular", "svelte"},
        {"node.js", "express.js", "nestjs"},
        {"tensorflow", "pytorch", "keras", "jax"},
        {"aws", "azure", "google cloud", "gcp"},
        {"docker", "kubernetes", "helm"},
        {"postgresql", "mysql", "sqlite", "mongodb"},
    ]
    skill_lower = skill_name.lower()
    user_skill_lower = {s.skill.lower() for s in prs_input.skills}

    for family in FRAMEWORK_FAMILIES:
        if skill_lower in family:
            if family & user_skill_lower:  # user already knows something in this family
                return 0.6

    return 1.0


def _prerequisite_sort(milestones: list[Milestone]) -> list[Milestone]:
    """
    Use:
      Ensure skill milestones appear before project milestones that depend
      on those skills. Preserves ROI order within each group.

    How it works:
      Two-pass:
        Pass 1: collect all skills covered by skill milestones.
        Pass 2: for each project milestone, if any of its primary_skills
                matches a skill milestone that comes after it in the list,
                move that skill milestone to just before the project.
      This is a lightweight topological reorder, not a full DAG sort —
      sufficient for the shallow dependency depth of career milestones.

    Concepts:
      Topological ordering applied to a flat list using a greedy swap.
      O(n^2) but n is always small (< 20 milestones per path).

    Used by: generate_milestones() before returning MilestoneResult.

    Output: reordered milestones list with skills before dependent projects.
    """
    skill_ms  = [m for m in milestones if m.type == "skill"]
    project_ms = [m for m in milestones if m.type == "project"]
    other_ms   = [m for m in milestones if m.type not in ("skill", "project")]

    covered_skills = {s for m in skill_ms for s in m.primary_skills}

    # Reorder: for each project, check if any of its primary_skills appear in
    # skill milestones that are positioned after it. If so, move those skills up.
    result: list[Milestone] = []
    remaining_skills = list(skill_ms)

    for proj in project_ms:
        needed = [s for s in proj.primary_skills if s in covered_skills]
        # Pull any needed skill milestones that haven't been added yet
        still_needed = [m for m in remaining_skills if any(s in m.primary_skills for s in needed)]
        for sm in still_needed:
            if sm not in result:
                result.append(sm)
                remaining_skills.remove(sm)
        result.append(proj)

    # Any remaining skill milestones not pulled in by a project
    result.extend(remaining_skills)
    result.extend(other_ms)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_milestones(
    prs_input:    PRSInput,
    baseline_prs: PRSResult,
    gap_result:   GapAnalysisResult,
    datasets:     PRSDatasets,
    max_milestones: int = 10,
) -> MilestoneResult:
    """
    Use:
      Generate a prioritised, ordered list of actionable career milestones.
      Called by career_orchestrator (M3-8) after compute_gap_analysis().

    How it works:
      1. Load effort map from milestone_effort_map.json
      2. Load role skill mapping to find missing skills for the target role
      3. For each missing skill: call project_delta() to get real projected delta
         Score by ROI = delta / effort_hours
      4. For each candidate project in datasets: call project_delta(), dedup guard
      5. For each candidate cert in datasets: call project_delta(), dedup guard
      6. Merge all milestones, sort by ROI descending
      7. Apply _prerequisite_sort() to ensure skill milestones come before
         project milestones that depend on them
      8. Truncate to max_milestones

    Concepts:
      ROI-first ordering: the highest value-per-hour action always comes first.
      Dedup guard: project_delta() returns skipped=True for items already present;
      these are counted but not added to the milestone list.
      All delta computation goes through the SAME project_delta() function as
      the what-if engine — one delta path, no ad-hoc math.

    Imports used by: career_orchestrator.py (M3-8).

    Parameters:
      prs_input      PRSInput  current student state
      baseline_prs   PRSResult computed PRS to diff against
      gap_result     GapAnalysisResult from compute_gap_analysis()
      datasets       PRSDatasets loaded cache
      max_milestones int max milestones to return (default 10)

    Output:
      Before: raw gap analysis + datasets
      After:  MilestoneResult with ordered Milestone list, total delta + hours
    """
    effort_map = _load_effort_map(datasets.dataset_dir)
    milestones: list[Milestone] = []
    skipped = 0

    # ---- 1. Skill milestones ------------------------------------------------
    role_entry = next(
        (r for r in datasets.role_skill_mapping if r["role"] == prs_input.target_role),
        None,
    )
    possessed_skills = {s.skill.lower() for s in prs_input.skills}
    # Also build an alias expansion set so e.g. "ML" covers "Machine Learning"
    _SKILL_ALIASES: dict[str, str] = {
        "ml": "machine learning",
        "dl": "deep learning",
        "ai": "artificial intelligence",
        "nlp": "natural language processing",
        "cv": "computer vision",
        "rl": "reinforcement learning",
        "mlops": "ml operations",
        "genai": "generative ai",
    }
    possessed_expanded: set[str] = set(possessed_skills)
    for s in possessed_skills:
        possessed_expanded.add(_SKILL_ALIASES.get(s, s))
        # Reverse: if user has "machine learning" add alias "ml"
        for abbrev, full in _SKILL_ALIASES.items():
            if s == full:
                possessed_expanded.add(abbrev)

    def _user_has_skill(sname: str) -> bool:
        """True if user already has this skill (exact or alias match)."""
        n = sname.lower()
        return n in possessed_expanded or _SKILL_ALIASES.get(n, n) in possessed_expanded

    if role_entry:
        for skill in role_entry["skills"]:
            sname = skill["skill_name"]
            if _user_has_skill(sname):
                skipped += 1
                continue

            delta = project_delta(
                prs_input, baseline_prs,
                Mutation(type="add_skill", payload=sname),
                datasets,
            )
            if delta.skipped or delta.overall_delta <= 0:
                skipped += 1
                continue

            base_hours = _skill_effort(skill, effort_map)
            factor    = _experience_factor(sname, skill.get("category"), prs_input)
            hours     = max(1, round(base_hours * factor))
            roi   = round(delta.overall_delta / max(hours, 1), 4)
            crit  = skill.get("role_criticality", "important")
            label = gap_result.pillar_labels.get("skill_readiness", "Medium")

            milestones.append(Milestone(
                id=f"SKILL_{sname[:10].upper().replace(' ', '_')}",
                type="skill",
                title=f"Learn {sname}",
                description=f"{sname} is a {crit} skill for {prs_input.target_role}.",
                projected_delta=delta.overall_delta,
                effort_hours=hours,
                roi=roi,
                primary_skills=[sname],
                pillar="skill_readiness",
                priority_label=label,
            ))

    # ---- 2. Project milestones ----------------------------------------------
    possessed_projects = {p.name.lower() for p in prs_input.projects}

    for proj_entry in datasets.projects_dataset:
        # Only suggest projects aligned with the target role
        role_align = proj_entry.get("role_alignment", [])
        if prs_input.target_role not in role_align:
            continue

        proj_dict = _to_prs_project(proj_entry)
        if proj_dict["name"].lower() in possessed_projects:
            skipped += 1
            continue

        delta = project_delta(
            prs_input, baseline_prs,
            Mutation(type="add_project", payload=proj_dict),
            datasets,
        )
        if delta.skipped or delta.overall_delta <= 0:
            skipped += 1
            continue

        difficulty = proj_entry.get("difficulty_level", "Intermediate")
        base_proj_hours = effort_map["project_effort"].get(
            difficulty, effort_map["defaults"]["project_effort_hours"]
        )
        # Apply experience factor: if user already has most primary skills, reduce effort
        proj_primary = proj_entry.get("primary_skills", [])
        overlap = sum(1 for s in proj_primary if s.lower() in possessed_skills)
        proj_factor = 0.6 if overlap >= max(1, len(proj_primary) // 2) else 1.0
        hours = max(1, round(base_proj_hours * proj_factor))
        roi = round(delta.overall_delta / max(hours, 1), 4)

        milestones.append(Milestone(
            id=f"PROJ_{proj_entry['project_name'][:10].upper().replace(' ', '_')}",
            type="project",
            title=f"Build: {proj_entry['project_name']}",
            description=proj_entry.get("description", "")[:120],
            projected_delta=delta.overall_delta,
            effort_hours=hours,
            roi=roi,
            primary_skills=proj_entry.get("primary_skills", []),
            pillar="projects_experience",
            priority_label=gap_result.pillar_labels.get("projects_experience", "Medium"),
        ))

    # ---- 3. Certification milestones ----------------------------------------
    possessed_certs = {c.lower() for c in prs_input.certifications}

    for cert_entry in datasets.certificates_dataset:
        role_align = cert_entry.get("role_alignment", [])
        if prs_input.target_role not in role_align:
            continue

        cname = cert_entry.get("certificate_name", "")
        if cname.lower() in possessed_certs:
            skipped += 1
            continue

        delta = project_delta(
            prs_input, baseline_prs,
            Mutation(type="add_certification", payload=cname),
            datasets,
        )
        if delta.skipped or delta.overall_delta <= 0:
            skipped += 1
            continue

        hours = _cert_effort(cert_entry, effort_map)
        roi   = round(delta.overall_delta / max(hours, 1), 4)

        milestones.append(Milestone(
            id=f"CERT_{cname[:10].upper().replace(' ', '_')}",
            type="certification",
            title=f"Earn: {cname}",
            description=f"Offered by {cert_entry.get('provider', 'Unknown')}. Level: {cert_entry.get('certificate_level', 'Intermediate')}.",
            projected_delta=delta.overall_delta,
            effort_hours=hours,
            roi=roi,
            primary_skills=cert_entry.get("skills_covered", []),
            pillar="certificate_quality",
            priority_label=gap_result.pillar_labels.get("certificate_quality", "Medium"),
        ))

    # ---- 4. Sort by ROI descending ------------------------------------------
    milestones.sort(key=lambda m: -m.roi)

    # ---- 5. Prerequisite pass -----------------------------------------------
    milestones = _prerequisite_sort(milestones)

    # ---- 6. Truncate --------------------------------------------------------
    milestones = milestones[:max_milestones]

    return MilestoneResult(
        milestones=milestones,
        total_delta=round(sum(m.projected_delta for m in milestones), 2),
        total_hours=sum(m.effort_hours for m in milestones),
        skipped_count=skipped,
    )
