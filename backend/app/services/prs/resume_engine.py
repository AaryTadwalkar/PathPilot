"""
Phase 9 -- Resume Quality Engine
==================================
Evaluates how well-crafted the resume is for ATS systems, professional
presentation, and role keyword alignment.

Formula:
    resume_quality_score =
        (ats_score          x 0.30)
      + (section_completeness x 0.20)
      + (keyword_relevance  x 0.20)
      + (formatting         x 0.15)
      + (grammar            x 0.10)
      + (impact_statements  x 0.05)

Hybrid analysis:
    Deterministic:
        Sections presence, contact data, skills count, project/experience
        presence, links (GitHub/LinkedIn), profile completeness.

    Vector (BGE embeddings):
        keyword_relevance -- cosine similarity between the resume text
        embedding and the role's required skills embedding.

    LLM (Gemini):
        grammar, professional language quality, bullet point clarity,
        impact statements.  Called ONCE with a focused prompt.
        Falls back to neutral scores if unavailable.

Resume text availability:
    Module 1 does not persist resume_text in the DB.  The engine
    therefore scores based on structured profile evidence (skills,
    projects, experience, links) from PRSInput for deterministic
    sub-scores, and uses the resume_analysis dict if present.
    If resume_text IS available (future-proof), it is used for
    vector and LLM analysis.

Required output:
    {
        "score": 72,
        "ats_score": 80,
        "section_completeness": 90,
        "keyword_relevance": 65,
        "formatting": 75,
        "grammar": 85,
        "impact_statements": 40,
        "issues": [],
        "improvement_suggestions": []
    }
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.services.prs.dataset_loader import PRSDatasets
from app.services.prs.input_builder import PRSInput

# ---------------------------------------------------------------------------
# Formula weights (spec-defined)
# ---------------------------------------------------------------------------

W_ATS         = 0.30
W_SECTIONS    = 0.20
W_KEYWORDS    = 0.20
W_FORMATTING  = 0.15
W_GRAMMAR     = 0.10
W_IMPACT      = 0.05

# ---------------------------------------------------------------------------
# Section presence points (for deterministic section_completeness)
# ---------------------------------------------------------------------------

# Each section contributes points toward 100
SECTION_WEIGHTS: dict[str, float] = {
    "has_name":        10.0,
    "has_email":       10.0,
    "has_github":      10.0,
    "has_linkedin":    10.0,
    "has_skills":      20.0,
    "has_projects":    20.0,
    "has_experience":  10.0,
    "has_education":   10.0,  # college + department
}

# ATS-critical sections (unweighted presence check)
ATS_CRITICAL = ["has_name", "has_email", "has_skills", "has_projects"]

# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class ResumeQualityResult:
    score: float
    ats_score: float
    section_completeness: float
    keyword_relevance: float
    formatting: float
    grammar: float
    impact_statements: float
    issues: list[str]
    improvement_suggestions: list[str]
    weak_areas: list[str]
    llm_used: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "score":                round(self.score, 2),
            "ats_score":            round(self.ats_score, 2),
            "section_completeness": round(self.section_completeness, 2),
            "keyword_relevance":    round(self.keyword_relevance, 2),
            "formatting":           round(self.formatting, 2),
            "grammar":              round(self.grammar, 2),
            "impact_statements":    round(self.impact_statements, 2),
            "issues":               self.issues,
            "improvement_suggestions": self.improvement_suggestions,
            "weak_areas":           self.weak_areas,
            "llm_used":             self.llm_used,
            "formula": (
                "ats*0.30 + sections*0.20 + keywords*0.20 "
                "+ formatting*0.15 + grammar*0.10 + impact*0.05"
            ),
        }


# ---------------------------------------------------------------------------
# Deterministic helpers
# ---------------------------------------------------------------------------

def _detect_sections(prs_input: PRSInput, analysis: dict[str, Any]) -> dict[str, bool]:
    """
    Detect which resume sections are present using the structured profile.

    Priority order for each field:
      1. PRSInput identity fields (github_url, linkedin_url, name, email, college, department)
         — these come from the User ORM and are always correct.
      2. resume_analysis dict — fallback for future use when resume_analysis is persisted.

    Previously this only checked analysis.get("github_url") etc., but resume_analysis
    is never stored in the DB so analysis was always {}, making every field appear missing.
    """
    # -- Identity: check PRSInput DB fields first, fall back to analysis dict --
    has_name     = bool(prs_input.name or _safe_str(analysis.get("name")))
    has_email    = bool(prs_input.email or _safe_str(analysis.get("email")))
    has_github   = bool(prs_input.github_url or _safe_str(analysis.get("github_url")))
    has_linkedin = bool(prs_input.linkedin_url or _safe_str(analysis.get("linkedin_url")))

    # -- Profile content --
    has_skills    = bool(prs_input.skills)
    has_projects  = bool(prs_input.projects)
    has_experience = bool(prs_input.experience)
    has_education  = bool(
        prs_input.college or prs_input.department
        or _safe_str(analysis.get("college"))
        or _safe_str(analysis.get("department"))
    )

    return {
        "has_name":       has_name,
        "has_email":      has_email,
        "has_github":     has_github,
        "has_linkedin":   has_linkedin,
        "has_skills":     has_skills,
        "has_projects":   has_projects,
        "has_experience": has_experience,
        "has_education":  has_education,
    }



def _section_completeness_score(sections: dict[str, bool]) -> tuple[float, list[str]]:
    """
    Weighted section completeness.  Returns (score_0_to_100, missing_sections).
    """
    total_possible = sum(SECTION_WEIGHTS.values())
    earned = sum(
        SECTION_WEIGHTS[k] for k, present in sections.items() if present
    )
    score = (earned / total_possible) * 100.0

    missing = []
    labels = {
        "has_name": "Full name",
        "has_email": "Email address",
        "has_github": "GitHub profile link",
        "has_linkedin": "LinkedIn profile link",
        "has_skills": "Skills section",
        "has_projects": "Projects section",
        "has_experience": "Work/internship experience",
        "has_education": "Education details",
    }
    for k, present in sections.items():
        if not present:
            missing.append(labels.get(k, k))

    return round(score, 2), missing


def _ats_score(sections: dict[str, bool], prs_input: PRSInput) -> float:
    """
    ATS score based on:
    - Critical section presence (60 pts)
    - Skills count adequacy (20 pts)
    - Projects/Experience adequacy (20 pts)
    """
    critical_score = sum(
        15.0 for k in ATS_CRITICAL if sections.get(k, False)
    )  # 4 x 15 = 60

    skills_count = len(prs_input.skills)
    if skills_count >= 10:
        skills_pts = 20.0
    elif skills_count >= 5:
        skills_pts = 12.0
    elif skills_count >= 2:
        skills_pts = 6.0
    else:
        skills_pts = 0.0

    has_proj_or_exp = sections.get("has_projects", False) or sections.get("has_experience", False)
    depth_pts = 20.0 if has_proj_or_exp else 0.0

    return min(100.0, critical_score + skills_pts + depth_pts)


def _formatting_score(sections: dict[str, bool], prs_input: PRSInput) -> float:
    """
    Deterministic proxy for formatting quality.

    Rewards:
    - Having professional links (GitHub, LinkedIn)  — signals professional formatting
    - Skills structured (not just one long string)  — implies proper bullet formatting
    - Projects with descriptions                    — implies formatted bullet points
    - Experience entries                            — proper structure
    """
    score = 40.0  # baseline — any resume has some structure

    # Professional links
    if sections.get("has_github"):
        score += 15.0
    if sections.get("has_linkedin"):
        score += 15.0

    # Projects with descriptions
    described_projects = [p for p in prs_input.projects if p.description and len(p.description) > 30]
    if len(described_projects) >= 2:
        score += 20.0
    elif described_projects:
        score += 10.0

    # Skills breadth
    if len(prs_input.skills) >= 8:
        score += 10.0
    elif len(prs_input.skills) >= 4:
        score += 5.0

    return min(100.0, score)


def _keyword_relevance_vector(prs_input: PRSInput, datasets: PRSDatasets) -> float:
    """
    Vector-based keyword relevance.

    Computes cosine similarity between:
      (user's skills + project skills + experience text)
    and:
      (role's required skills joined as a text)

    Falls back to skills-overlap ratio if embeddings fail.
    """
    target_role = prs_input.target_role

    # Build role skill text
    role_entry = next(
        (e for e in datasets.role_skill_mapping if e.get("role") == target_role),
        None,
    )
    if not role_entry:
        return 50.0

    role_skills = [s["skill_name"] for s in role_entry.get("skills", [])]
    if not role_skills:
        return 50.0

    # ---- Quick deterministic fallback: skills overlap ----
    user_skills_lower = {s.skill.lower() for s in prs_input.skills}
    role_skills_lower = {s.lower() for s in role_skills}
    overlap = len(user_skills_lower & role_skills_lower)
    overlap_score = min(100.0, (overlap / len(role_skills_lower)) * 100.0)

    # ---- Try vector similarity (richer signal) ----
    try:
        from app.services.embeddings import model as _bge_model

        # User "resume text" proxy: all skills + project skills + experience
        user_parts = list(prs_input.skill_names)
        for proj in prs_input.projects:
            user_parts.extend(proj.skills_used[:5])
        user_parts.extend(prs_input.experience[:3])
        user_text = " ".join(user_parts)

        role_text = " ".join(role_skills)

        if not user_text.strip():
            return overlap_score

        embs = _bge_model.encode(
            [user_text, role_text],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        sim = float(np.dot(embs[0], embs[1]))
        # Blend vector + overlap for robustness
        vector_score = min(100.0, sim * 100.0)
        return round((vector_score * 0.60) + (overlap_score * 0.40), 2)

    except Exception as exc:
        print(f"[ResumeEngine] Vector keyword relevance failed: {exc}")
        return round(overlap_score, 2)


# ---------------------------------------------------------------------------
# LLM analysis (Gemini)
# ---------------------------------------------------------------------------

def _llm_resume_analysis(prs_input: PRSInput) -> dict[str, Any] | None:
    """
    Evaluate resume grammar, impact statements and professional tone via
    the Phase 15 LLM Gateway.

    The gateway owns:
      - Pydantic schema validation + score clamping (0-100)
      - Bounded retry (3 attempts) on parse/validation failure
      - In-process SHA-256 cache keyed by content_hash + role
        (resume analysis IS role-dependent so role is part of the key)
      - Privacy-safe logging: resume text is NEVER printed to logs
      - Deterministic fallback: returns None when LLM is unavailable

    Returns dict with keys: grammar, impact_statements, professional_tone,
    issues, improvement_suggestions.  Returns None on failure.
    """
    from app.services.prs.llm_gateway import analyze_resume as _gw_analyze

    # Build resume content (never logged in full by the gateway)
    if prs_input.resume_text and len(prs_input.resume_text.strip()) > 100:
        resume_content = prs_input.resume_text          # gateway truncates internally
        content_source = "resume_text"
    else:
        # Structured proxy from profile data (safe to build, no raw text)
        lines: list[str] = []
        lines.append(f"Target Role: {prs_input.target_role}")
        lines.append(f"Skills: {', '.join(prs_input.skill_names[:15])}")
        if prs_input.projects:
            lines.append("Projects:")
            for p in prs_input.projects[:3]:
                desc = (p.description or "")[:120]
                lines.append(f"  - {p.name}: {desc}")
        if prs_input.experience:
            lines.append("Experience:")
            for exp in prs_input.experience[:3]:
                lines.append(f"  - {exp}")
        resume_content = "\n".join(lines)
        content_source = "structured_proxy"

    return _gw_analyze(
        resume_content=resume_content,
        content_source=content_source,
        target_role=prs_input.target_role,
    )


def _deterministic_grammar_score(prs_input: "PRSInput") -> float:
    """
    Multi-signal deterministic grammar proxy used when LLM is unavailable.

    Replaces the old single-signal description-length approach with four
    independent signals, each rewarding clear and deliberate writing:

    Signal 1 — Capitalisation consistency (0–15 pts)
        Each project description that starts with an uppercase letter adds
        points.  Systematic capitalisation correlates with careful writing.

    Signal 2 — Average description word count (0–15 pts)
        Longer descriptions indicate the user invested effort in expressing
        what the project does; very short descriptions suggest copy-paste.

    Signal 3 — Filler word penalty (0–10 deducted)
        "very", "just", "basically", etc. are hallmarks of informal or
        low-effort writing.  Each hit reduces the score.

    Signal 4 — Experience entry quality (0–10 pts)
        Experience entries written as complete sentences (more than 6 words)
        suggest the user can describe their work clearly.

    Baseline: 50.0 (neutral — no text to penalise, nothing to reward).
    Returns float in [0, 100].
    """
    all_text_parts = [
        (p.description or "") for p in prs_input.projects
    ] + prs_input.experience

    if not any(t.strip() for t in all_text_parts):
        return 60.0  # neutral — nothing to evaluate

    full_text = " ".join(all_text_parts)
    words_lower = full_text.lower().split()
    score = 50.0  # baseline

    # Signal 1: Capitalisation consistency
    caps_ok = sum(
        1 for p in prs_input.projects
        if p.description and p.description.strip() and p.description.strip()[0].isupper()
    )
    score += min(15.0, caps_ok * 5.0)

    # Signal 2: Average description word count
    desc_lengths = [
        len((p.description or "").split())
        for p in prs_input.projects
        if (p.description or "").strip()
    ]
    if desc_lengths:
        avg_words = sum(desc_lengths) / len(desc_lengths)
        if   avg_words >= 30: score += 15.0
        elif avg_words >= 15: score +=  9.0
        elif avg_words >= 7:  score +=  4.0

    # Signal 3: Filler word penalty
    FILLER = {
        "very", "just", "stuff", "things", "basically", "literally",
        "kinda", "sorta", "etc", "and stuff", "you know",
    }
    filler_count = sum(1 for w in words_lower if w in FILLER)
    score -= min(10.0, filler_count * 2.0)

    # Signal 4: Experience entry quality
    long_exp = sum(1 for e in prs_input.experience if len(e.split()) > 6)
    score += min(10.0, long_exp * 3.0)

    return max(0.0, min(100.0, score))


def _deterministic_impact_score(prs_input: "PRSInput") -> float:
    """
    Weighted deterministic impact proxy used when LLM is unavailable.

    Replaces the old binary verb-presence approach with four weighted signals:

    Signal 1 — Weighted action verb score (0–60 pts)
        Each strong action verb contributes a different number of points
        based on the strength of the word ("architected" scores higher than
        "created").  Capped at 60 to leave room for other signals.

    Signal 2 — Quantification (0–20 pts)
        Numbers in descriptions (e.g. ‘50% reduction’, ‘10,000 users’)
        strongly indicate measurable, impactful outcomes.

    Signal 3 — Outcome language (0–15 pts)
        Words like ‘live’, ‘production’, ‘deployed’, ‘users’, ‘client’
        signal real-world impact rather than academic exercises.

    Signal 4 — Weak-indicator penalty (0–15 deducted)
        Phrases like “followed tutorial” or “copied from” strongly indicate
        that the work was not original and lacks impact.

    Returns float in [0, 100].
    """
    import re as _re

    # Higher score = stronger action verb
    STRONG_VERBS: dict[str, float] = {
        "architected": 5.0, "engineered": 5.0, "deployed": 5.0,
        "optimized": 5.0, "reduced": 5.0, "automated": 4.0,
        "built": 4.0, "developed": 4.0, "designed": 4.0,
        "implemented": 4.0, "launched": 4.0, "shipped": 4.0,
        "achieved": 4.0, "improved": 4.0, "increased": 4.0,
        "integrated": 3.0, "led": 3.0, "managed": 3.0,
        "delivered": 3.0, "created": 2.0, "made": 1.0,
    }
    WEAK_INDICATORS = [
        "followed tutorial", "followed a tutorial", "watched video",
        "copied from", "based on tutorial", "guided by",
        "step by step", "step-by-step", "followed along",
    ]
    OUTCOME_WORDS = {
        "live", "production", "deployed", "users", "client",
        "real", "organization", "organisation", "public", "team",
    }

    all_text = " ".join(
        [(p.description or "") for p in prs_input.projects] + prs_input.experience
    )
    all_text_lower = all_text.lower()

    # Signal 1: Weighted verb score
    verb_points = sum(
        pts for verb, pts in STRONG_VERBS.items() if verb in all_text_lower
    )
    verb_score = min(60.0, verb_points * 2.5)

    # Signal 2: Quantification (digits in text)
    numbers = len(_re.findall(r"\b\d+[%x]?\b", all_text_lower))
    quant_score = min(20.0, numbers * 4.0)

    # Signal 3: Outcome language
    outcome_hits = sum(1 for w in OUTCOME_WORDS if w in all_text_lower)
    outcome_score = min(15.0, outcome_hits * 5.0)

    # Signal 4: Penalty for tutorial language
    penalty = sum(5.0 for phrase in WEAK_INDICATORS if phrase in all_text_lower)
    penalty = min(15.0, penalty)

    return max(0.0, min(100.0, verb_score + quant_score + outcome_score - penalty))


# ---------------------------------------------------------------------------
# Weak area detection
# ---------------------------------------------------------------------------

def _detect_weak_areas(
    sections: dict[str, bool],
    scores: dict[str, float],
    missing_sections: list[str],
) -> list[str]:
    weak = []

    if missing_sections:
        for m in missing_sections[:3]:
            weak.append(f"Missing resume section: {m}")

    if scores["keyword_relevance"] < 50:
        weak.append("Low keyword match with the target role -- add more relevant skills")

    if scores["grammar"] < 60:
        weak.append("Resume has grammar or writing quality issues")

    if scores["impact_statements"] < 50:
        weak.append("Bullet points lack quantified impact or strong action verbs")

    if not sections.get("has_github"):
        weak.append("No GitHub profile link -- add it to strengthen ATS and recruiter trust")

    if not sections.get("has_linkedin"):
        weak.append("No LinkedIn profile link -- add it for professional visibility")

    return weak


# ---------------------------------------------------------------------------
# Public engine function
# ---------------------------------------------------------------------------

def calculate_resume_quality(
    prs_input: PRSInput,
    datasets: PRSDatasets,
) -> ResumeQualityResult:
    """
    Calculate the Resume Quality pillar score.

    Parameters
    ----------
    prs_input : PRSInput
        Normalized PRS input from input_builder.
    datasets : PRSDatasets
        Loaded PRS datasets.

    Returns
    -------
    ResumeQualityResult
        Full sub-score breakdown + issues + improvement suggestions.
    """
    # Safely extract resume_analysis if available
    analysis: dict[str, Any] = prs_input.resume_analysis or {}

    # ---- 1. Deterministic: section completeness ----
    sections = _detect_sections(prs_input, analysis)
    section_score, missing_sections = _section_completeness_score(sections)

    # ---- 2. ATS score ----
    ats = _ats_score(sections, prs_input)

    # ---- 3. Vector: keyword relevance ----
    keyword_rel = _keyword_relevance_vector(prs_input, datasets)

    # ---- 4. Formatting (deterministic proxy) ----
    formatting = _formatting_score(sections, prs_input)

    # ---- 5. LLM: grammar + impact_statements ----
    llm_result = _llm_resume_analysis(prs_input)
    llm_used = llm_result is not None

    if llm_result:
        grammar = float(llm_result["grammar"])
        impact  = float(llm_result["impact_statements"])
        llm_issues         = llm_result.get("issues", [])
        llm_suggestions    = llm_result.get("improvement_suggestions", [])
    else:
        grammar = _deterministic_grammar_score(prs_input)
        impact  = _deterministic_impact_score(prs_input)
        llm_issues      = []
        llm_suggestions = []

    # ---- 6. Final weighted score ----
    score = (
        (ats          * W_ATS)
      + (section_score * W_SECTIONS)
      + (keyword_rel  * W_KEYWORDS)
      + (formatting   * W_FORMATTING)
      + (grammar      * W_GRAMMAR)
      + (impact       * W_IMPACT)
    )
    score = max(0.0, min(100.0, score))

    # ---- Issues & suggestions ----
    issues = list(llm_issues)
    for m in missing_sections:
        issues.append(f"Missing: {m}")

    suggestions = list(llm_suggestions)
    if not sections.get("has_github"):
        suggestions.append("Add your GitHub profile URL to showcase your coding work.")
    if not sections.get("has_linkedin"):
        suggestions.append("Add your LinkedIn URL for professional credibility.")
    if keyword_rel < 50:
        suggestions.append(
            f"Add more keywords relevant to {prs_input.target_role} "
            "(check the role's required skills in the Skill Readiness results)."
        )

    # ---- Weak areas ----
    sub_scores = {
        "ats_score": ats,
        "section_completeness": section_score,
        "keyword_relevance": keyword_rel,
        "formatting": formatting,
        "grammar": grammar,
        "impact_statements": impact,
    }
    weak_areas = _detect_weak_areas(sections, sub_scores, missing_sections)

    return ResumeQualityResult(
        score=round(score, 2),
        ats_score=round(ats, 2),
        section_completeness=round(section_score, 2),
        keyword_relevance=round(keyword_rel, 2),
        formatting=round(formatting, 2),
        grammar=round(grammar, 2),
        impact_statements=round(impact, 2),
        issues=issues[:8],
        improvement_suggestions=suggestions[:8],
        weak_areas=weak_areas,
        llm_used=llm_used,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()
