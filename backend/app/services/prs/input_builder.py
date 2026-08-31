"""
Phase 5 — PRS Input Builder
============================
Combines the saved Module 1 profile (skills, projects, experience,
certifications, resume analysis) with the validated assessment answers
into one normalized PRSInput dataclass that every scoring engine
(Phases 6-10) will consume.

Rules:
- NEVER re-upload the resume; always use already-parsed data.
- Use the editable saved profile state — not raw extraction output.
- If a user added a skill in the profile editor after upload, it appears here.
- Extend the parser/profile minimally; prefer reading existing DB fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Canonical data containers
# ---------------------------------------------------------------------------

@dataclass
class PRSSkill:
    """A single skill entry from the user's saved profile."""
    skill: str
    category: str | None = None


@dataclass
class PRSProject:
    """A single project entry from the user's saved profile."""
    name: str
    description: str
    domain: str | None = None
    skills_used: list[str] = field(default_factory=list)


@dataclass
class PRSInput:
    """
    Complete, normalised input for the PRS engine.

    All five scoring engines read from this object exclusively.
    Nothing inside this object is calculated — it is purely
    a structured snapshot of user evidence.
    """

    # ---- Identity ----
    user_id: int
    target_role: str

    # ---- Profile identity fields (from User ORM, used by resume_engine) ----
    # These carry the DB-saved values so resume_engine sees real data even
    # when resume_analysis is empty (which it always is — not persisted yet).
    name:        str | None = None
    email:       str | None = None
    github_url:  str | None = None
    linkedin_url: str | None = None
    college:     str | None = None
    department:  str | None = None

    # ---- Skills (from saved user_skills rows) ----
    skills: list[PRSSkill] = field(default_factory=list)

    # ---- Projects (from saved user_projects rows) ----
    projects: list[PRSProject] = field(default_factory=list)

    # ---- Experience ----
    # Raw experience strings as saved in User.experience (JSON list of strings)
    experience: list[str] = field(default_factory=list)
    # Free-text duration e.g. "6 months", "1 year"
    experience_duration: str | None = None

    # ---- Certifications ----
    # Raw certificate name strings extracted from the resume
    certifications: list[str] = field(default_factory=list)

    # ---- Resume ----
    # Structured AI analysis dict (Gemini output), if available
    resume_analysis: dict[str, Any] = field(default_factory=dict)
    # Raw resume text stored at parse time (may be None if not persisted)
    resume_text: str | None = None

    # ---- Career meta ----
    # Career interests from the saved profile (used for suggested roles only)
    career_interests: list[str] = field(default_factory=list)

    # ---- Assessment evidence ----
    # Validated answer codes produced by assessment_service.validate_assessment_answers()
    assessment_answers: dict[str, Any] = field(default_factory=dict)

    # ---- Convenience properties ----

    @property
    def skill_names(self) -> list[str]:
        """Flat list of skill name strings."""
        return [s.skill for s in self.skills]

    @property
    def has_projects(self) -> bool:
        return bool(self.projects)

    @property
    def has_certifications(self) -> bool:
        return bool(self.certifications)

    @property
    def has_resume_analysis(self) -> bool:
        return bool(self.resume_analysis)


# ---------------------------------------------------------------------------
# Builder — the only public entry point
# ---------------------------------------------------------------------------

