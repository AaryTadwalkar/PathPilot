"""
Phase 12 -- Recommendation Engine
====================================
Generates actionable, explainable, gap-closing recommendations for a
user based on the complete PRS evaluation result.

Five recommendation categories (spec-defined):
    1. Skills        -- critical/important missing skills for the role
    2. Courses       -- from courses_dataset, matched to skill gaps + role
    3. Certifications -- from certificates_dataset, not already owned
    4. Projects      -- from projects_dataset, targeting deployment/portfolio gaps
    5. Resume        -- specific resume improvements when resume pillar is weak

UI limits (spec-defined):
    Top 3-5 skills
    Top 3 courses
    Top 3 certifications
    Top 3 projects

Every recommendation includes a `why_recommended` explanation derived
from the actual user gaps -- no hard-coded strings.

Pipeline (spec-defined):
    PRS Result
        -> Find Weak Pillars
        -> Find Critical Missing Skills
        -> Find Partial Skills
        -> Find Project / Deployment Gaps
        -> Find Certificate Gaps
        -> Find Resume Issues
        -> Semantic Match Recommendation Datasets
        -> Apply Recommendation Weights
        -> Remove Completed / Duplicate Items
        -> Rank by Expected PRS Impact
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.prs.dataset_loader import PRSDatasets
from app.services.prs.input_builder import PRSInput
from app.services.prs.orchestrator import PRSResult, PRS_WEIGHTS
from app.services.prs.constants import (
    WEAK_PILLAR_THRESHOLD,
    HINT_PILLAR_THRESHOLD,
    STRONG_PILLAR_THRESHOLD,
    PILLAR_WEIGHTS,
)

# ---------------------------------------------------------------------------
# Pillar weakness thresholds  (single source: constants.py)
# ---------------------------------------------------------------------------
# WEAK_PILLAR_THRESHOLD  = 50.0  (pillar flagged as weak in PRS result)
# HINT_PILLAR_THRESHOLD  = 55.0  (pillar gets score hint in recommendations)
# STRONG_PILLAR_THRESHOLD = 75.0 (pillar deprioritized in recommendations)

# Priority labels
PRIORITY_HIGH   = "High"
PRIORITY_MEDIUM = "Medium"
PRIORITY_LOW    = "Low"

# Skill criticality -> recommendation priority mapping
CRITICALITY_PRIORITY: dict[str, str] = {
    "critical":   PRIORITY_HIGH,
    "important":  PRIORITY_MEDIUM,
    "high":       PRIORITY_MEDIUM,
    "medium":     PRIORITY_LOW,
    "low":        PRIORITY_LOW,
}

# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    type: str                        # skill | course | certification | project | resume
    title: str
    why_recommended: str
    skills_addressed: list[str]
    priority: str                    # High | Medium | Low
    url: str | None = None
    provider: str | None = None
    difficulty: str | None = None
    expected_outcomes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type":             self.type,
            "title":            self.title,
            "why_recommended":  self.why_recommended,
            "skills_addressed": self.skills_addressed,
            "priority":         self.priority,
        }
        if self.url:
            d["url"] = self.url
        if self.provider:
            d["provider"] = self.provider
        if self.difficulty:
            d["difficulty"] = self.difficulty
        if self.expected_outcomes:
            d["expected_outcomes"] = self.expected_outcomes
        return d


@dataclass
class RecommendationResult:
    skills: list[Recommendation]
    courses: list[Recommendation]
    certifications: list[Recommendation]
    projects: list[Recommendation]
    resume_tips: list[Recommendation]
    summary: str                     # one-line human-readable diagnosis

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary":        self.summary,
            "skills":         [r.to_dict() for r in self.skills],
            "courses":        [r.to_dict() for r in self.courses],
            "certifications": [r.to_dict() for r in self.certifications],
            "projects":       [r.to_dict() for r in self.projects],
            "resume_tips":    [r.to_dict() for r in self.resume_tips],
        }

    def flat_list(self) -> list[dict[str, Any]]:
        """Returns a single flat ranked list merging all categories."""
        all_recs = (
            self.skills
            + self.courses
            + self.certifications
            + self.projects
            + self.resume_tips
        )
        priority_order = {PRIORITY_HIGH: 0, PRIORITY_MEDIUM: 1, PRIORITY_LOW: 2}
        return [
            r.to_dict()
            for r in sorted(all_recs, key=lambda r: priority_order.get(r.priority, 3))
        ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    return text.strip().lower()


def _user_skill_norms(prs_input: PRSInput) -> set[str]:
    return {_norm(s.skill) for s in prs_input.skills}


def _user_cert_norms(prs_input: PRSInput) -> set[str]:
    return {_norm(c) for c in prs_input.certifications}


def _has_deployment_gap(prs_result: PRSResult) -> bool:
    """True if the projects/experience pillar is weak."""
    return prs_result.pillar_scores.get("projects_experience", 100.0) < HINT_PILLAR_THRESHOLD


def _weak_pillars(prs_result: PRSResult) -> list[str]:
    return [k for k, v in prs_result.pillar_scores.items() if v < HINT_PILLAR_THRESHOLD]


def _skill_priority(skill_name: str, role_skills: list[dict[str, Any]]) -> str:
    for s in role_skills:
        if _norm(s.get("skill_name", "")) == _norm(skill_name):
            return CRITICALITY_PRIORITY.get(s.get("role_criticality", "medium"), PRIORITY_MEDIUM)
    return PRIORITY_MEDIUM


def _skills_overlap(item_skills: list[str], target_skills: list[str]) -> int:
    """Count how many item skills overlap with target skills (case-insensitive)."""
    item_norm  = {_norm(s) for s in item_skills}
    target_norm = {_norm(s) for s in target_skills}
    return len(item_norm & target_norm)


def _relevance_score(item_role_alignment: list[str], target_role: str) -> float:
    """
    1.0 if exact role match, 0.5 if partial match, 0.0 otherwise.
    """
    target_norm = _norm(target_role)
    for r in item_role_alignment:
        if _norm(r) == target_norm:
            return 1.0
    for r in item_role_alignment:
        if target_norm in _norm(r) or _norm(r) in target_norm:
            return 0.5
    return 0.0


def _user_experience_level(prs_input: PRSInput) -> str:
    """
    Infer the user’s experience tier from assessment Q4 answer so that
    course difficulty can be matched to the user’s level.

    Mapping:
        2_plus_years / 1_2_years  → "Advanced"
        6_12_months               → "Intermediate"
        less_6_months / none      → "Beginner"

    Used by _recommend_courses() to add a difficulty-level match bonus.
    Imported nowhere else — internal to this module.

    Returns one of: "Beginner", "Intermediate", "Advanced".
    """
    duration = prs_input.assessment_answers.get("relevant_experience_duration", "none")
    if duration in ("2_plus_years", "1_2_years"):
        return "Advanced"
    if duration == "6_12_months":
        return "Intermediate"
    return "Beginner"


def _pillar_impact_hint(prs_result: PRSResult, pillar_key: str) -> str:
    """
    Return a short parenthetical string describing how weak the given pillar
    is, so recommendation ‘why’ strings can include real score context.

    Example output: " (your Skill Readiness is 38/100)"

    Returns empty string when the pillar is above the weak threshold so the
    hint is only surfaced when it adds real information.
    """
    score = prs_result.pillar_scores.get(pillar_key, 100.0)
    if score >= STRONG_PILLAR_THRESHOLD:
        return ""
    display = {
        "skill_readiness":     "Skill Readiness",
        "projects_experience": "Projects & Experience",
        "role_alignment":      "Role Alignment",
        "resume_quality":      "Resume Quality",
        "certificate_quality": "Certificate Quality",
    }.get(pillar_key, pillar_key.replace("_", " ").title())
    return f" (your {display} score is {score:.0f}/100)"


# ---------------------------------------------------------------------------
# 1. Skill Recommendations
# ---------------------------------------------------------------------------

def _recommend_skills(
    prs_input: PRSInput,
    prs_result: PRSResult,
    datasets: PRSDatasets,
    limit: int = 5,
) -> list[Recommendation]:
    """
    Recommend the top missing role skills, ordered by:
      critical > important > high demand > foundational_type
    """
    role_entry = next(
        (e for e in datasets.role_skill_mapping if e.get("role") == prs_input.target_role),
        None,
    )
    if not role_entry:
        return []

    user_norms = _user_skill_norms(prs_input)
    missing_skills = [
        s for s in role_entry.get("skills", [])
        if _norm(s["skill_name"]) not in user_norms
    ]

    # Sort by criticality desc, then foundational first
    criticality_order = {"critical": 0, "important": 1, "high": 1, "medium": 2, "low": 3}
    foundational_order = {"foundational": 0, "specialized": 1, "supporting": 2, "advanced_bonus": 3}

    missing_skills.sort(key=lambda s: (
        criticality_order.get(s.get("role_criticality", "medium"), 2),
        foundational_order.get(s.get("foundational_type", "specialized"), 1),
    ))

    recs: list[Recommendation] = []
    for skill in missing_skills[:limit]:
        name = skill["skill_name"]
        criticality = skill.get("role_criticality", "medium")
        demand = skill.get("industry_demand", "medium")
        priority = CRITICALITY_PRIORITY.get(criticality, PRIORITY_MEDIUM)
        hint = _pillar_impact_hint(prs_result, "skill_readiness")

        why = (
            f"'{name}' is a {criticality} skill for {prs_input.target_role} "
            f"with {demand} industry demand. Adding it will directly improve "
            f"your Skill Readiness and Role Alignment scores{hint}."
        )

        recs.append(Recommendation(
            type="skill",
            title=name,
            why_recommended=why,
            skills_addressed=[name],
            priority=priority,
        ))

    return recs


# ---------------------------------------------------------------------------
# 2. Course Recommendations
# ---------------------------------------------------------------------------

def _recommend_courses(
    prs_input: PRSInput,
    prs_result: PRSResult,
    datasets: PRSDatasets,
    limit: int = 3,
) -> list[Recommendation]:
    """
    Score each course by:
      role_alignment x 0.45 + missing_skill_overlap x 0.45 + level_match x 0.10
    Filter out courses whose skills_covered are already fully owned.
    Deduplicate by course_name.

    level_match bonus: 0.20 when the course difficulty matches the user’s
    inferred experience level (Beginner/Intermediate/Advanced from Q4).
    This surfaces the right course at the right level instead of always
    recommending intermediate content to a beginner.
    """
    if not datasets.courses_dataset:
        return []

    user_norms = _user_skill_norms(prs_input)
    missing_skills = prs_result.missing_skills  # from skill engine
    user_level = _user_experience_level(prs_input)  # Beginner / Intermediate / Advanced
    hint = _pillar_impact_hint(prs_result, "skill_readiness")

    scored: list[tuple[float, dict[str, Any]]] = []
    for course in datasets.courses_dataset:
        course_skills = course.get("skills_covered", [])
        role_align    = _relevance_score(course.get("role_alignment", []), prs_input.target_role)

        # Skip courses where the user already has all covered skills
        new_skills = [s for s in course_skills if _norm(s) not in user_norms]
        if not new_skills:
            continue

        # Overlap with missing skills
        if missing_skills:
            overlap = _skills_overlap(new_skills, missing_skills)
            overlap_score = overlap / len(missing_skills)
        else:
            overlap_score = 0.3  # neutral if no missing skills detected

        # Level match bonus: 0.20 when difficulty matches inferred user level
        course_level = (course.get("difficulty_level") or "").strip()
        level_bonus = 0.20 if course_level == user_level else 0.0

        total_score = (
            (role_align * 0.45)
            + (min(1.0, overlap_score) * 0.45)
            + level_bonus
        )
        scored.append((total_score, course))

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)

    recs: list[Recommendation] = []
    seen_names: set[str] = set()
    for score, course in scored[:limit * 2]:
        name = course["course_name"]
        if _norm(name) in seen_names:
            continue
        seen_names.add(_norm(name))

        course_skills   = course.get("skills_covered", [])
        new_skills      = [s for s in course_skills if _norm(s) not in user_norms]
        overlap_skills  = [s for s in new_skills if _norm(s) in {_norm(m) for m in missing_skills}]
        priority        = PRIORITY_HIGH if score >= 0.6 else PRIORITY_MEDIUM if score >= 0.3 else PRIORITY_LOW
        course_level    = (course.get("difficulty_level") or "").strip()
        level_tag       = f" ({course_level} level, matches your experience)" if course_level == user_level else ""

        if overlap_skills:
            why = (
                f"This course covers {', '.join(overlap_skills[:3])} "
                f"which {'is' if len(overlap_skills) == 1 else 'are'} currently missing from "
                f"your {prs_input.target_role} profile{hint}{level_tag}."
            )
        else:
            why = (
                f"This course is aligned to {prs_input.target_role} and teaches "
                f"{', '.join(new_skills[:3])} which are not yet in your profile{level_tag}."
            )

        recs.append(Recommendation(
            type="course",
            title=name,
            why_recommended=why,
            skills_addressed=new_skills[:5],
            priority=priority,
            url=course.get("course_url"),
            provider=course.get("provider"),
            difficulty=course.get("difficulty_level"),
        ))
        if len(recs) >= limit:
            break

    return recs


# ---------------------------------------------------------------------------
# 3. Certification Recommendations
# ---------------------------------------------------------------------------

def _recommend_certifications(
    prs_input: PRSInput,
    prs_result: PRSResult,
    datasets: PRSDatasets,
    limit: int = 3,
) -> list[Recommendation]:
    """
    Never recommend a certificate already completed.
    Score by role_alignment x 0.50 + missing_skill_overlap x 0.50
    Also boost by provider credibility tier.
    """
    if not datasets.certificates_dataset:
        return []

    user_norms     = _user_skill_norms(prs_input)
    user_cert_norms = _user_cert_norms(prs_input)
    missing_skills  = prs_result.missing_skills

    # High-credibility provider bonus
    def _provider_bonus(provider: str) -> float:
        score = datasets.certificate_provider_scores.get(provider, 50)
        return (float(score) - 50.0) / 100.0  # -0.5 to +0.5 range

    scored: list[tuple[float, dict[str, Any]]] = []
    for cert in datasets.certificates_dataset:
        cert_name  = cert.get("certificate_name", "")
        # Skip already-owned certificates
        if _norm(cert_name) in user_cert_norms:
            continue
        # Also skip if any alias / partial match of cert_name is in user certs
        if any(_norm(cert_name) in uc or uc in _norm(cert_name) for uc in user_cert_norms):
            continue

        cert_skills = cert.get("skills_covered", [])
        role_align  = _relevance_score(cert.get("role_alignment", []), prs_input.target_role)

        # New skills contribution
        new_skills = [s for s in cert_skills if _norm(s) not in user_norms]
        if not new_skills and role_align == 0.0:
            continue

        # Overlap with missing skills
        if missing_skills:
            overlap = _skills_overlap(cert_skills, missing_skills)
            overlap_score = overlap / len(missing_skills)
        else:
            overlap_score = 0.2

        provider_bonus = _provider_bonus(cert.get("provider", "Unknown"))
        total_score    = (role_align * 0.50) + (min(1.0, overlap_score) * 0.50) + (provider_bonus * 0.15)
        scored.append((total_score, cert))

    scored.sort(key=lambda x: x[0], reverse=True)

    recs: list[Recommendation] = []
    seen: set[str] = set()
    for score, cert in scored[:limit * 2]:
        name = cert["certificate_name"]
        if _norm(name) in seen:
            continue
        seen.add(_norm(name))

        cert_skills  = cert.get("skills_covered", [])
        new_skills   = [s for s in cert_skills if _norm(s) not in user_norms]
        gap_skills   = [s for s in cert_skills if _norm(s) in {_norm(m) for m in missing_skills}]
        provider     = cert.get("provider", "")
        priority     = PRIORITY_HIGH if score >= 0.5 else PRIORITY_MEDIUM if score >= 0.25 else PRIORITY_LOW
        hint         = _pillar_impact_hint(prs_result, "certificate_quality")

        if gap_skills:
            why = (
                f"Earning this {provider} certification will validate your knowledge of "
                f"{', '.join(gap_skills[:3])}, which {'is' if len(gap_skills)==1 else 'are'} "
                f"currently missing in your {prs_input.target_role} profile{hint}."
            )
        else:
            why = (
                f"This {provider} certification is recognized for {prs_input.target_role} roles "
                f"and will improve your Certificate Quality score{hint}."
            )

        recs.append(Recommendation(
            type="certification",
            title=name,
            why_recommended=why,
            skills_addressed=(gap_skills or new_skills)[:5],
            priority=priority,
            url=cert.get("certificate_url"),
            provider=provider,
            difficulty=cert.get("certificate_level"),
        ))
        if len(recs) >= limit:
            break

    return recs


# ---------------------------------------------------------------------------
# 4. Project Recommendations
# ---------------------------------------------------------------------------

def _recommend_projects(
    prs_input: PRSInput,
    prs_result: PRSResult,
    datasets: PRSDatasets,
    limit: int = 3,
) -> list[Recommendation]:
    """
    Score by:
      role_alignment x 0.35 + missing_skill_overlap x 0.35
      + deployment_gap_bonus x 0.20 + deployment_outcome_bonus x 0.10

    Deployment-outcome bonus: extra weight for projects whose expected_outcomes
    explicitly mention deployment/cloud when the user’s Q1 answer is 'no' or
    'local_only'.  This surfaces deployment-teaching projects to the users who
    need them most — not just any project with CI/CD in its tech stack.
    """
    if not datasets.projects_dataset:
        return []

    user_norms    = _user_skill_norms(prs_input)
    missing_skills = prs_result.missing_skills
    has_deploy_gap = _has_deployment_gap(prs_result)
    weak           = set(_weak_pillars(prs_result))
    hint           = _pillar_impact_hint(prs_result, "projects_experience")

    # Determine if the user specifically needs deployment experience (Q1)
    deployment_answer = prs_input.assessment_answers.get("deployment_exposure", "cloud_production")
    needs_deploy_practice = deployment_answer in ("no", "local_only")

    # Project names already in user profile
    user_proj_norms = {_norm(p.name) for p in prs_input.projects}

    scored: list[tuple[float, dict[str, Any]]] = []
    for proj in datasets.projects_dataset:
        proj_name  = proj.get("project_name", "")
        # Skip projects the user already has (approximate)
        if _norm(proj_name) in user_proj_norms:
            continue

        proj_skills = proj.get("primary_skills", [])
        role_align  = _relevance_score(proj.get("role_alignment", []), prs_input.target_role)

        if role_align == 0.0:
            continue  # not relevant at all

        # Missing skill overlap
        if missing_skills:
            overlap = _skills_overlap(proj_skills, missing_skills)
            overlap_score = overlap / len(missing_skills)
        else:
            overlap_score = 0.2

        # Tech-stack deployment gap bonus (has deployment-related tech)
        deploy_keywords = {"ci/cd", "docker", "deployment", "cloud", "aws", "github actions"}
        tech_norms = {_norm(t) for t in proj.get("tech_stack", [])}
        deploy_bonus = 0.3 if (has_deploy_gap and bool(tech_norms & deploy_keywords)) else 0.0

        # Deployment-outcome bonus: project explicitly teaches deployment
        # Only applied when user said they have never deployed (strongest signal)
        outcome_words = {"deploy", "cloud", "hosting", "production", "live"}
        outcomes_lower = [o.lower() for o in proj.get("expected_outcomes", [])]
        teaches_deploy = any(
            any(ow in o for ow in outcome_words) for o in outcomes_lower
        )
        outcome_bonus = 0.2 if (needs_deploy_practice and teaches_deploy) else 0.0

        total_score = (
            (role_align * 0.35)
            + (min(1.0, overlap_score) * 0.35)
            + (deploy_bonus * 0.20)
            + outcome_bonus
        )
        scored.append((total_score, proj))

    scored.sort(key=lambda x: x[0], reverse=True)

    recs: list[Recommendation] = []
    seen: set[str] = set()
    for score, proj in scored[:limit * 2]:
        name = proj["project_name"]
        if _norm(name) in seen:
            continue
        seen.add(_norm(name))

        proj_skills = proj.get("primary_skills", [])
        gap_skills  = [s for s in proj_skills if _norm(s) in {_norm(m) for m in missing_skills}]
        is_deploy   = has_deploy_gap and any(
            _norm(t) in {"ci/cd", "docker", "aws", "github actions"}
            for t in proj.get("tech_stack", [])
        )
        teaches_deploy_outcome = needs_deploy_practice and any(
            any(ow in o.lower() for ow in {"deploy", "cloud", "hosting", "live"})
            for o in proj.get("expected_outcomes", [])
        )
        difficulty  = proj.get("difficulty_level", "")
        priority    = PRIORITY_HIGH if score >= 0.5 else PRIORITY_MEDIUM

        if gap_skills and (is_deploy or teaches_deploy_outcome):
            why = (
                f"This project closes your deployment gap and teaches "
                f"{', '.join(gap_skills[:3])}, strengthening both your Projects and "
                f"Role Alignment scores{hint}."
            )
        elif gap_skills:
            why = (
                f"Building this project will help you practice "
                f"{', '.join(gap_skills[:3])} in a real-world context, "
                f"directly closing skill gaps for {prs_input.target_role}{hint}."
            )
        elif is_deploy or teaches_deploy_outcome:
            why = (
                f"This project focuses on deployment and engineering practices, "
                f"which is your current weakest area for {prs_input.target_role}{hint}."
            )
        else:
            why = (
                f"This project is well-aligned to {prs_input.target_role} and "
                f"will strengthen your portfolio with {difficulty.lower()} complexity work{hint}."
            )

        recs.append(Recommendation(
            type="project",
            title=name,
            why_recommended=why,
            skills_addressed=(gap_skills or proj_skills)[:5],
            priority=priority,
            difficulty=difficulty,
            expected_outcomes=proj.get("expected_outcomes", [])[:4],
        ))
        if len(recs) >= limit:
            break

    return recs


# ---------------------------------------------------------------------------
# 5. Resume Improvement Tips
# ---------------------------------------------------------------------------

def _recommend_resume_improvements(
    prs_input: PRSInput,
    prs_result: PRSResult,
    limit: int = 3,
) -> list[Recommendation]:
    """
    Only generated when resume pillar is weak (< WEAK_PILLAR_THRESHOLD).
    Tips are derived from the resume engine's weak_areas in prs_result.
    """
    resume_score = prs_result.pillar_scores.get("resume_quality", 100.0)
    if resume_score >= STRONG_PILLAR_THRESHOLD:
        return []  # Resume is strong enough -- don't surface noise

    # Derive specific tips from the actual weak_areas
    weak_areas_lower = [a.lower() for a in prs_result.weak_areas]
    recs: list[Recommendation] = []

    tips: list[tuple[str, str, list[str]]] = []  # (condition_substring, title, skills)

    if any("github" in a for a in weak_areas_lower):
        tips.append((
            "GitHub link",
            "Add your GitHub profile URL to your resume",
            ["GitHub"],
        ))
    if any("linkedin" in a for a in weak_areas_lower):
        tips.append((
            "LinkedIn link",
            "Add your LinkedIn profile URL to your resume",
            ["LinkedIn"],
        ))
    if any("impact" in a or "action verb" in a for a in weak_areas_lower):
        tips.append((
            "Use strong action verbs",
            "Rewrite project bullets with strong action verbs and quantified outcomes",
            ["Writing", "Impact Statements"],
        ))
    if any("grammar" in a for a in weak_areas_lower):
        tips.append((
            "Grammar and spelling",
            "Proofread your resume for grammar and spelling errors",
            ["Writing"],
        ))
    if any("keyword" in a for a in weak_areas_lower):
        tips.append((
            "Role keywords",
            f"Add role-specific keywords for {prs_input.target_role} to improve ATS visibility",
            ["Keywords", "ATS Optimization"],
        ))
    if any("section" in a for a in weak_areas_lower):
        tips.append((
            "Incomplete sections",
            "Ensure all standard resume sections are present: Education, Skills, Projects, Experience",
            ["Resume Structure"],
        ))

    # Always add a general tip if resume score is very low
    if resume_score < 40 and len(tips) < 2:
        tips.append((
            "General resume quality",
            "Consider rewriting your resume with a professional template and complete profile sections",
            ["Resume Quality"],
        ))

    priority = PRIORITY_HIGH if resume_score < HINT_PILLAR_THRESHOLD else PRIORITY_MEDIUM
    for _, title, skills in tips[:limit]:
        why = (
            f"Your Resume Quality score is {resume_score:.0f}/100. "
            f"This improvement will directly raise your resume pillar score."
        )
        recs.append(Recommendation(
            type="resume",
            title=title,
            why_recommended=why,
            skills_addressed=skills,
            priority=priority,
        ))

    return recs


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

def _generate_summary(
    prs_result: PRSResult,
    target_role: str,
    weak_pillars: list[str],
) -> str:
    prs_score = prs_result.prs_score
    level     = prs_result.readiness_level
    n_missing = len(prs_result.missing_skills)

    if not weak_pillars:
        return (
            f"Your PRS score is {prs_score:.0f}/100 ({level}). "
            f"Your profile is well-rounded for {target_role} -- "
            f"focus on deepening expertise to reach the next level."
        )

    pillar_display = {
        "skill_readiness":     "Skill Readiness",
        "projects_experience": "Projects & Experience",
        "role_alignment":      "Role Alignment",
        "resume_quality":      "Resume Quality",
        "certificate_quality": "Certificate Quality",
    }
    weak_labels = [pillar_display.get(p, p) for p in weak_pillars[:2]]
    missing_hint = f" You are missing {n_missing} role skills." if n_missing > 0 else ""
    return (
        f"Your PRS score is {prs_score:.0f}/100 ({level}). "
        f"Your biggest gaps are in {' and '.join(weak_labels)}.{missing_hint} "
        f"The recommendations below will have the highest impact on your {target_role} readiness."
    )


# ---------------------------------------------------------------------------
# Public engine function
# ---------------------------------------------------------------------------

def generate_recommendations(
    prs_input: PRSInput,
    prs_result: PRSResult,
    datasets: PRSDatasets,
) -> RecommendationResult:
    """
    Generate the complete, ranked recommendation set for a PRS evaluation.

    Parameters
    ----------
    prs_input : PRSInput
        The normalized input object (has user profile, target role, skills, etc.).
    prs_result : PRSResult
        The orchestrated PRS result (has pillar scores, missing skills, weak areas).
    datasets : PRSDatasets
        Loaded PRS datasets (courses, projects, certificates, role skills).

    Returns
    -------
    RecommendationResult
        Structured recommendations across all five categories.
    """
    weak_pillars = _weak_pillars(prs_result)

    # ---- 1. Skills ----
    skill_recs = _recommend_skills(prs_input, prs_result, datasets, limit=5)

    # ---- 2. Courses ----
    course_recs = _recommend_courses(prs_input, prs_result, datasets, limit=3)

    # ---- 3. Certifications ----
    cert_recs = _recommend_certifications(prs_input, prs_result, datasets, limit=3)

    # ---- 4. Projects ----
    proj_recs = _recommend_projects(prs_input, prs_result, datasets, limit=3)

    # ---- 5. Resume ----
    resume_recs = _recommend_resume_improvements(prs_input, prs_result, limit=3)

    # ---- Summary ----
    summary = _generate_summary(prs_result, prs_input.target_role, weak_pillars)

    return RecommendationResult(
        skills=skill_recs,
        courses=course_recs,
        certifications=cert_recs,
        projects=proj_recs,
        resume_tips=resume_recs,
        summary=summary,
    )
