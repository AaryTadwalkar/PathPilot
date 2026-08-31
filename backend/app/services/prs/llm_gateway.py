"""
Phase 15 -- LLM Structured Output Gateway
==========================================
Single entry point for ALL Gemini calls made by PRS engines.

Every call MUST:
  1. Define the expected output schema with Pydantic (clamp scores 0-100)
  2. Validate Gemini's raw text against the schema
  3. Retry up to MAX_RETRIES times on parse/validation failure
  4. Fall back to a deterministic sentinel value on persistent failure
  5. Never log sensitive resume text
  6. Cache results so unchanged profile content is never re-evaluated

Supported call types (spec-aligned):
  - project_complexity  : per-project complexity + domain classification
  - resume_quality      : grammar, impact statements, professional tone

Cache dimensions (spec-defined):
  - content_hash  (SHA-256 of the input text — role-independent for complexity)
  - target_role   (included for resume call — role-dependent)
  - engine_version
  - dataset_version
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRIES     = 3          # bounded retry on malformed output
RETRY_DELAY_S   = 0.5        # seconds between retries
ENGINE_VERSION  = "prs-v1"
DATASET_VERSION = "1.0"

# ---------------------------------------------------------------------------
# In-process LRU-style cache  (dict is sufficient for a single-process server)
# ---------------------------------------------------------------------------

_CACHE: dict[str, dict[str, Any]] = {}
MAX_CACHE_SIZE = 512          # evict oldest when limit reached


def _cache_get(key: str) -> dict[str, Any] | None:
    return _CACHE.get(key)


def _cache_put(key: str, value: dict[str, Any]) -> None:
    if len(_CACHE) >= MAX_CACHE_SIZE:
        # Evict the first (oldest) entry
        oldest = next(iter(_CACHE))
        del _CACHE[oldest]
    _CACHE[key] = value


def _make_cache_key(*parts: str) -> str:
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Pydantic output schemas (Phase 15 spec-aligned)
# ---------------------------------------------------------------------------

class ProjectAnalysisItem(BaseModel):
    """Schema for a single project in Gemini's batch response."""
    name: str
    domains: list[str] = Field(default_factory=list)
    complexity_score: float = Field(ge=0, le=100)
    rationale: str = ""

    @field_validator("complexity_score", mode="before")
    @classmethod
    def clamp_complexity(cls, v: Any) -> float:
        """Clamp to [0, 100] regardless of what the LLM returns."""
        try:
            f = float(v)
        except (TypeError, ValueError):
            f = 50.0
        return max(0.0, min(100.0, f))

    @field_validator("domains", mode="before")
    @classmethod
    def coerce_domains(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(d) for d in v]
        return []


class ProjectBatchOutput(BaseModel):
    """Validated output for a project batch classification call."""
    projects: list[ProjectAnalysisItem]

    @model_validator(mode="before")
    @classmethod
    def wrap_list(cls, v: Any) -> Any:
        """Accept either a raw list or an object with 'projects' key."""
        if isinstance(v, list):
            return {"projects": v}
        return v


class ResumeAnalysisOutput(BaseModel):
    """Schema for Gemini's resume quality analysis."""
    grammar: float = Field(default=70.0, ge=0, le=100)
    impact_statements: float = Field(default=50.0, ge=0, le=100)
    professional_tone: float = Field(default=70.0, ge=0, le=100)
    issues: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)

    @field_validator("grammar", "impact_statements", "professional_tone", mode="before")
    @classmethod
    def clamp_scores(cls, v: Any) -> float:
        try:
            f = float(v)
        except (TypeError, ValueError):
            f = 60.0
        return max(0.0, min(100.0, f))

    @field_validator("issues", "improvement_suggestions", mode="before")
    @classmethod
    def coerce_lists(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(s) for s in v[:8]]
        return []


# ---------------------------------------------------------------------------
# Internal Gemini client helper
# ---------------------------------------------------------------------------

