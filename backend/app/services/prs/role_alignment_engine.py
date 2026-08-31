"""
Phase 10 -- Role Alignment Engine
====================================
Measures how well the user's overall profile is oriented toward
the selected target role — coverage-focused, NOT depth-weighted
(that is Phase 6's job).

Formula:
    role_alignment_score =
        (skills_alignment   x 0.70)
      + (tech_stack_alignment x 0.30)

Skills alignment (coverage):
    skills_alignment =
        (matched_role_skills / total_role_skills) x 100

    A skill is "matched" if:
      1. Exact / alias match (case-insensitive)
      2. OR semantic embedding similarity >= SEMANTIC_MATCH_THRESHOLD

    This is intentionally simple coverage — no importance weighting
    (Phase 6 already handles that). Every role skill counts equally.

Tech stack alignment:
    tech_stack_alignment =
        (matched_stack_score / total_possible_stack_score) x 100

    Primary stack technologies contribute 1.0 weight each.
    Secondary stack technologies contribute 0.5 weight each.
    A technology is matched via:
      1. Exact / alias match
      2. OR embedding similarity >= SEMANTIC_MATCH_THRESHOLD

    This prevents a profile that only knows obscure tools from
    scoring as well as one that covers the canonical role stack.

Design intent:
    Role Alignment is about direction — does this person's toolkit
    point toward this role? It must produce DIFFERENT scores for
    different roles given the same profile, which is the Phase 10
    completion criterion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.services.prs.dataset_loader import PRSDatasets
from app.services.prs.input_builder import PRSInput

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

# Cosine similarity threshold for a semantic skill/tech match
SEMANTIC_MATCH_THRESHOLD = 0.78

# Stack weights: primary tech is more important than secondary
PRIMARY_WEIGHT   = 1.0
SECONDARY_WEIGHT = 0.5

# Pillar formula weights (spec-defined)
W_SKILLS_ALIGNMENT    = 0.70
W_TECH_STACK_ALIGNMENT = 0.30


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class RoleAlignmentResult:
    """Complete output of the Role Alignment Engine."""
    score: float                        # 0-100 pillar score
    skills_alignment: float             # 0-100 coverage score
    tech_stack_alignment: float         # 0-100 stack score
    matched_role_skills: list[str]      # role skills the user has
    unmatched_role_skills: list[str]    # role skills the user is missing
    matched_stack: list[str]            # stack techs the user has
    unmatched_stack: list[str]          # stack techs the user is missing
    weak_areas: list[str]
    breakdown: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score":                 round(self.score, 2),
            "skills_alignment":      round(self.skills_alignment, 2),
            "tech_stack_alignment":  round(self.tech_stack_alignment, 2),
            "matched_role_skills":   self.matched_role_skills,
            "unmatched_role_skills": self.unmatched_role_skills,
            "matched_stack":         self.matched_stack,
            "unmatched_stack":       self.unmatched_stack,
            "weak_areas":            self.weak_areas,
            "breakdown":             self.breakdown,
        }


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    return text.strip().lower()


def _resolve_alias(name: str, aliases: dict[str, str], max_hops: int = 3) -> str:
    """Walk the skill/stack alias chain to a canonical form."""
    current = _norm(name)
    for _ in range(max_hops):
        resolved = aliases.get(current)
        if resolved is None:
            break
        resolved_norm = _norm(resolved)
        if resolved_norm == current:
            break
        current = resolved_norm
    return current


def _build_alias_lookup(raw: dict[str, str]) -> dict[str, str]:
    """Lowercased alias -> lowercased canonical."""
    return {_norm(k): _norm(v) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# Lazy BGE embedding loader
# ---------------------------------------------------------------------------

def _get_embeddings(texts: list[str]) -> np.ndarray | None:
    """Return L2-normalised embeddings, or None if unavailable."""
    try:
        from app.services.embeddings import model as _bge_model
        return _bge_model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    except Exception as exc:
        print(f"[RoleAlignmentEngine] Embedding unavailable: {exc}")
        return None


# ---------------------------------------------------------------------------
# Core match function
# ---------------------------------------------------------------------------

def _matches_any(
    target: str,                    # normalised role skill / stack tech
    user_norms: set[str],           # normalised user skill names (with aliases resolved)
    user_embeddings: np.ndarray | None,
    target_embedding: np.ndarray | None,
) -> bool:
    """
    Return True if the user has a skill/tech that matches `target`.

    Match priority:
      1. Exact normalised match (cheapest)
      2. Semantic embedding cosine similarity >= threshold (richer)
    """
    # 1. Exact match
    if target in user_norms:
        return True

    # 2. Semantic match
    if user_embeddings is not None and target_embedding is not None:
        # cosine similarities between target and all user skill embeddings
        sims = user_embeddings @ target_embedding  # shape (n,)
        if float(sims.max()) >= SEMANTIC_MATCH_THRESHOLD:
            return True

    return False


# ---------------------------------------------------------------------------
# Skills alignment
# ---------------------------------------------------------------------------

def _compute_skills_alignment(
    prs_input: PRSInput,
    datasets: PRSDatasets,
    skill_alias_lookup: dict[str, str],
) -> tuple[float, list[str], list[str]]:
    """
    Returns (skills_alignment_score_0_100, matched_role_skills, unmatched_role_skills).

    Coverage-oriented: every role skill counts equally (no importance weighting).
    """
    role_entry = next(
        (e for e in datasets.role_skill_mapping if e.get("role") == prs_input.target_role),
        None,
    )
    if not role_entry:
        return 0.0, [], []

    role_skills: list[str] = [s["skill_name"] for s in role_entry.get("skills", [])]
    if not role_skills:
        return 0.0, [], []

    # Build normalised user skill set (alias-resolved)
    user_norms: set[str] = set()
    for skill_obj in prs_input.skills:
        raw_norm = _norm(skill_obj.skill)
        user_norms.add(raw_norm)
        user_norms.add(_resolve_alias(skill_obj.skill, skill_alias_lookup))

    # Embed user skills + each role skill for semantic matching
    all_texts = list(prs_input.skill_names) + role_skills
    all_embs = _get_embeddings(all_texts) if prs_input.skills else None

    n_user = len(prs_input.skills)
    user_embs  = all_embs[:n_user]  if all_embs is not None else None
    role_embs  = all_embs[n_user:]  if all_embs is not None else None

    matched: list[str] = []
    unmatched: list[str] = []

    for idx, role_skill in enumerate(role_skills):
        role_norm  = _resolve_alias(role_skill, skill_alias_lookup)
        role_emb   = role_embs[idx] if role_embs is not None else None

        if _matches_any(role_norm, user_norms, user_embs, role_emb):
            matched.append(role_skill)
        else:
            unmatched.append(role_skill)

    total = len(role_skills)
    score = (len(matched) / total) * 100.0 if total > 0 else 0.0

    return round(score, 2), matched, unmatched


# ---------------------------------------------------------------------------
# Tech stack alignment
# ---------------------------------------------------------------------------

def _compute_tech_stack_alignment(
    prs_input: PRSInput,
    datasets: PRSDatasets,
    stack_alias_lookup: dict[str, str],
) -> tuple[float, list[str], list[str]]:
    """
    Returns (tech_stack_alignment_score_0_100, matched_stack, unmatched_stack).

    Primary technologies weight 1.0, secondary weight 0.5.
    """
    stack_entry = next(
        (e for e in datasets.role_tech_stack_mapping if e.get("role") == prs_input.target_role),
        None,
    )
    if not stack_entry:
        return 0.0, [], []

    primary   = stack_entry.get("primary_stack", [])
    secondary = stack_entry.get("secondary_stack", [])

    if not primary and not secondary:
        return 0.0, [], []

    # Build normalised user skill set (skills + project tech)
    user_norms: set[str] = set()
    all_user_skills: list[str] = list(prs_input.skill_names)

    for skill_obj in prs_input.skills:
        raw_norm = _norm(skill_obj.skill)
        user_norms.add(raw_norm)
        user_norms.add(_resolve_alias(skill_obj.skill, stack_alias_lookup))

    # Also include technologies from project skills_used
    for proj in prs_input.projects:
        for tech in proj.skills_used:
            tech_norm = _norm(tech)
            user_norms.add(tech_norm)
            user_norms.add(_resolve_alias(tech, stack_alias_lookup))
            all_user_skills.append(tech)

    # Embed all techs at once
    all_stack_techs = primary + secondary
    all_texts = list(set(all_user_skills)) + all_stack_techs

    all_embs: np.ndarray | None = None
    if all_user_skills:
        all_embs = _get_embeddings(all_texts)

    n_user_unique = len(set(all_user_skills))
    user_embs = all_embs[:n_user_unique]  if all_embs is not None else None
    stack_embs = all_embs[n_user_unique:] if all_embs is not None else None

    matched: list[str] = []
    unmatched: list[str] = []

    total_possible  = 0.0
    matched_score   = 0.0

    stack_idx = 0
    for tech_list, weight in [(primary, PRIMARY_WEIGHT), (secondary, SECONDARY_WEIGHT)]:
        for tech in tech_list:
            tech_norm = _resolve_alias(tech, stack_alias_lookup)
            tech_emb  = stack_embs[stack_idx] if stack_embs is not None else None
            stack_idx += 1

            total_possible += weight
            if _matches_any(tech_norm, user_norms, user_embs, tech_emb):
                matched_score += weight
                matched.append(tech)
            else:
                unmatched.append(tech)

    score = (matched_score / total_possible) * 100.0 if total_possible > 0 else 0.0

    return round(score, 2), matched, unmatched


# ---------------------------------------------------------------------------
# Weak area detection
# ---------------------------------------------------------------------------

def _detect_weak_areas(
    skills_alignment: float,
    tech_stack_alignment: float,
    unmatched_role_skills: list[str],
    unmatched_stack: list[str],
    target_role: str,
) -> list[str]:
    weak: list[str] = []

    if skills_alignment < 40.0:
        weak.append(
            f"Low role alignment -- fewer than 40% of {target_role} core skills are present"
        )
    elif skills_alignment < 65.0:
        weak.append(
            f"Partial role alignment -- some key {target_role} skills are missing"
        )

    if tech_stack_alignment < 40.0:
        weak.append(
            f"Low tech stack alignment with {target_role} ecosystem"
        )

    # Surface the top missing skills (max 3)
    for skill in unmatched_role_skills[:3]:
        weak.append(f"Missing role skill: {skill}")

    return weak


# ---------------------------------------------------------------------------
# Public engine function
# ---------------------------------------------------------------------------

def calculate_role_alignment(
    prs_input: PRSInput,
    datasets: PRSDatasets,
) -> RoleAlignmentResult:
    """
    Calculate the Role Alignment pillar score.

    Parameters
    ----------
    prs_input : PRSInput
        Normalized PRS input from input_builder.
    datasets : PRSDatasets
        Loaded PRS datasets.

    Returns
    -------
    RoleAlignmentResult
        Coverage-oriented alignment breakdown.
    """
    # Build alias lookups once
    skill_alias_lookup = _build_alias_lookup(datasets.skill_aliases)
    stack_alias_lookup = _build_alias_lookup(datasets.stack_aliases)

    # ---- Skills alignment (0.70 weight) ----
    skills_align, matched_skills, unmatched_skills = _compute_skills_alignment(
        prs_input, datasets, skill_alias_lookup
    )

    # ---- Tech stack alignment (0.30 weight) ----
    stack_align, matched_stack, unmatched_stack = _compute_tech_stack_alignment(
        prs_input, datasets, stack_alias_lookup
    )

    # ---- Final pillar score ----
    score = (
        (skills_align * W_SKILLS_ALIGNMENT)
      + (stack_align  * W_TECH_STACK_ALIGNMENT)
    )
    score = max(0.0, min(100.0, score))

    # ---- Weak areas ----
    weak_areas = _detect_weak_areas(
        skills_align, stack_align, unmatched_skills, unmatched_stack, prs_input.target_role
    )

    breakdown = {
        "skills_alignment":     round(skills_align, 2),
        "tech_stack_alignment": round(stack_align, 2),
        "role_skill_coverage":  f"{len(matched_skills)}/{len(matched_skills) + len(unmatched_skills)}",
        "stack_coverage":       f"{len(matched_stack)}/{len(matched_stack) + len(unmatched_stack)}",
        "formula": "skills_alignment*0.70 + tech_stack_alignment*0.30",
        "note": "Coverage-oriented -- every role skill counted equally (no importance weighting)",
    }

    return RoleAlignmentResult(
        score=round(score, 2),
        skills_alignment=round(skills_align, 2),
        tech_stack_alignment=round(stack_align, 2),
        matched_role_skills=matched_skills,
        unmatched_role_skills=unmatched_skills,
        matched_stack=matched_stack,
        unmatched_stack=unmatched_stack,
        weak_areas=weak_areas,
        breakdown=breakdown,
    )
