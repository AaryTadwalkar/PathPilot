"""
Phase 7 -- Projects + Experience Engine
=========================================
Measures practical engineering maturity.

Final formula:
    projects_experience_score =
        (final_project_score   x 0.80)
      + (experience_score      x 0.20)

Project score:
    final_project_score =
        (project_quality_score   x 0.75)
      + (project_relevance_score x 0.25)

Project quality:
    project_quality_score =
        (project_complexity         x 0.45)
      + (tech_stack_sophistication  x 0.35)
      + (deployment_exposure        x 0.20)

Experience score:
    experience_score =
        (experience_duration_score    x 0.40)
      + (experience_role_relevance    x 0.30)
      + (engineering_workflow_exposure x 0.30)

Multiple-project aggregation (top-3 relevant, weighted):
    best project  -> 50%
    second        -> 30%
    third         -> 20%

Assessment questions consumed:
    Q1 deployment_exposure         -> deployment_exposure score
    Q2 project_ownership           -> project complexity proxy
    Q3 engineering_practices       -> engineering_workflow_exposure
    Q4 relevant_experience_duration-> experience_duration_score
    Q5 real_world_usage            -> project complexity signal
    Q6 problem_solving_independence-> project complexity signal

LLM usage:
    Gemini is called ONCE to classify project domains and estimate
    complexity for each user project.  If Gemini is unavailable the
    engine falls back to deterministic scoring so it never blocks.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.services.prs.dataset_loader import PRSDatasets
from app.services.prs.input_builder import PRSInput, PRSProject
from app.services.prs.assessment_service import SCORE_MAPS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Assessment-derived deployment exposure scores  (Q1)
DEPLOYMENT_SCORES: dict[str, float] = {
    "cloud_production": 100.0,
    "public_hosting":   85.0,
    "local_only":       40.0,
    "no":                0.0,
}

# Project-ownership complexity mapping (Q2)
OWNERSHIP_COMPLEXITY: dict[str, float] = {
    "architecture_integrated_systems": 100.0,
    "multiple_components":              80.0,
    "small_independent":                50.0,
    "tutorial_minor_changes":           20.0,
}

# Real-world usage score (Q5)
USAGE_SCORES: dict[str, float] = {
    "organization_client_user_base": 100.0,
    "small_real_users":               75.0,
    "friends_or_team":                40.0,
    "no":                              0.0,
}

# Problem-solving independence (Q6)
PROBLEM_SOLVING_SCORES: dict[str, float] = {
    "root_cause_tradeoffs":  100.0,
    "debug_and_implement":    80.0,
    "adapt_existing_code":    50.0,
    "tutorial_dependent":     20.0,
}

# Experience duration (Q4)
DURATION_SCORES: dict[str, float] = {
    "2_plus_years":   100.0,
    "1_2_years":       85.0,
    "6_12_months":     65.0,
    "less_6_months":   35.0,
    "none":             0.0,
}

# Engineering workflow practice scores (Q3, additive up to 100)
PRACTICE_SCORES: dict[str, float] = {
    "git":              20.0,
    "code_reviews":     15.0,
    "testing":          20.0,
    "ci_cd":            20.0,
    "cloud_deployment": 15.0,
    "issue_tracking":    5.0,
    "agile":             5.0,
    "none":              0.0,
}

# Default stack sophistication for technologies not in the dataset
DEFAULT_STACK_SCORE = 50.0

# Multi-project aggregation weights (best, second, third)
PROJECT_AGG_WEIGHTS = [0.50, 0.30, 0.20]

# Semantic similarity threshold for relevance matching
RELEVANCE_SIM_THRESHOLD = 0.60


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ProjectScore:
    """Scores for a single user project."""
    project_name: str
    quality_score: float         # 0-100
    relevance_score: float       # 0-100
    final_score: float           # quality*0.75 + relevance*0.25
    complexity: float
    tech_sophistication: float
    domain_match: float
    llm_classified: bool


@dataclass
class ProjectsExperienceResult:
    """Complete output of the Projects + Experience Engine."""
    score: float                        # 0-100 final pillar score
    final_project_score: float          # 0-100 aggregated project score
    experience_score: float             # 0-100
    project_scores: list[dict[str, Any]]
    weak_areas: list[str]
    breakdown: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "final_project_score": round(self.final_project_score, 2),
            "experience_score": round(self.experience_score, 2),
            "project_scores": self.project_scores,
            "weak_areas": self.weak_areas,
            "breakdown": self.breakdown,
        }


# ---------------------------------------------------------------------------
# Assessment helpers
# ---------------------------------------------------------------------------

def _get_answer(answers: dict[str, Any], key: str, default: str = "none") -> str:
    """Safely pull a single-select answer code, fallback to default."""
    val = answers.get(key, default)
    return val if isinstance(val, str) else default


def _get_multi_answer(answers: dict[str, Any], key: str) -> list[str]:
    """Safely pull a multi-select answer list."""
    val = answers.get(key, [])
    return val if isinstance(val, list) else []


# ---------------------------------------------------------------------------
# Deployment exposure  (Q1)
# ---------------------------------------------------------------------------

def _deployment_score(answers: dict[str, Any]) -> float:
    code = _get_answer(answers, "deployment_exposure", "no")
    return DEPLOYMENT_SCORES.get(code, 0.0)


# ---------------------------------------------------------------------------
# Project complexity  (Q2 + Q5 + Q6 + optional LLM)
# ---------------------------------------------------------------------------

def _assessment_complexity_score(answers: dict[str, Any]) -> float:
    """
    Deterministic complexity from assessment answers only.
    Combines Q2 (ownership), Q5 (real-world usage), Q6 (problem solving).
    """
    ownership = OWNERSHIP_COMPLEXITY.get(
        _get_answer(answers, "project_ownership", "tutorial_minor_changes"), 20.0
    )
    usage = USAGE_SCORES.get(
        _get_answer(answers, "real_world_usage", "no"), 0.0
    )
    problem = PROBLEM_SOLVING_SCORES.get(
        _get_answer(answers, "problem_solving_independence", "tutorial_dependent"), 20.0
    )
    # Weighted blend: ownership is the strongest signal
    return (ownership * 0.50) + (usage * 0.25) + (problem * 0.25)


def _description_richness(project: "PRSProject") -> float:
    """
    Score a project's description for technical depth and content quality.

    Used as a 20% signal inside _deterministic_classify_project() to replace
    the LLM complexity estimate when Gemini is unavailable.

    Scoring components (all capped, summed to 100 max):
      - Word count tier       (0–30) — more words = more thought
      - Technical markers     (0–40) — architecture/engineering keywords
      - Quantification        (0–20) — numbers imply real results
      - Project name richness (0–10) — multi-word names are more deliberate

    This function is also called from calculate_projects_experience() as part
    of the final complexity blending when llm_classified is False.

    Returns float in [0, 100].
    """
    import re as _re

    text = (project.description or "").lower()
    name = (project.name or "")

    # — Word count tier —
    words = len(text.split())
    if   words >= 150: word_pts = 30.0
    elif words >= 80:  word_pts = 22.0
    elif words >= 40:  word_pts = 14.0
    elif words >= 15:  word_pts =  7.0
    else:              word_pts =  0.0

    # — Technical depth markers —
    TECHNICAL_MARKERS = {
        "api", "database", "db", "authentication", "auth", "deployment", "deploy",
        "docker", "kubernetes", "k8s", "microservice", "endpoint", "scalable",
        "algorithm", "model", "pipeline", "integration", "asynchronous", "async",
        "caching", "cache", "load balancing", "ci/cd", "test", "benchmark",
        "optimize", "architecture", "designed", "implemented", "server",
        "frontend", "backend", "fullstack", "real-time", "streaming", "queue",
        "websocket", "graphql", "rest", "orm", "migration", "schema",
    }
    tech_hits = sum(1 for m in TECHNICAL_MARKERS if m in text)
    tech_pts = min(40.0, tech_hits * 4.0)

    # — Quantification (numbers signal measurable outcomes) —
    numbers = len(_re.findall(r"\b\d+[%x]?\b", text))
    quant_pts = min(20.0, numbers * 4.0)

    # — Project name richness (single word = tutorial clone; multi-word = deliberate) —
    name_pts = min(10.0, len(name.split()) * 2.5)

    return min(100.0, word_pts + tech_pts + quant_pts + name_pts)


def _deterministic_classify_project(
    project: "PRSProject",
    target_role: str,
    answers: dict[str, Any],
    datasets: "PRSDatasets",
) -> dict[str, Any]:
    """
    Produce the same output shape as the LLM gateway’s classify_projects()
    without any API calls.

    Output shape:
        {"name": str, "domains": list[str], "complexity_score": float,
         "rationale": str}

    Domain classification strategy
    --------------------------------
    Gemini classifies projects into domain strings ("Backend Systems",
    "Machine Learning", etc.).  We replicate this by reversing the
    role → tech-stack dataset:

      1.  Normalise the project’s skills_used via stack aliases.
      2.  For every role in role_tech_stack_mapping count how many
          project skills appear in primary_stack (weight 2) and
          secondary_stack (weight 1).
      3.  Take the top-2 matched roles.
      4.  Look up each matched role’s domains via role_domain_mapping.
      5.  Deduplicate and take the top-3 domain strings.

    Complexity score strategy
    -------------------------
    Five weighted signals replace the single LLM estimate:

      tech_sophistication  (0.30) — _tech_sophistication_score() [already exists]
      description_richness (0.20) — _description_richness()       [NEW]
      ownership            (0.25) — assessment Q2 (project_ownership)
      real_world_usage     (0.15) — assessment Q5 (real_world_usage)
      problem_solving      (0.10) — assessment Q6 (problem_solving_independence)

    All components are [0, 100]; the weighted sum is clamped to [0, 100].

    Called by calculate_projects_experience() when llm_results is empty
    (i.e. always in PRS_DETERMINISTIC_MODE, or when Gemini fails).
    """
    # —— Tech sophistication (already implemented, re-use) ——
    tech_soph = _tech_sophistication_score(project, datasets)

    # —— Description richness (new per-project signal) ——
    desc_rich = _description_richness(project)

    # —— Assessment signals ——
    ownership      = OWNERSHIP_COMPLEXITY.get(
        _get_answer(answers, "project_ownership", "tutorial_minor_changes"), 20.0
    )
    usage          = USAGE_SCORES.get(
        _get_answer(answers, "real_world_usage", "no"), 0.0
    )
    problem_solving = PROBLEM_SOLVING_SCORES.get(
        _get_answer(answers, "problem_solving_independence", "tutorial_dependent"), 20.0
    )

    # —— 5-signal complexity composite ——
    complexity_score = min(100.0, max(0.0,
        tech_soph       * 0.30
        + desc_rich     * 0.20
        + ownership     * 0.25
        + usage         * 0.15
        + problem_solving * 0.10
    ))

    # —— Domain classification via reverse role-stack lookup ——
    # Normalize project skills via aliases
    alias_map: dict[str, str] = {k.lower(): v.lower() for k, v in datasets.stack_aliases.items()}
    project_skills_norm: set[str] = {
        alias_map.get(s.lower(), s.lower()) for s in (project.skills_used or [])
    }

    # Score each role by how many of its stack techs the project uses
    role_stack_scores: list[tuple[float, str]] = []
    for entry in datasets.role_tech_stack_mapping:
        role_name = entry.get("role", "")
        primary   = [alias_map.get(t.lower(), t.lower()) for t in entry.get("primary_stack", [])]
        secondary = [alias_map.get(t.lower(), t.lower()) for t in entry.get("secondary_stack", [])]

        score = 0.0
        for tech in primary:
            if tech in project_skills_norm:
                score += 2.0
        for tech in secondary:
            if tech in project_skills_norm:
                score += 1.0

        if score > 0:
            role_stack_scores.append((score, role_name))

    # Take top-2 matched roles, get their domain lists
    role_stack_scores.sort(key=lambda x: x[0], reverse=True)
    top_roles = [r for _, r in role_stack_scores[:2]]

    seen_domains: list[str] = []
    seen_set:     set[str]  = set()
    for role in top_roles:
        for domain in datasets.role_domain_mapping.get(role, []):
            d_norm = domain.strip()
            if d_norm.lower() not in seen_set:
                seen_domains.append(d_norm)
                seen_set.add(d_norm.lower())

    # Fallback: if project has no recognised stack, derive domain from target role
    if not seen_domains:
        for domain in datasets.role_domain_mapping.get(target_role, [])[:2]:
            seen_domains.append(domain)

    domains = seen_domains[:3]

    # Build a one-line rationale for debugging/explainability
    rationale = (
        f"tech_soph={tech_soph:.0f} desc_rich={desc_rich:.0f} "
        f"ownership={ownership:.0f} usage={usage:.0f} "
        f"problem_solving={problem_solving:.0f} → complexity={complexity_score:.0f}"
    )

    return {
        "name":             project.name,
        "domains":          domains,
        "complexity_score": round(complexity_score, 1),
        "rationale":        rationale,
        "llm_classified":   False,
    }


def _llm_classify_projects(projects: list[PRSProject], target_role: str) -> list[dict[str, Any]]:
    """
    Classify all user projects via the Phase 15 LLM Gateway.

    The gateway owns:
      - Pydantic schema validation + score clamping (0-100)
      - Bounded retry (MAX_RETRIES attempts)
      - In-process SHA-256 content cache (role-independent -- complexity
        may be reused across roles; relevance is recalculated here)
      - Privacy-safe logging (no resume text ever printed)
      - Deterministic fallback: returns [] when LLM is unavailable

    Returns a validated list of dicts:
        {name, domains, complexity_score (clamped 0-100), rationale}
    """
    if not projects:
        return []

    from app.services.prs.llm_gateway import classify_projects as _gw_classify

    # Build privacy-safe project input dicts for the gateway
    project_dicts = [
        {
            "name":        p.name,
            # Description truncated to 250 chars inside gateway (privacy)
            "description": (p.description or ""),
            "skills":      ", ".join(p.skills_used[:10]) if p.skills_used else "",
        }
        for p in projects
    ]

    return _gw_classify(project_dicts, target_role)



# ---------------------------------------------------------------------------
# Tech stack sophistication
# ---------------------------------------------------------------------------

def _tech_sophistication_score(project: PRSProject, datasets: PRSDatasets) -> float:
    """
    Score a project's tech sophistication from its skills_used list.
    Uses stack_sophistication_mapping with alias normalisation.
    Does NOT reward merely listing many technologies.

    Strategy:
    - Look up each skill in the mapping (case-insensitive, then alias)
    - Take the average of the TOP 3 matched technology scores
    - This prevents score inflation from long but shallow lists
    """
    if not project.skills_used:
        return DEFAULT_STACK_SCORE

    # Build a lowercased lookup from the dataset
    raw_map: dict[str, float] = {}
    for tech, score in datasets.stack_sophistication_mapping.items():
        raw_map[tech.lower()] = float(score)

    # Also check aliases
    alias_map = {k.lower(): v.lower() for k, v in datasets.stack_aliases.items()}

    matched_scores: list[float] = []
    for skill in project.skills_used:
        skill_lower = skill.lower()
        # Direct lookup
        if skill_lower in raw_map:
            matched_scores.append(raw_map[skill_lower])
            continue
        # Alias resolution
        resolved = alias_map.get(skill_lower, skill_lower)
        if resolved in raw_map:
            matched_scores.append(raw_map[resolved])

    if not matched_scores:
        return DEFAULT_STACK_SCORE

    # Top-3 average to avoid inflation
    top_scores = sorted(matched_scores, reverse=True)[:3]
    return float(np.mean(top_scores))


# ---------------------------------------------------------------------------
# Project relevance  (domain matching)
# ---------------------------------------------------------------------------

def _project_relevance_score(
    project: PRSProject,
    target_role: str,
    datasets: PRSDatasets,
    llm_domains: list[str],
) -> float:
    """
    Score how relevant a project is to the target role using:
    1. Direct role_alignment field in projects_dataset (exact match)
    2. Domain matching via role_domain_mapping
    3. Semantic embedding similarity between project text and role domains

    Returns 0-100.
    """
    role_domains: list[str] = datasets.role_domain_mapping.get(target_role, [])

    # ---- Check projects_dataset for a template match ----
    # (User's project may loosely match a reference project for the role)
    for ref_proj in datasets.projects_dataset:
        if target_role in ref_proj.get("role_alignment", []):
            # Check if the user project uses similar primary skills
            ref_skills = set(s.lower() for s in ref_proj.get("primary_skills", []))
            user_skills = set(s.lower() for s in project.skills_used)
            overlap = len(ref_skills & user_skills)
            if overlap >= 2:
                # Good skill overlap with a relevant reference project
                return min(100.0, 60.0 + overlap * 8.0)

    # ---- Domain matching via LLM-classified domains ----
    if llm_domains and role_domains:
        role_domains_lower = {d.lower() for d in role_domains}
        for d in llm_domains:
            if d.lower() in role_domains_lower:
                return 85.0
        # Partial word overlap check
        for d in llm_domains:
            for rd in role_domains:
                if any(word in rd.lower() for word in d.lower().split() if len(word) > 3):
                    return 65.0

    # ---- Semantic embedding similarity ----
    if role_domains:
        try:
            from app.services.embeddings import model as _bge_model

            # Build a rich project text for embedding
            proj_parts = [project.name]
            if project.description:
                proj_parts.append(project.description[:200])
            if project.skills_used:
                proj_parts.append(", ".join(project.skills_used[:8]))
            project_text = " ".join(proj_parts)

            role_domain_text = " ".join(role_domains)

            embs = _bge_model.encode(
                [project_text, role_domain_text],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            sim = float(np.dot(embs[0], embs[1]))
            if sim >= RELEVANCE_SIM_THRESHOLD:
                return round(min(100.0, sim * 100.0), 1)

        except Exception as exc:
            print(f"[ProjectsEngine] Embedding relevance failed: {exc}")

    # ---- Minimal base score (at least the user has projects) ----
    return 25.0


# ---------------------------------------------------------------------------
# Single project scorer
# ---------------------------------------------------------------------------

def _score_single_project(
    project: PRSProject,
    target_role: str,
    answers: dict[str, Any],
    datasets: PRSDatasets,
    llm_result: dict[str, Any] | None,
) -> ProjectScore:
    """
    Score one project.

    Parameters
    ----------
    llm_result : dict or None
        Result from Gemini for this project: {name, domains, complexity_score, rationale}
    """
    # ---- Complexity ----
    if llm_result and "complexity_score" in llm_result:
        # Blend LLM complexity with assessment-based complexity
        llm_complexity = float(llm_result["complexity_score"])
        assessment_complexity = _assessment_complexity_score(answers)
        complexity = (llm_complexity * 0.60) + (assessment_complexity * 0.40)
        llm_classified = True
    else:
        complexity = _assessment_complexity_score(answers)
        llm_classified = False

    # ---- Tech stack sophistication ----
    tech_soph = _tech_sophistication_score(project, datasets)

    # ---- Deployment exposure ----
    deployment = _deployment_score(answers)

    # ---- Project quality ----
    quality_score = (
        (complexity   * 0.45)
      + (tech_soph    * 0.35)
      + (deployment   * 0.20)
    )
    quality_score = max(0.0, min(100.0, quality_score))

    # ---- Relevance ----
    llm_domains = llm_result.get("domains", []) if llm_result else []
    relevance_score = _project_relevance_score(
        project, target_role, datasets, llm_domains
    )

    # ---- Final project score ----
    final = (quality_score * 0.75) + (relevance_score * 0.25)
    final = max(0.0, min(100.0, final))

    return ProjectScore(
        project_name=project.name,
        quality_score=round(quality_score, 2),
        relevance_score=round(relevance_score, 2),
        final_score=round(final, 2),
        complexity=round(complexity, 2),
        tech_sophistication=round(tech_soph, 2),
        domain_match=round(relevance_score, 2),
        llm_classified=llm_classified,
    )


# ---------------------------------------------------------------------------
# Multi-project aggregation
# ---------------------------------------------------------------------------

def _aggregate_project_scores(scored_projects: list[ProjectScore]) -> float:
    """
    Aggregate top-3 project scores with weighted formula:
      best -> 50%, second -> 30%, third -> 20%

    Sorts by final_score descending before applying weights.
    """
    if not scored_projects:
        return 0.0

    sorted_scores = sorted(scored_projects, key=lambda p: p.final_score, reverse=True)
    top = sorted_scores[:3]

    weights = PROJECT_AGG_WEIGHTS[: len(top)]
    # Renormalize weights to sum to 1 (in case we have fewer than 3 projects)
    weight_sum = sum(weights)
    weights = [w / weight_sum for w in weights]

    return float(sum(p.final_score * w for p, w in zip(top, weights)))


# ---------------------------------------------------------------------------
# Experience score
# ---------------------------------------------------------------------------

def _experience_score(answers: dict[str, Any], prs_input: PRSInput) -> dict[str, float]:
    """
    experience_score =
        (experience_duration_score    x 0.40)
      + (experience_role_relevance    x 0.30)
      + (engineering_workflow_exposure x 0.30)

    experience_duration_score: Q4 answer
    experience_role_relevance : derived from saved profile experience list
                                 + Q4 (if they have relevant duration, we trust it)
    engineering_workflow_exposure: Q3 additive score
    """
    # -- Duration (Q4) --
    duration_code = _get_answer(answers, "relevant_experience_duration", "none")
    duration_score = DURATION_SCORES.get(duration_code, 0.0)

    # -- Role relevance: use saved profile experience count as a signal --
    # If the user listed real experience entries and Q4 says they have
    # relevant experience, give full relevance credit; otherwise partial.
    exp_entries = prs_input.experience
    has_experience_entries = bool(exp_entries)

    if duration_code in ("1_2_years", "2_plus_years"):
        role_relevance = 90.0
    elif duration_code == "6_12_months":
        role_relevance = 70.0 if has_experience_entries else 55.0
    elif duration_code == "less_6_months":
        role_relevance = 45.0 if has_experience_entries else 30.0
    else:
        role_relevance = 10.0 if has_experience_entries else 0.0

    # -- Engineering workflow (Q3) --
    practices = _get_multi_answer(answers, "engineering_practices")
    if "none" in practices or not practices:
        workflow_score = 0.0
    else:
        raw = sum(PRACTICE_SCORES.get(p, 0.0) for p in practices)
        workflow_score = min(100.0, raw)

    exp_score = (
        (duration_score   * 0.40)
      + (role_relevance   * 0.30)
      + (workflow_score   * 0.30)
    )

    return {
        "experience_score": round(exp_score, 2),
        "duration_score": round(duration_score, 2),
        "role_relevance": round(role_relevance, 2),
        "workflow_score": round(workflow_score, 2),
        "practices": practices,
        "duration_code": duration_code,
    }


# ---------------------------------------------------------------------------
# Weak area detection
# ---------------------------------------------------------------------------

def _detect_weak_areas(
    final_project_score: float,
    exp_breakdown: dict[str, float],
    answers: dict[str, Any],
) -> list[str]:
    weak: list[str] = []

    if final_project_score < 40.0:
        weak.append("Low project quality or relevance")

    deployment = _deployment_score(answers)
    if deployment == 0.0:
        weak.append("No deployment experience")
    elif deployment <= 40.0:
        weak.append("Projects not deployed beyond local environment")

    if exp_breakdown["workflow_score"] < 30.0:
        weak.append("Limited engineering workflow practices (testing, CI/CD, code reviews)")

    if exp_breakdown["duration_score"] < 35.0:
        weak.append("Minimal role-relevant practical experience")

    ownership_code = _get_answer(answers, "project_ownership", "tutorial_minor_changes")
    if ownership_code in ("tutorial_minor_changes",):
        weak.append("Most project work is tutorial-based rather than independent")

    return weak


# ---------------------------------------------------------------------------
# Public engine function
# ---------------------------------------------------------------------------

def calculate_projects_experience(
    prs_input: PRSInput,
    datasets: PRSDatasets,
) -> ProjectsExperienceResult:
    """
    Calculate the Projects + Experience pillar score.

    Parameters
    ----------
    prs_input : PRSInput
        Normalized PRS input from input_builder.
    datasets : PRSDatasets
        Loaded PRS datasets from dataset_loader.

    Returns
    -------
    ProjectsExperienceResult
        Full breakdown including per-project scores and experience sub-scores.
    """
    answers = prs_input.assessment_answers
    target_role = prs_input.target_role
    projects = prs_input.projects

    # ---- Step 1: LLM classification (one batch call) ----
    llm_results: list[dict[str, Any]] = []
    if projects:
        llm_results = _llm_classify_projects(projects, target_role)

    # Build a name->result lookup for LLM results
    llm_lookup: dict[str, dict[str, Any]] = {}
    for llm_item in llm_results:
        name = llm_item.get("name", "").strip().lower()
        if name:
            llm_lookup[name] = llm_item

    # ---- Step 1b: Deterministic classification when LLM unavailable ----
    # Runs for every project that the LLM did not classify (empty llm_lookup
    # is the common case in PRS_DETERMINISTIC_MODE or when Gemini fails).
    det_lookup: dict[str, dict[str, Any]] = {}
    if projects and not llm_lookup:
        for project in projects:
            det_result = _deterministic_classify_project(
                project=project,
                target_role=target_role,
                answers=answers,
                datasets=datasets,
            )
            det_lookup[project.name.strip().lower()] = det_result

    # ---- Step 2: Score each project individually ----
    scored_projects: list[ProjectScore] = []
    for project in projects:
        # Prefer LLM result, then deterministic result, then None
        proj_key = project.name.strip().lower()
        llm_match = llm_lookup.get(proj_key) or det_lookup.get(proj_key)
        ps = _score_single_project(
            project=project,
            target_role=target_role,
            answers=answers,
            datasets=datasets,
            llm_result=llm_match,
        )
        scored_projects.append(ps)

    # ---- Step 3: Handle no-projects case ----
    # If user has no saved projects, fall back entirely to assessment signals
    if not scored_projects:
        # Use assessment-only project proxy
        assessment_complexity = _assessment_complexity_score(answers)
        deployment = _deployment_score(answers)
        # Build a synthetic project quality (no real projects means no tech sophistication)
        synthetic_quality = (assessment_complexity * 0.60) + (deployment * 0.40)
        final_project_score = synthetic_quality * 0.50  # Penalty for no portfolio evidence
    else:
        final_project_score = _aggregate_project_scores(scored_projects)

    # ---- Step 4: Experience score ----
    exp_breakdown = _experience_score(answers, prs_input)
    exp_score = exp_breakdown["experience_score"]

    # ---- Step 5: Final pillar score ----
    pillar_score = (
        (final_project_score * 0.80)
      + (exp_score           * 0.20)
    )
    pillar_score = max(0.0, min(100.0, pillar_score))

    # ---- Step 6: Weak areas ----
    weak_areas = _detect_weak_areas(final_project_score, exp_breakdown, answers)

    # ---- Serialise project scores ----
    project_score_dicts = [
        {
            "project_name":      ps.project_name,
            "final_score":       ps.final_score,
            "quality_score":     ps.quality_score,
            "relevance_score":   ps.relevance_score,
            "complexity":        ps.complexity,
            "tech_sophistication": ps.tech_sophistication,
            "llm_classified":    ps.llm_classified,
        }
        for ps in scored_projects
    ]

    breakdown = {
        "final_project_score":  round(final_project_score, 2),
        "experience_score":     round(exp_score, 2),
        "project_count":        len(scored_projects),
        "experience_breakdown": exp_breakdown,
        "llm_available":        bool(llm_results),
        "formula": {
            "pillar": "final_project_score*0.80 + experience_score*0.20",
            "project": "quality*0.75 + relevance*0.25",
            "quality": "complexity*0.45 + tech_soph*0.35 + deployment*0.20",
        },
    }

    return ProjectsExperienceResult(
        score=round(pillar_score, 2),
        final_project_score=round(final_project_score, 2),
        experience_score=round(exp_score, 2),
        project_scores=project_score_dicts,
        weak_areas=weak_areas,
        breakdown=breakdown,
    )