def build_prs_input(
    *,
    user,              # models.User ORM object (with .skills and .projects loaded)
    target_role: str,
    assessment_answers: dict[str, Any],
) -> PRSInput:
    """
    Build a PRSInput from a loaded User ORM object and validated assessment answers.

    Parameters
    ----------
    user : models.User
        SQLAlchemy User instance with relationship attributes ``skills`` and
        ``projects`` already loaded (eager or explicit).
    target_role : str
        The single role chosen by the user for this evaluation.
    assessment_answers : dict
        Validated answer codes from ``assessment_service.validate_assessment_answers()``.

    Returns
    -------
    PRSInput
        Ready-to-use normalised input object.

    Raises
    ------
    ValueError
        When required identity fields are missing.
    """
    if not user or not user.id:
        raise ValueError("build_prs_input: user must be a persisted User record with an id")
    if not target_role or not target_role.strip():
        raise ValueError("build_prs_input: target_role must be a non-empty string")

    target_role = target_role.strip()

    # ---- Skills ----
    skills = [
        PRSSkill(
            skill=_clean_str(row.skill),
            category=_clean_str(row.category) or None,
        )
        for row in (user.skills or [])
        if _clean_str(row.skill)
    ]

    # ---- Projects ----
    projects = [
        PRSProject(
            name=_clean_str(proj.name),
            description=_clean_str(proj.description),
            domain=_clean_str(proj.domain) or None,
            skills_used=_coerce_string_list(proj.skills_used),
        )
        for proj in (user.projects or [])
        if _clean_str(proj.name)
    ]

    # ---- Experience ----
    experience = _coerce_string_list(user.experience)
    experience_duration = _clean_str(user.experience_duration) or None

    # ---- Certifications ----
    # Module 1 does not yet have a dedicated certifications table.
    # The resume parser may store certification names inside resume_analysis
    # or as a specific profile field.  We check both known locations so that
    # Phase 5 is future-proof when Module 1 adds a richer cert model.
    certifications = _extract_certifications(user)

    # ---- Resume analysis ----
    # Stored as JSON in user or as a separate field (varies by Module 1 impl).
    resume_analysis = _extract_resume_analysis(user)
    resume_text = _clean_str(getattr(user, "resume_text", None)) or None

    # ---- Career interests ----
    career_interests = _coerce_string_list(user.career_interests)

    # ---- Profile identity fields — read directly from User ORM ----
    # resume_engine._detect_sections() checks these instead of the
    # always-empty resume_analysis dict (resume_analysis is never persisted).
    name        = _clean_str(getattr(user, "name", None)) or None
    email       = _clean_str(getattr(user, "email", None)) or None
    github_url  = _clean_str(getattr(user, "github_url", None)) or None
    linkedin_url = _clean_str(getattr(user, "linkedin_url", None)) or None
    college     = _clean_str(getattr(user, "college", None)) or None
    department  = _clean_str(getattr(user, "department", None)) or None

    return PRSInput(
        user_id=user.id,
        target_role=target_role,
        name=name,
        email=email,
        github_url=github_url,
        linkedin_url=linkedin_url,
        college=college,
        department=department,
        skills=skills,
        projects=projects,
        experience=experience,
        experience_duration=experience_duration,
        certifications=certifications,
        resume_analysis=resume_analysis,
        resume_text=resume_text,
        career_interests=career_interests,
        assessment_answers=assessment_answers,
    )


def prs_input_to_dict(prs_input: PRSInput) -> dict[str, Any]:
    """
    Serialize PRSInput to a plain dictionary for logging, debugging or
    API responses.  Does NOT include resume_text to avoid leaking PII.
    """
    return {
        "user_id": prs_input.user_id,
        "target_role": prs_input.target_role,
        "skills": [{"skill": s.skill, "category": s.category} for s in prs_input.skills],
        "projects": [
            {
                "name": p.name,
                "description": p.description[:200] + "..." if len(p.description) > 200 else p.description,
                "domain": p.domain,
                "skills_used": p.skills_used,
            }
            for p in prs_input.projects
        ],
        "experience": prs_input.experience,
        "experience_duration": prs_input.experience_duration,
        "certifications": prs_input.certifications,
        "has_resume_analysis": prs_input.has_resume_analysis,
        "career_interests": prs_input.career_interests,
        "assessment_answers": prs_input.assessment_answers,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_str(value: Any) -> str:
    """Convert any value to a stripped string; return empty string for None."""
    if value is None:
        return ""
    return str(value).strip()


def _coerce_string_list(value: Any) -> list[str]:
    """
    Coerce a DB JSON field to a flat list of non-empty strings.

    Handles: None, [], ["str1", "str2"], already-clean lists, etc.
    """
    if not value:
        return []
    if isinstance(value, list):
        return [_clean_str(item) for item in value if _clean_str(item)]
    if isinstance(value, str):
        # Defensive: if stored as a comma-separated string
        return [s.strip() for s in value.split(",") if s.strip()]
    return []


def _extract_certifications(user) -> list[str]:
    """
    Extract certification names from the user record.

    Checks (in priority order):
    1. user.certifications  (if Module 1 ever adds a certifications field)
    2. user.resume_analysis["certifications"]
    3. user.resume_analysis["certifications_list"]
    """
    # Priority 1: dedicated certifications attribute
    if hasattr(user, "certifications") and user.certifications:
        return _coerce_string_list(user.certifications)

    # Priority 2 & 3: nested inside resume_analysis JSON blob
    analysis = _safe_dict(getattr(user, "resume_analysis", None))
    for key in ("certifications", "certifications_list", "certificates"):
        raw = analysis.get(key)
        if raw:
            result = _coerce_string_list(raw)
            if result:
                return result

    return []


def _extract_resume_analysis(user) -> dict[str, Any]:
    """
    Return the structured resume analysis dict, or {} if unavailable.
    """
    raw = getattr(user, "resume_analysis", None)
    return _safe_dict(raw)


def _safe_dict(value: Any) -> dict[str, Any]:
    """Return value if it is a dict, otherwise {}."""
    if isinstance(value, dict):
        return value
    return {}
