import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any


class DatasetValidationError(RuntimeError):
    """Raised when a critical PRS dataset is missing or invalid."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("PRS dataset validation failed: " + "; ".join(errors))


@dataclass(frozen=True)
class PRSDatasets:
    dataset_dir: Path
    skills_master: list[dict[str, Any]]
    role_skill_mapping: list[dict[str, Any]]
    role_domain_mapping: dict[str, list[str]]
    role_tech_stack_mapping: list[dict[str, Any]]
    stack_sophistication_mapping: dict[str, int | float]
    certificates_dataset: list[dict[str, Any]]
    certificate_provider_scores: dict[str, int | float]
    certificate_level_mapping: dict[str, int | float]
    skill_aliases: dict[str, str]
    certificate_aliases: dict[str, str]
    stack_aliases: dict[str, str]
    courses_dataset: list[dict[str, Any]] = field(default_factory=list)
    projects_dataset: list[dict[str, Any]] = field(default_factory=list)
    assessment_questions: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def roles(self) -> list[str]:
        return sorted({entry["role"] for entry in self.role_skill_mapping})


REQUIRED_FILES = {
    "skills_master": "skills_master.json",
    "role_skill_mapping": "role_skill_mapping.json",
    "role_domain_mapping": "role_domain_mapping.json",
    "role_tech_stack_mapping": "role_tech_stack_mapping.json",
    "stack_sophistication_mapping": "stack_sophistication_mapping.json",
    "certificates_dataset": "certificates_dataset.json",
    "certificate_provider_scores": "certificate_provider_scores.json",
    "certificate_level_mapping": "certificate_level_mapping.json",
    "skill_aliases": "aliases/skill_aliases.json",
    "certificate_aliases": "aliases/certificate_aliases.json",
    "stack_aliases": "aliases/stack_aliases.json",
}

OPTIONAL_FILES = {
    "courses_dataset": "courses_dataset.json",
    "projects_dataset": "projects_dataset.json",
    "assessment_questions": "assessment_questions.json",
}

ROLE_CRITICALITY_VALUES = {
    "critical",
    "very_high",
    "high",
    "medium",
    "low",
    # Present in the current dataset; engines will map it deliberately.
    "important",
}

INDUSTRY_DEMAND_VALUES = {
    "very_high",
    "high",
    "medium",
    "low",
}

PRACTICAL_IMPACT_VALUES = {
    "very_high",
    "high",
    "medium",
    "low",
}

FOUNDATIONAL_TYPE_VALUES = {
    "foundational",
    "supporting",
    "advanced_bonus",
    # Present in the current dataset; engines will map it deliberately.
    "specialized",
}


def resolve_dataset_dir(dataset_dir: str | Path | None = None) -> Path:
    """
    Resolve the PRS dataset directory.

    Resolution order:
    1. Explicit function argument.
    2. PRS_DATASET_DIR environment variable.
    3. Repository-level datasets folder.
    """
    if dataset_dir:
        candidate = Path(dataset_dir)
    elif os.getenv("PRS_DATASET_DIR"):
        candidate = Path(os.environ["PRS_DATASET_DIR"])
    else:
        candidate = Path(__file__).resolve().parents[4] / "datasets"

    return candidate.expanduser().resolve()


@lru_cache(maxsize=4)
def load_prs_datasets(dataset_dir: str | None = None) -> PRSDatasets:
    resolved_dir = resolve_dataset_dir(dataset_dir)
    errors: list[str] = []
    warnings: list[str] = []

    if not resolved_dir.exists():
        raise DatasetValidationError(
            [f"Dataset directory does not exist: {resolved_dir}"]
        )

    loaded: dict[str, Any] = {}

    for key, relative_path in REQUIRED_FILES.items():
        loaded[key] = _load_required_json(resolved_dir, relative_path, errors)

    for key, relative_path in OPTIONAL_FILES.items():
        loaded[key] = _load_optional_json(resolved_dir, relative_path, warnings)

    if errors:
        raise DatasetValidationError(errors)

    _validate_all(loaded, errors, warnings)

    if errors:
        raise DatasetValidationError(errors)

    return PRSDatasets(
        dataset_dir=resolved_dir,
        skills_master=loaded["skills_master"],
        role_skill_mapping=loaded["role_skill_mapping"],
        role_domain_mapping=loaded["role_domain_mapping"],
        role_tech_stack_mapping=loaded["role_tech_stack_mapping"],
        stack_sophistication_mapping=loaded["stack_sophistication_mapping"],
        certificates_dataset=loaded["certificates_dataset"],
        certificate_provider_scores=loaded["certificate_provider_scores"],
        certificate_level_mapping=loaded["certificate_level_mapping"],
        skill_aliases=loaded["skill_aliases"],
        certificate_aliases=loaded["certificate_aliases"],
        stack_aliases=loaded["stack_aliases"],
        courses_dataset=loaded["courses_dataset"] or [],
        projects_dataset=loaded["projects_dataset"] or [],
        assessment_questions=loaded["assessment_questions"] or {},
        warnings=warnings,
    )


def clear_prs_dataset_cache() -> None:
    load_prs_datasets.cache_clear()


def _load_required_json(
    dataset_dir: Path,
    relative_path: str,
    errors: list[str],
) -> Any:
    path = dataset_dir / relative_path
    if not path.exists():
        errors.append(f"Missing required dataset file: {path}")
        return None
    return _read_json(path, errors)


def _load_optional_json(
    dataset_dir: Path,
    relative_path: str,
    warnings: list[str],
) -> Any:
    path = dataset_dir / relative_path
    if not path.exists():
        warnings.append(f"Optional dataset file is not present: {path}")
        return None
    errors: list[str] = []
    data = _read_json(path, errors)
    if errors:
        warnings.extend(errors)
        return None
    return data


def _read_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        errors.append(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        )
    except OSError as exc:
        errors.append(f"Could not read dataset file {path}: {exc}")
    return None


def _validate_all(
    loaded: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    _require_type(loaded, "skills_master", list, errors)
    _require_type(loaded, "role_skill_mapping", list, errors)
    _require_type(loaded, "role_domain_mapping", dict, errors)
    _require_type(loaded, "role_tech_stack_mapping", list, errors)
    _require_type(loaded, "stack_sophistication_mapping", dict, errors)
    _require_type(loaded, "certificates_dataset", list, errors)
    _require_type(loaded, "certificate_provider_scores", dict, errors)
    _require_type(loaded, "certificate_level_mapping", dict, errors)
    _require_type(loaded, "skill_aliases", dict, errors)
    _require_type(loaded, "certificate_aliases", dict, errors)
    _require_type(loaded, "stack_aliases", dict, errors)

    if errors:
        return

    known_skills = _validate_skills_master(loaded["skills_master"], errors)
    role_names = _validate_role_skill_mapping(
        loaded["role_skill_mapping"],
        known_skills,
        errors,
        warnings,
    )
    _validate_role_domains(loaded["role_domain_mapping"], role_names, errors, warnings)
    _validate_role_tech_stacks(
        loaded["role_tech_stack_mapping"],
        role_names,
        errors,
        warnings,
    )
    _validate_numeric_score_map(
        loaded["stack_sophistication_mapping"],
        "stack_sophistication_mapping",
        errors,
        min_value=0,
        max_value=100,
    )
    _validate_certificates(
        loaded["certificates_dataset"],
        loaded["certificate_provider_scores"],
        loaded["certificate_level_mapping"],
        errors,
        warnings,
    )
    _validate_numeric_score_map(
        loaded["certificate_provider_scores"],
        "certificate_provider_scores",
        errors,
        min_value=0,
        max_value=100,
    )
    _validate_numeric_score_map(
        loaded["certificate_level_mapping"],
        "certificate_level_mapping",
        errors,
        min_value=0,
        max_value=100,
    )
    _validate_aliases(
        loaded["skill_aliases"],
        "skill_aliases",
        errors,
        known_targets=known_skills,
        warnings=warnings,
    )
    _validate_aliases(
        loaded["certificate_aliases"],
        "certificate_aliases",
        errors,
        known_targets={
            cert["certificate_name"].lower()
            for cert in loaded["certificates_dataset"]
            if isinstance(cert, dict) and cert.get("certificate_name")
        },
        warnings=warnings,
    )
    _validate_aliases(
        loaded["stack_aliases"],
        "stack_aliases",
        errors,
        known_targets=None,
        warnings=warnings,
    )
    _validate_recommendation_dataset(
        loaded.get("courses_dataset") or [],
        "courses_dataset",
        "course_id",
        "course_name",
        role_names,
        errors,
        warnings,
    )
    _validate_recommendation_dataset(
        loaded.get("projects_dataset") or [],
        "projects_dataset",
        "project_id",
        "project_name",
        role_names,
        errors,
        warnings,
    )
    _validate_assessment_questions(loaded.get("assessment_questions") or {}, errors)


def _require_type(
    loaded: dict[str, Any],
    key: str,
    expected_type: type,
    errors: list[str],
) -> None:
    if not isinstance(loaded.get(key), expected_type):
        errors.append(
            f"{key} must be {expected_type.__name__}, got "
            f"{type(loaded.get(key)).__name__}"
        )


def _validate_skills_master(
    skills_master: list[dict[str, Any]],
    errors: list[str],
) -> set[str]:
    required_fields = {"skill_name", "category", "aliases", "cluster"}
    names: set[str] = set()

    for index, skill in enumerate(skills_master):
        if not isinstance(skill, dict):
            errors.append(f"skills_master[{index}] must be an object")
            continue
        _require_fields(skill, required_fields, f"skills_master[{index}]", errors)
        name = _normalized(skill.get("skill_name"))
        if not name:
            continue
        if name in names:
            errors.append(f"Duplicate skill in skills_master: {skill['skill_name']}")
        names.add(name)
        if not isinstance(skill.get("aliases"), list):
            errors.append(f"skills_master[{index}].aliases must be a list")

    return names


def _validate_role_skill_mapping(
    role_skill_mapping: list[dict[str, Any]],
    known_skills: set[str],
    errors: list[str],
    warnings: list[str],
) -> set[str]:
    role_names: set[str] = set()
    required_role_fields = {"role", "skills"}
    required_skill_fields = {
        "skill_name",
        "category",
        "role_criticality",
        "industry_demand",
        "practical_impact",
        "foundational_type",
    }

    for role_index, role_entry in enumerate(role_skill_mapping):
        if not isinstance(role_entry, dict):
            errors.append(f"role_skill_mapping[{role_index}] must be an object")
            continue
        _require_fields(
            role_entry,
            required_role_fields,
            f"role_skill_mapping[{role_index}]",
            errors,
        )
        role = role_entry.get("role")
        if role in role_names:
            errors.append(f"Duplicate role in role_skill_mapping: {role}")
        if role:
            role_names.add(role)
        skills = role_entry.get("skills")
        if not isinstance(skills, list) or not skills:
            errors.append(f"role_skill_mapping[{role_index}].skills must be a non-empty list")
            continue

        seen_role_skills: set[str] = set()
        for skill_index, skill in enumerate(skills):
            context = f"role_skill_mapping[{role}].skills[{skill_index}]"
            if not isinstance(skill, dict):
                errors.append(f"{context} must be an object")
                continue
            _require_fields(skill, required_skill_fields, context, errors)
            skill_name = _normalized(skill.get("skill_name"))
            if skill_name in seen_role_skills:
                errors.append(f"Duplicate skill for role {role}: {skill.get('skill_name')}")
            seen_role_skills.add(skill_name)
            if skill_name and skill_name not in known_skills:
                warnings.append(
                    f"{context}.skill_name is not in skills_master: {skill.get('skill_name')}"
                )
            _require_allowed(
                skill.get("role_criticality"),
                ROLE_CRITICALITY_VALUES,
                f"{context}.role_criticality",
                errors,
            )
            _require_allowed(
                skill.get("industry_demand"),
                INDUSTRY_DEMAND_VALUES,
                f"{context}.industry_demand",
                errors,
            )
            _require_allowed(
                skill.get("practical_impact"),
                PRACTICAL_IMPACT_VALUES,
                f"{context}.practical_impact",
                errors,
            )
            _require_allowed(
                skill.get("foundational_type"),
                FOUNDATIONAL_TYPE_VALUES,
                f"{context}.foundational_type",
                errors,
            )

    return role_names


def _validate_role_domains(
    role_domain_mapping: dict[str, list[str]],
    role_names: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    missing = sorted(role_names - set(role_domain_mapping.keys()))
    if missing:
        errors.append(
            "role_domain_mapping is missing roles from role_skill_mapping: "
            + ", ".join(missing)
        )

    for role, domains in role_domain_mapping.items():
        if role not in role_names:
            warnings.append(f"role_domain_mapping has extra role without skills: {role}")
        if not isinstance(domains, list) or not all(isinstance(item, str) for item in domains):
            errors.append(f"role_domain_mapping[{role}] must be a list of strings")


def _validate_role_tech_stacks(
    role_tech_stack_mapping: list[dict[str, Any]],
    role_names: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    stack_roles: set[str] = set()
    for index, entry in enumerate(role_tech_stack_mapping):
        context = f"role_tech_stack_mapping[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{context} must be an object")
            continue
        _require_fields(entry, {"role", "primary_stack", "secondary_stack"}, context, errors)
        role = entry.get("role")
        if role in stack_roles:
            errors.append(f"Duplicate role in role_tech_stack_mapping: {role}")
        if role:
            stack_roles.add(role)
        for key in ("primary_stack", "secondary_stack"):
            values = entry.get(key)
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                errors.append(f"{context}.{key} must be a list of strings")

    missing = sorted(role_names - stack_roles)
    if missing:
        errors.append(
            "role_tech_stack_mapping is missing roles from role_skill_mapping: "
            + ", ".join(missing)
        )

    extra = sorted(stack_roles - role_names)
    if extra:
        warnings.append(
            "role_tech_stack_mapping has extra roles without role_skill_mapping: "
            + ", ".join(extra)
        )


def _validate_certificates(
    certificates: list[dict[str, Any]],
    provider_scores: dict[str, int | float],
    level_mapping: dict[str, int | float],
    errors: list[str],
    warnings: list[str],
) -> None:
    required_fields = {
        "certificate_id",
        "certificate_name",
        "provider",
        "certificate_level",
        "skills_covered",
        "role_alignment",
        "certificate_url",
        "industry_relevance",
    }
    seen_ids: set[str] = set()
    levels = {_normalized(key) for key in level_mapping.keys()}

    for index, certificate in enumerate(certificates):
        context = f"certificates_dataset[{index}]"
        if not isinstance(certificate, dict):
            errors.append(f"{context} must be an object")
            continue
        _require_fields(certificate, required_fields, context, errors)
        cert_id = certificate.get("certificate_id")
        if cert_id in seen_ids:
            errors.append(f"Duplicate certificate_id: {cert_id}")
        if cert_id:
            seen_ids.add(cert_id)
        provider = certificate.get("provider")
        if provider and provider not in provider_scores:
            warnings.append(
                f"{context}.provider has no certificate_provider_scores entry: {provider}"
            )
        level = _normalized(certificate.get("certificate_level"))
        if level and level not in levels:
            errors.append(
                f"{context}.certificate_level has no certificate_level_mapping entry: "
                f"{certificate.get('certificate_level')}"
            )
        for key in ("skills_covered", "role_alignment"):
            values = certificate.get(key)
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                errors.append(f"{context}.{key} must be a list of strings")


def _validate_numeric_score_map(
    score_map: dict[str, int | float],
    name: str,
    errors: list[str],
    min_value: int,
    max_value: int,
) -> None:
    for key, value in score_map.items():
        if not isinstance(value, (int, float)):
            errors.append(f"{name}[{key}] must be numeric")
            continue
        if value < min_value or value > max_value:
            errors.append(f"{name}[{key}] must be between {min_value} and {max_value}")


def _validate_aliases(
    aliases: dict[str, str],
    name: str,
    errors: list[str],
    known_targets: set[str] | None,
    warnings: list[str],
) -> None:
    normalized_aliases = {_normalized(key): _normalized(value) for key, value in aliases.items()}

    for raw_alias, raw_target in aliases.items():
        if not isinstance(raw_alias, str) or not isinstance(raw_target, str):
            errors.append(f"{name} aliases and targets must be strings")
            continue
        if _normalized(raw_alias) == _normalized(raw_target):
            warnings.append(f"{name} has canonical self-alias: {raw_alias}")
            continue
        _detect_alias_cycle(normalized_aliases, _normalized(raw_alias), name, errors)
        if known_targets is not None and _normalized(raw_target) not in known_targets:
            warnings.append(f"{name} target is not in canonical dataset: {raw_target}")


def _detect_alias_cycle(
    aliases: dict[str, str],
    alias: str,
    name: str,
    errors: list[str],
) -> None:
    seen: set[str] = set()
    current = alias
    while current in aliases:
        next_value = aliases[current]
        if next_value == current:
            return
        if current in seen:
            errors.append(f"{name} contains circular alias involving: {alias}")
            return
        seen.add(current)
        current = next_value


def _validate_recommendation_dataset(
    rows: list[dict[str, Any]],
    name: str,
    id_field: str,
    title_field: str,
    role_names: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        context = f"{name}[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{context} must be an object")
            continue
        _require_fields(
            row,
            {id_field, title_field, "skills_covered" if name == "courses_dataset" else "primary_skills", "role_alignment"},
            context,
            errors,
        )
        row_id = row.get(id_field)
        if row_id in seen_ids:
            errors.append(f"Duplicate {id_field} in {name}: {row_id}")
        if row_id:
            seen_ids.add(row_id)
        for role in row.get("role_alignment", []):
            if role not in role_names:
                warnings.append(f"{context}.role_alignment references unmapped role: {role}")


def _validate_assessment_questions(
    assessment_questions: dict[str, list[dict[str, Any]]],
    errors: list[str],
) -> None:
    if not isinstance(assessment_questions, dict):
        errors.append("assessment_questions must be an object")
        return

    seen_ids: set[str] = set()
    for group, questions in assessment_questions.items():
        if not isinstance(questions, list):
            errors.append(f"assessment_questions[{group}] must be a list")
            continue
        for index, question in enumerate(questions):
            context = f"assessment_questions[{group}][{index}]"
            if not isinstance(question, dict):
                errors.append(f"{context} must be an object")
                continue
            _require_fields(question, {"id", "question", "type", "weight", "options"}, context, errors)
            question_id = question.get("id")
            if question_id in seen_ids:
                errors.append(f"Duplicate assessment question id: {question_id}")
            if question_id:
                seen_ids.add(question_id)
            options = question.get("options")
            if not isinstance(options, dict) or not options:
                errors.append(f"{context}.options must be a non-empty object")
            else:
                _validate_numeric_score_map(options, f"{context}.options", errors, 0, 100)


def _require_fields(
    row: dict[str, Any],
    fields: set[str],
    context: str,
    errors: list[str],
) -> None:
    for field_name in sorted(fields):
        if field_name not in row:
            errors.append(f"{context} missing required field: {field_name}")


def _require_allowed(
    value: Any,
    allowed_values: set[str],
    context: str,
    errors: list[str],
) -> None:
    if _normalized(value) not in allowed_values:
        errors.append(
            f"{context} has invalid value {value!r}; allowed values: "
            + ", ".join(sorted(allowed_values))
        )


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()
