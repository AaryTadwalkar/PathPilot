import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.prs.dataset_loader import (
    DatasetValidationError,
    clear_prs_dataset_cache,
    load_prs_datasets,
)


class PRSDatasetLoaderTests(unittest.TestCase):
    def setUp(self):
        clear_prs_dataset_cache()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.dataset_dir = self.temp_dir / "datasets"
        (self.dataset_dir / "aliases").mkdir(parents=True)
        self._write_minimal_valid_dataset()

    def tearDown(self):
        clear_prs_dataset_cache()
        shutil.rmtree(self.temp_dir)

    def test_loads_valid_datasets(self):
        datasets = load_prs_datasets(str(self.dataset_dir))

        self.assertEqual(datasets.roles, ["Backend Developer"])
        self.assertEqual(datasets.skills_master[0]["skill_name"], "Python")
        self.assertEqual(datasets.courses_dataset[0]["course_id"], "COURSE001")
        self.assertEqual(datasets.projects_dataset[0]["project_id"], "PROJ001")

    def test_missing_required_dataset_fails_explicitly(self):
        (self.dataset_dir / "role_skill_mapping.json").unlink()

        with self.assertRaises(DatasetValidationError) as context:
            load_prs_datasets(str(self.dataset_dir))

        self.assertIn(
            "Missing required dataset file",
            str(context.exception),
        )
        self.assertIn("role_skill_mapping.json", str(context.exception))

    def test_invalid_numeric_score_fails_explicitly(self):
        self._write_json(
            "certificate_provider_scores.json",
            {"Trusted Provider": 120},
        )

        with self.assertRaises(DatasetValidationError) as context:
            load_prs_datasets(str(self.dataset_dir))

        self.assertIn(
            "certificate_provider_scores[Trusted Provider] must be between 0 and 100",
            str(context.exception),
        )

    def _write_minimal_valid_dataset(self):
        self._write_json(
            "skills_master.json",
            [
                {
                    "skill_name": "Python",
                    "category": "Programming Language",
                    "aliases": ["py"],
                    "cluster": "Software Engineering",
                },
                {
                    "skill_name": "REST APIs",
                    "category": "API Design",
                    "aliases": ["rest api"],
                    "cluster": "Backend Engineering",
                },
                {
                    "skill_name": "Docker",
                    "category": "DevOps",
                    "aliases": [],
                    "cluster": "Cloud and DevOps",
                },
            ],
        )
        self._write_json(
            "role_skill_mapping.json",
            [
                {
                    "role": "Backend Developer",
                    "skills": [
                        {
                            "skill_name": "Python",
                            "category": "core",
                            "role_criticality": "critical",
                            "industry_demand": "high",
                            "practical_impact": "high",
                            "foundational_type": "foundational",
                        },
                        {
                            "skill_name": "REST APIs",
                            "category": "core",
                            "role_criticality": "important",
                            "industry_demand": "high",
                            "practical_impact": "high",
                            "foundational_type": "supporting",
                        },
                    ],
                }
            ],
        )
        self._write_json(
            "role_domain_mapping.json",
            {"Backend Developer": ["API Development"]},
        )
        self._write_json(
            "role_tech_stack_mapping.json",
            [
                {
                    "role": "Backend Developer",
                    "primary_stack": ["Python", "REST APIs"],
                    "secondary_stack": ["Docker"],
                }
            ],
        )
        self._write_json(
            "stack_sophistication_mapping.json",
            {"Python": 60, "REST APIs": 65, "Docker": 80},
        )
        self._write_json(
            "certificates_dataset.json",
            [
                {
                    "certificate_id": "CERT001",
                    "certificate_name": "Backend Certificate",
                    "provider": "Trusted Provider",
                    "certificate_level": "intermediate",
                    "skills_covered": ["Python", "REST APIs"],
                    "role_alignment": ["Backend Developer"],
                    "certificate_url": "https://example.com/cert",
                    "industry_relevance": "High",
                }
            ],
        )
        self._write_json(
            "certificate_provider_scores.json",
            {"Trusted Provider": 90},
        )
        self._write_json(
            "certificate_level_mapping.json",
            {"intermediate": 70},
        )
        self._write_json(
            "aliases/skill_aliases.json",
            {"py": "Python"},
        )
        self._write_json(
            "aliases/certificate_aliases.json",
            {"backend cert": "Backend Certificate"},
        )
        self._write_json(
            "aliases/stack_aliases.json",
            {"containers": "Docker"},
        )
        self._write_json(
            "courses_dataset.json",
            [
                {
                    "course_id": "COURSE001",
                    "course_name": "Backend Course",
                    "platform": "Example",
                    "provider": "Trusted Provider",
                    "difficulty_level": "Intermediate",
                    "skills_covered": ["Python"],
                    "role_alignment": ["Backend Developer"],
                    "course_url": "https://example.com/course",
                }
            ],
        )
        self._write_json(
            "projects_dataset.json",
            [
                {
                    "project_id": "PROJ001",
                    "project_name": "Backend API",
                    "description": "Build an API.",
                    "difficulty_level": "Intermediate",
                    "primary_skills": ["REST APIs"],
                    "tech_stack": ["Python"],
                    "role_alignment": ["Backend Developer"],
                    "expected_outcomes": ["API"],
                }
            ],
        )
        self._write_json(
            "assessment_questions.json",
            {
                "deployment_exposure": [
                    {
                        "id": "DEPLOYMENT",
                        "question": "Deployment?",
                        "type": "single_select",
                        "weight": 100,
                        "options": {"none": 0, "cloud": 100},
                    }
                ]
            },
        )

    def _write_json(self, relative_path, data):
        path = self.dataset_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
