"""
Phase 6 — Skill Readiness Engine
==================================
Calculates the role-specific technical capability score (0-100).

Matching pipeline (in order of priority):
  1. Exact match          (case-insensitive)
  2. Alias match          (dataset aliases + per-skill aliases from skills_master)
  3. Embedding similarity (BGE cosine similarity)
  4. Skill cluster validation

Semantic thresholds:
  >= 0.85   → Strong Match  (match_score = similarity)
  0.75-0.85 → Valid Match   (match_score = similarity)
  0.60-0.75 → Weak Partial  (match_score = similarity * 0.5)
  < 0.60    → Ignore

Importance weight formula:
  importance_weight =
      (role_criticality_score × 0.40)
    + (industry_demand_score  × 0.25)
    + (practical_impact_score × 0.20)
    + (foundational_score     × 0.15)

Final skill readiness formula:
  skill_readiness_score =
      (sum(skill_contributions) / sum(all_importance_weights)) × 100
  where
      skill_contribution = importance_weight × match_score
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.services.prs.dataset_loader import PRSDatasets
from app.services.prs.input_builder import PRSInput

# ──────────────────────────────────────────────────────────────────────────────
# Score tables (from the specification)
# ──────────────────────────────────────────────────────────────────────────────

ROLE_CRITICALITY_SCORES: dict[str, float] = {
    "critical":  10.0,
    "very_high":  9.0,
    "high":       7.0,
    "important":  7.0,   # dataset uses "important" as alias for "high"
    "medium":     5.0,
    "low":        3.0,
}

INDUSTRY_DEMAND_SCORES: dict[str, float] = {
    "very_high": 10.0,
    "high":       8.0,
    "medium":     6.0,
    "low":        4.0,
}

PRACTICAL_IMPACT_SCORES: dict[str, float] = {
    "very_high": 10.0,
    "high":       8.0,
    "medium":     6.0,
    "low":        4.0,
}

FOUNDATIONAL_TYPE_SCORES: dict[str, float] = {
    "foundational":    10.0,
    "supporting":       7.0,
    "advanced_bonus":   5.0,
    "specialized":      5.0,   # dataset uses "specialized" → maps to advanced_bonus tier
}

# Semantic similarity thresholds
THRESHOLD_STRONG  = 0.85
THRESHOLD_VALID   = 0.75
THRESHOLD_PARTIAL = 0.60

# Weak-partial penalty (contribution is dampened)
WEAK_PARTIAL_FACTOR = 0.50


# ──────────────────────────────────────────────────────────────────────────────
# Output dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SkillMatchDetail:
    """Per-required-skill breakdown for explainability."""
    role_skill: str
    match_type: str          # "exact" | "alias" | "semantic_strong" | "semantic_valid" | "partial" | "unmatched"
    matched_user_skill: str | None
    similarity: float        # cosine similarity (or 1.0 for exact/alias)
    match_score: float       # effective contribution weight (0.0 – 1.0)
    importance_weight: float


@dataclass
class SkillReadinessResult:
    """Complete output of the Skill Readiness Engine."""
    score: float                                    # 0–100
    matched_skills: list[str]                       # strong + valid matches
    partial_matches: list[str]                      # weak partial matches
    missing_skills: list[str]                       # unmatched required skills
    match_details: list[dict[str, Any]]             # full SkillMatchDetail dicts
    total_importance_weight: float
    total_contribution: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "matched_skills": self.matched_skills,
            "partial_matches": self.partial_matches,
            "missing_skills": self.missing_skills,
            "match_details": self.match_details,
            "total_importance_weight": round(self.total_importance_weight, 4),
            "total_contribution": round(self.total_contribution, 4),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Lazy embedding helper (imports SentenceTransformer only once)
# ──────────────────────────────────────────────────────────────────────────────

_model_cache: Any = None


def _get_model():
    """Return the shared BGE model (singleton loaded on first call)."""
    global _model_cache
    if _model_cache is None:
        from app.services.embeddings import model as _bge_model
        _model_cache = _bge_model
    return _model_cache


def _embed(texts: list[str]) -> np.ndarray:
    """Encode a list of texts into L2-normalised embeddings."""
    model = _get_model()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity for already-normalised vectors (dot product)."""
    return float(np.dot(a, b))


# ──────────────────────────────────────────────────────────────────────────────
# Importance weight calculation
# ──────────────────────────────────────────────────────────────────────────────

