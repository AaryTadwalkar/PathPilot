"""
Phase 8 -- Certificate Quality Engine
=======================================
Evaluates the credibility and relevance of the user's certificates
for the selected target role.

Formula:
    certificate_quality_score =
        (industry_credibility x 0.40)
      + (role_relevance       x 0.35)
      + (skill_depth          x 0.25)

Pipeline per certificate:
    1. Normalize name (alias resolution -> canonical)
    2. Dataset lookup (exact / alias match against certificates_dataset)
    3. Provider credibility score  (certificate_provider_scores)
    4. Role relevance  (role_alignment field + semantic embedding similarity)
    5. Skill depth     (certificate_level_mapping + skills_covered overlap)
    6. Per-cert score  = credibility*0.40 + relevance*0.35 + depth*0.25

Multiple-certificate aggregation:
    Top-3 relevant certificates, weighted:
        best   -> 50%
        second -> 30%
        third  -> 20%

    Prevents dozens of beginner badges from inflating the score.

No-certificate state:
    Returns score=0, no error.

Fallback provider score:
    If a provider is not in the dataset, "Unknown" score (50) is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.services.prs.dataset_loader import PRSDatasets
from app.services.prs.input_builder import PRSInput

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Aggregation weights for top-3 certificates
CERT_AGG_WEIGHTS = [0.50, 0.30, 0.20]

# Minimum cosine similarity to consider a semantic role-relevance match
SEMANTIC_ROLE_SIM_THRESHOLD = 0.65

# Default provider score when provider is completely unknown
DEFAULT_PROVIDER_SCORE = 50.0

# Pillar formula weights
W_CREDIBILITY = 0.40
W_RELEVANCE   = 0.35
W_DEPTH       = 0.25


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CertScore:
    """Scores for one resolved certificate."""
    raw_name: str               # exactly as the user wrote it
    canonical_name: str         # after alias resolution
    matched_dataset: bool       # True if found in certificates_dataset
    provider: str
    provider_score: float       # 0-100
    level_score: float          # 0-100 from certificate_level_mapping
    role_relevance: float       # 0-100
    skill_depth: float          # 0-100  (level_score + skills overlap)
    cert_score: float           # 0-100 final per-cert score


@dataclass
class CertificateQualityResult:
    """Complete output of the Certificate Quality Engine."""
    score: float                        # 0-100 pillar score
    certificate_scores: list[dict[str, Any]]
    no_certificates: bool
    weak_areas: list[str]
    breakdown: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score":               round(self.score, 2),
            "certificate_scores":  self.certificate_scores,
            "no_certificates":     self.no_certificates,
            "weak_areas":          self.weak_areas,
            "breakdown":           self.breakdown,
        }


# ---------------------------------------------------------------------------
# Name normalisation & alias resolution
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    return text.strip().lower()


def _resolve_cert_alias(raw: str, cert_aliases: dict[str, str], max_hops: int = 3) -> str:
    """
    Walk the certificate alias chain up to max_hops to reach a canonical name.
    Returns the canonical name (still lower-cased for comparison).
    """
    current = _norm(raw)
    for _ in range(max_hops):
        if current in cert_aliases:
            current = _norm(cert_aliases[current])
        else:
            break
    return current


def _build_cert_alias_lookup(datasets: PRSDatasets) -> dict[str, str]:
    """
    Build a flat {normalised_alias: normalised_canonical} dict from
    datasets.certificate_aliases.
    """
    return {_norm(k): _norm(v) for k, v in datasets.certificate_aliases.items()}


# ---------------------------------------------------------------------------
# Dataset lookup
# ---------------------------------------------------------------------------

def _find_in_dataset(
    canonical: str,
    datasets: PRSDatasets,
) -> dict[str, Any] | None:
    """
    Exact / alias match against certificates_dataset.

    Tries:
      1. Exact lowercase match on certificate_name
      2. Partial substring match (canonical is a substring of cert name or vice-versa)
    """
    for entry in datasets.certificates_dataset:
        entry_norm = _norm(entry.get("certificate_name", ""))
        if entry_norm == canonical:
            return entry
        # Substring check (handles abbreviated names)
        if canonical in entry_norm or entry_norm in canonical:
            return entry
    return None


# ---------------------------------------------------------------------------
# Provider credibility
# ---------------------------------------------------------------------------

def _infer_provider(cert_name: str, datasets: PRSDatasets) -> str:
    """
    Infer provider name from the certificate name when not available from
    the dataset.  Checks if any known provider appears in the cert name.
    """
    cert_lower = cert_name.lower()
    for provider in datasets.certificate_provider_scores:
        if provider.lower() in cert_lower:
            return provider
    return "Unknown"


def _provider_score(provider: str, datasets: PRSDatasets) -> float:
    """Return credibility score for a provider (0-100)."""
    # Direct match
    score = datasets.certificate_provider_scores.get(provider)
    if score is not None:
        return float(score)
    # Case-insensitive search
    for prov, s in datasets.certificate_provider_scores.items():
        if prov.lower() == provider.lower():
            return float(s)
    return DEFAULT_PROVIDER_SCORE


# ---------------------------------------------------------------------------
# Level / depth score
# ---------------------------------------------------------------------------

def _level_score(level_str: str, datasets: PRSDatasets) -> float:
    """
    Map a certificate level string to a depth score using
    certificate_level_mapping.  Returns 50 for unknown levels.
    """
    if not level_str:
        return float(datasets.certificate_level_mapping.get("unknown", 50))
    level_norm = _norm(level_str)
    score = datasets.certificate_level_mapping.get(level_norm)
    if score is not None:
        return float(score)
    # Fallback partial match
    for lvl, s in datasets.certificate_level_mapping.items():
        if lvl in level_norm or level_norm in lvl:
            return float(s)
    return float(datasets.certificate_level_mapping.get("unknown", 50))


# ---------------------------------------------------------------------------
# Role relevance
# ---------------------------------------------------------------------------

def _role_relevance_score(
    cert_entry: dict[str, Any] | None,
    raw_cert_name: str,
    target_role: str,
    datasets: PRSDatasets,
) -> float:
    """
    Compute role relevance for a certificate.

    Strategy (ordered):
    1. If found in dataset: check role_alignment list directly (fast path)
    2. Semantic embedding: embed (cert skills covered) vs (role required skills)
    3. Fallback: 30 (neutral — certificate exists but relevance unclear)
    """
    # ---- 1. Dataset role_alignment direct check ----
    if cert_entry:
        role_alignment: list[str] = cert_entry.get("role_alignment", [])
        if target_role in role_alignment:
            return 100.0
        # Close match: partial role name overlap
        target_lower = target_role.lower()
        for aligned_role in role_alignment:
            if aligned_role.lower() in target_lower or target_lower in aligned_role.lower():
                return 75.0

    # ---- 2. Semantic embedding similarity ----
    try:
        from app.services.embeddings import model as _bge_model

        # Build rich cert text: name + skills covered
        cert_skills = cert_entry.get("skills_covered", []) if cert_entry else []
        cert_text = raw_cert_name
        if cert_skills:
            cert_text += " " + " ".join(cert_skills[:8])

        # Build rich role text: role name + required skills
        role_entry = next(
            (e for e in datasets.role_skill_mapping if e.get("role") == target_role),
            None,
        )
        role_skills = [s["skill_name"] for s in role_entry.get("skills", [])] if role_entry else []
        role_text = target_role
        if role_skills:
            role_text += " " + " ".join(role_skills[:8])

        embs = _bge_model.encode(
            [cert_text, role_text],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        sim = float(np.dot(embs[0], embs[1]))

        if sim >= SEMANTIC_ROLE_SIM_THRESHOLD:
            return round(min(100.0, sim * 100.0), 1)
        # Partial relevance for weaker similarity
        if sim >= 0.45:
            return round(sim * 80.0, 1)

    except Exception as exc:
        print(f"[CertEngine] Embedding relevance failed: {exc}")

    # ---- 3. Fallback ----
    return 30.0


# ---------------------------------------------------------------------------
# Skill depth
# ---------------------------------------------------------------------------

def _skill_depth_score(
    cert_entry: dict[str, Any] | None,
    level_score: float,
    target_role: str,
    datasets: PRSDatasets,
) -> float:
    """
    skill_depth = (level_score x 0.60) + (skills_overlap x 0.40)

    skills_overlap: how many certificate skills match the role's required skills.
    """
    if cert_entry is None:
        # No dataset match: use only the level score (already uncertain)
        return level_score * 0.60 + 30.0 * 0.40  # neutral overlap

    # Skills overlap between cert skills_covered and role required skills
    cert_skills_norm = {_norm(s) for s in cert_entry.get("skills_covered", [])}
    role_entry = next(
        (e for e in datasets.role_skill_mapping if e.get("role") == target_role),
        None,
    )
    if role_entry:
        role_skills_norm = {_norm(s["skill_name"]) for s in role_entry.get("skills", [])}
        if role_skills_norm:
            overlap_ratio = len(cert_skills_norm & role_skills_norm) / len(role_skills_norm)
            overlap_score = min(100.0, overlap_ratio * 100.0)
        else:
            overlap_score = 30.0
    else:
        overlap_score = 30.0

    return round((level_score * 0.60) + (overlap_score * 0.40), 2)


# ---------------------------------------------------------------------------
# Score a single certificate
# ---------------------------------------------------------------------------

def _score_single_cert(
    raw_name: str,
    target_role: str,
    datasets: PRSDatasets,
    alias_lookup: dict[str, str],
) -> CertScore:
    """
    Score one certificate through the full pipeline:
      Normalize -> Dataset lookup -> Credibility -> Relevance -> Depth
    """
    # ---- Normalise ----
    canonical = _resolve_cert_alias(raw_name, alias_lookup)

    # ---- Dataset lookup ----
    entry = _find_in_dataset(canonical, datasets)

    # ---- Provider ----
    if entry:
        provider = entry.get("provider", _infer_provider(raw_name, datasets))
    else:
        provider = _infer_provider(raw_name, datasets)

    cred_score = _provider_score(provider, datasets)

    # ---- Level / depth ----
    level_str = entry.get("certificate_level", "") if entry else ""
    lvl_score = _level_score(level_str, datasets)

    # ---- Role relevance ----
    rel_score = _role_relevance_score(entry, raw_name, target_role, datasets)

    # ---- Skill depth ----
    depth_score = _skill_depth_score(entry, lvl_score, target_role, datasets)

    # ---- Per-cert final score ----
    cert_score = (
        (cred_score * W_CREDIBILITY)
      + (rel_score  * W_RELEVANCE)
      + (depth_score * W_DEPTH)
    )
    cert_score = max(0.0, min(100.0, cert_score))

    return CertScore(
        raw_name=raw_name,
        canonical_name=canonical,
        matched_dataset=entry is not None,
        provider=provider,
        provider_score=round(cred_score, 2),
        level_score=round(lvl_score, 2),
        role_relevance=round(rel_score, 2),
        skill_depth=round(depth_score, 2),
        cert_score=round(cert_score, 2),
    )


# ---------------------------------------------------------------------------
# Multi-certificate aggregation
# ---------------------------------------------------------------------------

def _aggregate_cert_scores(cert_scores: list[CertScore]) -> float:
    """
    Top-3 by cert_score, weighted 50/30/20.
    Re-normalises weights if fewer than 3 certs.
    """
    if not cert_scores:
        return 0.0

    sorted_certs = sorted(cert_scores, key=lambda c: c.cert_score, reverse=True)
    top = sorted_certs[:3]
    weights = CERT_AGG_WEIGHTS[: len(top)]
    weight_sum = sum(weights)
    weights = [w / weight_sum for w in weights]

    return float(sum(c.cert_score * w for c, w in zip(top, weights)))


# ---------------------------------------------------------------------------
# Weak area detection
# ---------------------------------------------------------------------------

def _detect_weak_areas(
    cert_scores: list[CertScore],
    aggregated: float,
    target_role: str,
) -> list[str]:
    weak: list[str] = []

    if not cert_scores:
        weak.append("No certificates detected in profile")
        return weak

    # Check if any cert is relevant to the target role
    relevant = [c for c in cert_scores if c.role_relevance >= 60.0]
    if not relevant:
        weak.append(f"No certificates directly relevant to {target_role}")

    # Check for low-credibility certs only
    high_cred = [c for c in cert_scores if c.provider_score >= 75.0]
    if not high_cred:
        weak.append("All certificates are from lower-credibility providers")

    # Beginner-only warning
    advanced = [c for c in cert_scores if c.level_score >= 60.0]
    if not advanced:
        weak.append("Only beginner-level certificates found — no intermediate/advanced certificates")

    if aggregated < 40.0 and cert_scores:
        weak.append("Overall certificate quality is low for the selected role")

    return weak


# ---------------------------------------------------------------------------
# Public engine function
# ---------------------------------------------------------------------------

def calculate_certificate_quality(
    prs_input: PRSInput,
    datasets: PRSDatasets,
) -> CertificateQualityResult:
    """
    Calculate the Certificate Quality pillar score.

    Parameters
    ----------
    prs_input : PRSInput
        Normalized PRS input from input_builder.
    datasets : PRSDatasets
        Loaded PRS datasets from dataset_loader.

    Returns
    -------
    CertificateQualityResult
        Full breakdown including per-certificate scores.
    """
    certs = prs_input.certifications
    target_role = prs_input.target_role

    # ---- No certificates ----
    if not certs:
        return CertificateQualityResult(
            score=0.0,
            certificate_scores=[],
            no_certificates=True,
            weak_areas=["No certificates detected in profile"],
            breakdown={
                "cert_count": 0,
                "aggregated_score": 0.0,
                "formula": "credibility*0.40 + role_relevance*0.35 + skill_depth*0.25",
            },
        )

    # ---- Build alias lookup once ----
    alias_lookup = _build_cert_alias_lookup(datasets)

    # ---- Score each certificate ----
    cert_scores: list[CertScore] = []
    for raw_name in certs:
        if not raw_name or not raw_name.strip():
            continue
        cs = _score_single_cert(raw_name, target_role, datasets, alias_lookup)
        cert_scores.append(cs)

    if not cert_scores:
        return CertificateQualityResult(
            score=0.0,
            certificate_scores=[],
            no_certificates=True,
            weak_areas=["No valid certificates could be scored"],
            breakdown={"cert_count": 0, "aggregated_score": 0.0},
        )

    # ---- Aggregate top-3 ----
    aggregated = _aggregate_cert_scores(cert_scores)
    aggregated = max(0.0, min(100.0, aggregated))

    # ---- Weak areas ----
    weak_areas = _detect_weak_areas(cert_scores, aggregated, target_role)

    # ---- Serialise ----
    cert_score_dicts = [
        {
            "raw_name":        cs.raw_name,
            "canonical_name":  cs.canonical_name,
            "matched_dataset": cs.matched_dataset,
            "provider":        cs.provider,
            "provider_score":  cs.provider_score,
            "level_score":     cs.level_score,
            "role_relevance":  cs.role_relevance,
            "skill_depth":     cs.skill_depth,
            "cert_score":      cs.cert_score,
        }
        for cs in cert_scores
    ]

    breakdown = {
        "cert_count":       len(cert_scores),
        "aggregated_score": round(aggregated, 2),
        "top_cert":         cert_scores[0].raw_name if cert_scores else None,
        "formula": {
            "per_cert": "credibility*0.40 + role_relevance*0.35 + skill_depth*0.25",
            "aggregation": "top3: best*0.50 + second*0.30 + third*0.20",
        },
    }

    return CertificateQualityResult(
        score=round(aggregated, 2),
        certificate_scores=cert_score_dicts,
        no_certificates=False,
        weak_areas=weak_areas,
        breakdown=breakdown,
    )