def _get_gemini_client() -> Any | None:
    """Return a configured Gemini client, or None if not available."""
    try:
        import google.genai as genai
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return None
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def _strip_markdown(raw: str) -> str:
    """Remove ```json ... ``` fences if present."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Remove first line (```json or ```) and last line (```)
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        raw = "\n".join(lines[start:end])
    return raw.strip()


def _call_with_retry(
    client: Any,
    prompt: str,
    model: str = "gemini-2.0-flash",
) -> str | None:
    """
    Call Gemini with up to MAX_RETRIES attempts.
    Returns the raw text response or None on all failures.
    Never raises.
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            return response.text
        except Exception as exc:
            _log_safe(f"[LLMGateway] Attempt {attempt + 1}/{MAX_RETRIES} failed: {type(exc).__name__}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_S)
    return None


def _log_safe(msg: str) -> None:
    """Print a log message that never contains user content."""
    print(msg)


# ---------------------------------------------------------------------------
# Public API 1: Project complexity + domain classification
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Deterministic mode guard — set PRS_DETERMINISTIC_MODE=true in .env to
# disable ALL Gemini calls.  Both gateway functions will return immediately,
# forcing every engine into its fully-deterministic fallback path.
# Benefits: zero API calls, zero retry delays (saves ~1.5 s per evaluation),
# fully reproducible scores, no rate-limit errors.
# ---------------------------------------------------------------------------

def _is_deterministic_mode() -> bool:
    """
    Return True when the caller has opted out of LLM calls.

    Reads the PRS_DETERMINISTIC_MODE environment variable once per call
    (no caching needed — the variable is checked rarely and Python string
    comparison is cheap).
    """
    return os.getenv("PRS_DETERMINISTIC_MODE", "").strip().lower() == "true"


def classify_projects(
    projects: list[dict[str, str]],   # [{name, description, domain, skills}]
    target_role: str,
) -> list[dict[str, Any]]:
    """
    Call Gemini once to classify all projects in a batch.

    Parameters
    ----------
    projects : list of dicts with keys: name, description, skills (comma string)
    target_role : the role being evaluated (for prompt context only)

    Returns
    -------
    list of validated dicts:
        {name, domains, complexity_score (0-100 clamped), rationale}
    Falls back to [] (triggers deterministic fallback in projects_engine).

    Cache dimension: content_hash of all project content (role-independent
    complexity; project relevance is recalculated per-role in projects_engine).

    When PRS_DETERMINISTIC_MODE=true this returns [] immediately so the
    caller (projects_engine) uses the rich deterministic classifier instead.
    """
    if not projects:
        return []

    # ── Deterministic mode: bypass Gemini entirely ────────────────────────────
    if _is_deterministic_mode():
        _log_safe("[LLMGateway] classify_projects: deterministic mode — skipping LLM")
        return []

    # Build a deterministic hash of all project content (role-independent)
    content_str = json.dumps(projects, sort_keys=True)
    content_key = _make_cache_key(
        _content_hash(content_str),
        ENGINE_VERSION,
        DATASET_VERSION,
    )

    cached = _cache_get(content_key)
    if cached is not None:
        _log_safe(f"[LLMGateway] project classify: cache hit ({len(projects)} projects)")
        return cached.get("result", [])

    client = _get_gemini_client()
    if client is None:
        return []

    # Build concise, privacy-safe project summaries
    summaries: list[str] = []
    for i, p in enumerate(projects):
        parts = [f"{i + 1}. Name: {p.get('name', 'Unnamed')}"]
        desc = p.get("description", "")
        if desc:
            parts.append(f"   Description: {desc[:250]}")
        skills = p.get("skills", "")
        if skills:
            parts.append(f"   Skills: {skills[:150]}")
        summaries.append("\n".join(parts))

    prompt = f"""You are a technical project evaluator. Analyze these student projects for a candidate targeting: "{target_role}".

For EACH project provide:
1. domains: list of 1-3 technical domains (e.g. "Backend Systems", "Machine Learning", "Web Applications", "Data Engineering")
2. complexity_score: integer 0-100
   0-25: tutorial/copy-paste level
   26-50: small independent with basic functionality
   51-75: multiple integrated components, real functionality
   76-100: complex architecture, production-grade thinking

Projects:
{chr(10).join(summaries)}

Respond ONLY with a valid JSON array, one object per project in the same order:
[
  {{"name": "exact project name", "domains": ["domain1"], "complexity_score": 70, "rationale": "brief technical reason"}},
  ...
]"""

    raw_text = _call_with_retry(client, prompt)
    if raw_text is None:
        _log_safe("[LLMGateway] project classify: all retries failed, using deterministic fallback")
        return []

    # Parse + validate with Pydantic
    for attempt in range(MAX_RETRIES):
        try:
            stripped = _strip_markdown(raw_text)
            raw_json = json.loads(stripped)
            validated = ProjectBatchOutput.model_validate(raw_json)
            result = [
                {
                    "name":             item.name,
                    "domains":          item.domains,
                    "complexity_score": item.complexity_score,  # already clamped 0-100
                    "rationale":        item.rationale,
                }
                for item in validated.projects
            ]
            _log_safe(f"[LLMGateway] project classify: validated {len(result)} projects")
            _cache_put(content_key, {"result": result})
            return result

        except (json.JSONDecodeError, ValueError, Exception) as exc:
            _log_safe(
                f"[LLMGateway] project classify: parse/validation error "
                f"(attempt {attempt + 1}/{MAX_RETRIES}): {type(exc).__name__}"
            )
            if attempt < MAX_RETRIES - 1:
                # Ask Gemini to fix its own output
                raw_text = _call_with_retry(
                    client,
                    f"The following JSON is invalid. Fix it and return ONLY a valid JSON array:\n{raw_text}",
                ) or raw_text
            else:
                _log_safe("[LLMGateway] project classify: schema validation failed, using deterministic fallback")
                return []

    return []


# ---------------------------------------------------------------------------
# Public API 2: Resume quality analysis
# ---------------------------------------------------------------------------

def analyze_resume(
    resume_content: str,
    content_source: str,
    target_role: str,
) -> dict[str, Any] | None:
    """
    Call Gemini to evaluate resume grammar, impact statements, and tone.

    Parameters
    ----------
    resume_content : text to analyze (NEVER logged in full)
    content_source : "resume_text" | "structured_proxy" (for prompt context)
    target_role : used for cache key (resume analysis is role-dependent)

    Returns
    -------
    Validated dict:
        {grammar, impact_statements, professional_tone, issues, improvement_suggestions}
    Returns None on failure (triggers deterministic fallback in resume_engine).

    Privacy: resume_content is NEVER printed to logs.
    When PRS_DETERMINISTIC_MODE=true this returns None immediately so the
    resume_engine uses its enhanced deterministic fallback path.
    """
    if not resume_content or len(resume_content.strip()) < 20:
        return None

    # ── Deterministic mode: bypass Gemini entirely ────────────────────────────
    if _is_deterministic_mode():
        _log_safe("[LLMGateway] analyze_resume: deterministic mode — skipping LLM")
        return None

    # Cache key includes content hash AND role (analysis is role-dependent)
    content_key = _make_cache_key(
        _content_hash(resume_content),
        target_role.lower(),
        ENGINE_VERSION,
        DATASET_VERSION,
    )

    cached = _cache_get(content_key)
    if cached is not None:
        _log_safe("[LLMGateway] resume analysis: cache hit")
        return cached.get("result")

    client = _get_gemini_client()
    if client is None:
        return None

    # Truncate to protect privacy and cost (never log the content)
    content_preview = resume_content[:2500]

    prompt = f"""You are an expert resume reviewer evaluating a candidate's resume quality.
Analyze the following resume content (source: {content_source}, role: {target_role}).

Resume Content:
{content_preview}

Respond ONLY with valid JSON (no markdown, no explanation outside the JSON):
{{
    "grammar": <integer 0-100>,
    "impact_statements": <integer 0-100>,
    "professional_tone": <integer 0-100>,
    "issues": [<list of specific problems, max 5 concise strings>],
    "improvement_suggestions": [<list of actionable suggestions, max 5 concise strings>]
}}

Scoring guide:
- grammar: 90+ = no errors, 70-90 = minor, 50-70 = moderate, <50 = many errors
- impact_statements: 90+ = strong verbs + quantified results, 50-70 = some action verbs but vague, <50 = passive/weak
- professional_tone: 90+ = polished, 50-70 = acceptable but informal, <50 = unprofessional"""

    raw_text = _call_with_retry(client, prompt)
    if raw_text is None:
        _log_safe("[LLMGateway] resume analysis: all retries failed, using deterministic fallback")
        return None

    # Parse + validate with Pydantic
    for attempt in range(MAX_RETRIES):
        try:
            stripped = _strip_markdown(raw_text)
            raw_json = json.loads(stripped)
            validated = ResumeAnalysisOutput.model_validate(raw_json)
            result = {
                "grammar":                  validated.grammar,
                "impact_statements":        validated.impact_statements,
                "professional_tone":        validated.professional_tone,
                "issues":                   validated.issues,
                "improvement_suggestions":  validated.improvement_suggestions,
            }
            _log_safe("[LLMGateway] resume analysis: validated successfully")
            _cache_put(content_key, {"result": result})
            return result

        except (json.JSONDecodeError, ValueError, Exception) as exc:
            _log_safe(
                f"[LLMGateway] resume analysis: parse/validation error "
                f"(attempt {attempt + 1}/{MAX_RETRIES}): {type(exc).__name__}"
            )
            if attempt < MAX_RETRIES - 1:
                raw_text = _call_with_retry(
                    client,
                    f"The following JSON is malformed. Return ONLY a valid JSON object:\n{raw_text}",
                ) or raw_text
            else:
                _log_safe("[LLMGateway] resume analysis: schema validation failed, using deterministic fallback")
                return None

    return None


# ---------------------------------------------------------------------------
# Cache inspection utility (for tests / diagnostics only)
# ---------------------------------------------------------------------------

def get_cache_stats() -> dict[str, int]:
    return {"size": len(_CACHE), "max_size": MAX_CACHE_SIZE}


def clear_cache() -> None:
    _CACHE.clear()
