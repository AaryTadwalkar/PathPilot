"""
app/services/career/progression_engine.py
==========================================
Module 3 - M3-7: Role Progression Engine.

What this file does:
  Looks up the career progression chain for a given target role.
  Returns entry paths, next roles, adjacent roles, and senior path.
  Fully independent of M3-3 to M3-6 — can be called in any order.

Overall design:
  Pure dataset lookup — no computation, no PRS engine calls.
  Reads role_progression_mapping.json from the datasets directory.
  Caches the loaded mapping in a module-level dict (cheap, < 1KB).

Elements:
  ProgressionResult    dataclass  Return type of get_role_progression()
  get_role_progression()          Main public function
  _load_progression_map()         Internal loader with module-level cache

Final output:
  ProgressionResult with entry_path, next_roles, adjacent_roles, senior_path,
  typical_experience_years, typical_years_to_next, and a flag for role_found.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.services.prs.dataset_loader import PRSDatasets


# ---------------------------------------------------------------------------
# Module-level cache (avoids re-reading the file on every request)
# ---------------------------------------------------------------------------

_PROGRESSION_CACHE: dict[str, dict] | None = None


def _load_progression_map(dataset_dir: Path) -> dict[str, dict]:
    """
    Use:
      Load role_progression_mapping.json into a dict keyed by role name.
      Module-level cache means the file is only read once per process.

    How it works:
      First call reads the JSON file and builds {role: progression_dict}.
      Subsequent calls return the cached result.

    Used by: get_role_progression() only.

    Output:
      Before: None (cache empty)
      After:  dict of {role_name: {entry_path, next_roles, ...}}
    """
    global _PROGRESSION_CACHE
    if _PROGRESSION_CACHE is not None:
        return _PROGRESSION_CACHE

    path = dataset_dir / "role_progression_mapping.json"
    raw: list[dict] = json.loads(path.read_text(encoding="utf-8"))
    _PROGRESSION_CACHE = {entry["role"]: entry["progression"] for entry in raw}
    return _PROGRESSION_CACHE


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProgressionResult:
    """
    Use:
      Return value of get_role_progression(). Stored in career_paths.role_progression.
      Shown in the frontend as the "Your Career Journey" section.

    Contains:
      target_role              the role the student is targeting
      role_found               False if the role has no entry in the mapping
      entry_path               roles that lead INTO target_role (stepping stones)
      next_roles               roles the student can move to AFTER mastering this role
      adjacent_roles           parallel roles at the same level
      senior_path              the long-term leadership/specialist destination
      typical_experience_years  experience range for this role level
      typical_years_to_next     expected time before progressing to next_roles

    Technologies:
      Pure Python dataclass. Serialised to JSON for career_paths.role_progression.
    """
    target_role:              str
    role_found:               bool
    entry_path:               list[str] = field(default_factory=list)
    next_roles:               list[str] = field(default_factory=list)
    adjacent_roles:           list[str] = field(default_factory=list)
    senior_path:              str = ""
    typical_experience_years: str = ""
    typical_years_to_next:    str = ""

    def to_dict(self) -> dict:
        """Serialise for JSON storage in career_paths.role_progression."""
        return {
            "target_role":              self.target_role,
            "role_found":               self.role_found,
            "entry_path":               self.entry_path,
            "next_roles":               self.next_roles,
            "adjacent_roles":           self.adjacent_roles,
            "senior_path":              self.senior_path,
            "typical_experience_years": self.typical_experience_years,
            "typical_years_to_next":    self.typical_years_to_next,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_role_progression(
    target_role: str,
    datasets:    PRSDatasets,
) -> ProgressionResult:
    """
    Use:
      Return the career progression chain for a given role.
      Called by career_orchestrator (M3-8) in parallel with the gap/milestone
      pipeline — it has no dependencies on the other engines.

    How it works:
      Loads the module-level cache of role_progression_mapping.json.
      Looks up target_role. If not found, returns a ProgressionResult with
      role_found=False and all list fields empty (graceful degradation — the
      rest of the career path still works, just without progression data).

    Concepts:
      Graceful degradation: a missing role in the progression map is not an
      error — it just means we can't show the progression chain. The student
      still gets their milestones, ETA, and gap analysis.

    Imports used by: career_orchestrator.py (M3-8).

    Parameters:
      target_role  str         the role the student is targeting
      datasets     PRSDatasets loaded dataset cache (used for dataset_dir)

    Output:
      Before: role name string
      After:  ProgressionResult with full chain, or role_found=False if unknown
    """
    prog_map = _load_progression_map(datasets.dataset_dir)
    prog = prog_map.get(target_role)

    if not prog:
        return ProgressionResult(
            target_role=target_role,
            role_found=False,
        )

    return ProgressionResult(
        target_role=target_role,
        role_found=True,
        entry_path=prog.get("entry_path", []),
        next_roles=prog.get("next_roles", []),
        adjacent_roles=prog.get("adjacent_roles", []),
        senior_path=prog.get("senior_path", ""),
        typical_experience_years=prog.get("typical_experience_years", ""),
        typical_years_to_next=prog.get("typical_years_to_next", ""),
    )