def _importance_weight(skill_entry: dict[str, Any]) -> float:
    """
    importance_weight =
        (role_criticality_score × 0.40)
      + (industry_demand_score  × 0.25)
      + (practical_impact_score × 0.20)
      + (foundational_score     × 0.15)
    """
    rc = ROLE_CRITICALITY_SCORES.get(
        str(skill_entry.get("role_criticality", "")).lower(), 5.0
    )
    id_ = INDUSTRY_DEMAND_SCORES.get(
        str(skill_entry.get("industry_demand", "")).lower(), 6.0
    )
    pi = PRACTICAL_IMPACT_SCORES.get(
        str(skill_entry.get("practical_impact", "")).lower(), 6.0
    )
    ft = FOUNDATIONAL_TYPE_SCORES.get(
        str(skill_entry.get("foundational_type", "")).lower(), 7.0
    )
    return (rc * 0.40) + (id_ * 0.25) + (pi * 0.20) + (ft * 0.15)


# ──────────────────────────────────────────────────────────────────────────────
# Normalisation helpers
# ──────────────────────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return text.strip().lower()


def _build_alias_lookup(datasets: PRSDatasets) -> dict[str, str]:
    """
    Build a flat alias → canonical_skill mapping from:
      1. aliases/skill_aliases.json
      2. skills_master.json per-skill aliases list
    Returned dict: {normalised_alias: normalised_canonical}
    """
    lookup: dict[str, str] = {}

    # From alias file
    for raw_alias, raw_target in datasets.skill_aliases.items():
        lookup[_norm(raw_alias)] = _norm(raw_target)

    # From skills_master inline aliases
    for entry in datasets.skills_master:
        canonical = _norm(entry.get("skill_name", ""))
        for alias in entry.get("aliases", []):
            alias_key = _norm(alias)
            if alias_key not in lookup:
                lookup[alias_key] = canonical

    return lookup


def _build_cluster_map(datasets: PRSDatasets) -> dict[str, str]:
    """
    Returns {normalised_skill_name: normalised_cluster} from skills_master.
    """
    return {
        _norm(e["skill_name"]): _norm(e.get("cluster", ""))
        for e in datasets.skills_master
        if e.get("skill_name")
    }


# ──────────────────────────────────────────────────────────────────────────────
# Matching pipeline
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_alias(raw: str, alias_lookup: dict[str, str]) -> str:
    """Walk the alias chain up to 3 hops to reach a canonical form."""
    current = _norm(raw)
    for _ in range(3):
        if current in alias_lookup:
            current = alias_lookup[current]
        else:
            break
    return current


def _match_single_role_skill(
    role_skill_name: str,
    user_skill_norms: list[str],           # normalised user skill names
    role_emb: np.ndarray,                  # pre-computed embedding for role_skill_name
    user_embs: np.ndarray,                 # pre-computed embeddings for user skills (N×D)
    alias_lookup: dict[str, str],
    cluster_map: dict[str, str],
) -> tuple[str, float, float]:
    """
    Match one required role skill against all user skills.

    Returns
    -------
    (match_type, similarity, match_score)
    match_score: effective 0.0 – 1.0 used in contribution formula
    """
    role_norm = _resolve_alias(role_skill_name, alias_lookup)

    # ── 1. Exact match ────────────────────────────────────────────────────────
    for user_norm in user_skill_norms:
        if _resolve_alias(user_norm, alias_lookup) == role_norm:
            return "exact", 1.0, 1.0

    # ── 2. Alias match (both sides normalised through alias chain) ────────────
    for user_norm in user_skill_norms:
        user_resolved = _resolve_alias(user_norm, alias_lookup)
        if user_resolved == role_norm:
            return "alias", 1.0, 1.0
        # Also check: does the user skill appear in the role skill's alias chain?
        if _norm(role_skill_name) in (user_norm, user_resolved):
            return "alias", 1.0, 1.0

    # ── 3. Embedding similarity ───────────────────────────────────────────────
    if len(user_embs) == 0:
        return "unmatched", 0.0, 0.0

    similarities = user_embs @ role_emb  # shape: (N,)
    best_idx = int(np.argmax(similarities))
    best_sim = float(similarities[best_idx])

    if best_sim >= THRESHOLD_STRONG:
        # 4. Cluster validation (optional bonus check — does not downgrade)
        role_cluster = cluster_map.get(role_norm, "")
        user_cluster = cluster_map.get(user_skill_norms[best_idx], "")
        match_type = "semantic_strong"
        if role_cluster and user_cluster and role_cluster == user_cluster:
            match_type = "semantic_strong_clustered"
        return match_type, best_sim, best_sim

    if best_sim >= THRESHOLD_VALID:
        return "semantic_valid", best_sim, best_sim

    if best_sim >= THRESHOLD_PARTIAL:
        return "partial", best_sim, best_sim * WEAK_PARTIAL_FACTOR

    return "unmatched", best_sim, 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Public engine function
# ──────────────────────────────────────────────────────────────────────────────

def calculate_skill_readiness(
    prs_input: PRSInput,
    datasets: PRSDatasets,
) -> SkillReadinessResult:
    """
    Calculate the Skill Readiness Score for the user's selected role.

    Parameters
    ----------
    prs_input : PRSInput
        Normalised PRS input built by input_builder.build_prs_input().
    datasets : PRSDatasets
        Loaded PRS datasets from dataset_loader.load_prs_datasets().

    Returns
    -------
    SkillReadinessResult
        Contains score (0–100), matched/partial/missing skill lists,
        and per-skill match details for full explainability.
    """
    target_role = prs_input.target_role

    # ── Find role skill mapping ───────────────────────────────────────────────
    role_entry = next(
        (e for e in datasets.role_skill_mapping if e.get("role") == target_role),
        None,
    )
    if role_entry is None:
        # No mapping → cannot score; return zero with explanation
        return SkillReadinessResult(
            score=0.0,
            matched_skills=[],
            partial_matches=[],
            missing_skills=[],
            match_details=[{"error": f"No skill mapping found for role: {target_role}"}],
            total_importance_weight=0.0,
            total_contribution=0.0,
        )

    required_skills: list[dict[str, Any]] = role_entry.get("skills", [])
    if not required_skills:
        return SkillReadinessResult(
            score=0.0,
            matched_skills=[],
            partial_matches=[],
            missing_skills=[],
            match_details=[],
            total_importance_weight=0.0,
            total_contribution=0.0,
        )

    # ── User skill preparation ────────────────────────────────────────────────
    user_skill_names = prs_input.skill_names  # list[str]
    if not user_skill_names:
        # No skills at all → all missing
        total_weight = sum(_importance_weight(s) for s in required_skills)
        return SkillReadinessResult(
            score=0.0,
            matched_skills=[],
            partial_matches=[],
            missing_skills=[s["skill_name"] for s in required_skills],
            match_details=[],
            total_importance_weight=total_weight,
            total_contribution=0.0,
        )

    user_skill_norms = [_norm(s) for s in user_skill_names]

    # ── Build lookup structures ───────────────────────────────────────────────
    alias_lookup = _build_alias_lookup(datasets)
    cluster_map = _build_cluster_map(datasets)

    # ── Pre-compute embeddings ────────────────────────────────────────────────
    # Role skills: one embedding per required skill
    role_skill_texts = [s["skill_name"] for s in required_skills]
    # User skills: one embedding per user skill
    all_texts = role_skill_texts + user_skill_names

    try:
        all_embs = _embed(all_texts)
        role_embs = all_embs[: len(role_skill_texts)]
        user_embs = all_embs[len(role_skill_texts) :]
    except Exception as exc:
        print(f"[SkillEngine] Embedding failed: {exc}. Falling back to text-only matching.")
        role_embs = np.zeros((len(role_skill_texts), 1))
        user_embs = np.zeros((len(user_skill_names), 1))

    # ── Match each required skill ─────────────────────────────────────────────
    total_weight   = 0.0
    total_contrib  = 0.0
    matched_skills : list[str] = []
    partial_matches: list[str] = []
    missing_skills : list[str] = []
    match_details  : list[dict[str, Any]] = []

    for idx, skill_entry in enumerate(required_skills):
        skill_name  = skill_entry["skill_name"]
        imp_weight  = _importance_weight(skill_entry)
        role_emb    = role_embs[idx]

        match_type, similarity, match_score = _match_single_role_skill(
            role_skill_name=skill_name,
            user_skill_norms=user_skill_norms,
            role_emb=role_emb,
            user_embs=user_embs,
            alias_lookup=alias_lookup,
            cluster_map=cluster_map,
        )

        contribution = imp_weight * match_score
        total_weight  += imp_weight
        total_contrib += contribution

        # Categorise
        if match_type == "unmatched":
            missing_skills.append(skill_name)
        elif match_type == "partial":
            partial_matches.append(skill_name)
        else:
            matched_skills.append(skill_name)

        match_details.append({
            "role_skill":         skill_name,
            "match_type":         match_type,
            "similarity":         round(similarity, 4),
            "match_score":        round(match_score, 4),
            "importance_weight":  round(imp_weight, 4),
            "contribution":       round(contribution, 4),
            "role_criticality":   skill_entry.get("role_criticality"),
            "industry_demand":    skill_entry.get("industry_demand"),
            "practical_impact":   skill_entry.get("practical_impact"),
            "foundational_type":  skill_entry.get("foundational_type"),
        })

    # ── Final score ───────────────────────────────────────────────────────────
    if total_weight > 0:
        raw_score = (total_contrib / total_weight) * 100.0
    else:
        raw_score = 0.0

    # Clamp to [0, 100]
    score = max(0.0, min(100.0, raw_score))

    return SkillReadinessResult(
        score=score,
        matched_skills=matched_skills,
        partial_matches=partial_matches,
        missing_skills=missing_skills,
        match_details=match_details,
        total_importance_weight=total_weight,
        total_contribution=total_contrib,
    )
