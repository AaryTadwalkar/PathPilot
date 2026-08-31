import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.prs.assessment_service import (
    get_assessment_questions,
    score_assessment_for_prototype,
    validate_assessment_answers,
)


VALID_ANSWERS = {
    "deployment_exposure": "public_hosting",
    "project_ownership": "multiple_components",
    "engineering_practices": ["git", "testing", "ci_cd"],
    "relevant_experience_duration": "6_12_months",
    "real_world_usage": "small_real_users",
    "problem_solving_independence": "debug_and_implement",
}


class PRSAssessmentServiceTests(unittest.TestCase):
    def test_six_backend_owned_questions_are_exposed(self):
        questions = get_assessment_questions()

        self.assertEqual(len(questions), 6)
        self.assertEqual(
            [question["id"] for question in questions],
            [
                "deployment_exposure",
                "project_ownership",
                "engineering_practices",
                "relevant_experience_duration",
                "real_world_usage",
                "problem_solving_independence",
            ],
        )

    def test_valid_answers_are_normalized(self):
        normalized = validate_assessment_answers(dict(VALID_ANSWERS))

        self.assertEqual(normalized["deployment_exposure"], "public_hosting")
        self.assertEqual(
            normalized["engineering_practices"],
            ["git", "testing", "ci_cd"],
        )

    def test_missing_answer_fails_explicitly(self):
        answers = dict(VALID_ANSWERS)
        answers.pop("real_world_usage")

        with self.assertRaises(ValueError) as context:
            validate_assessment_answers(answers)

        self.assertIn("Missing assessment answer: real_world_usage", str(context.exception))

    def test_none_cannot_be_combined_in_multi_select(self):
        answers = dict(VALID_ANSWERS)
        answers["engineering_practices"] = ["none", "git"]

        with self.assertRaises(ValueError) as context:
            validate_assessment_answers(answers)

        self.assertIn("'none' cannot be combined", str(context.exception))

    def test_prototype_bridge_scores_are_backend_owned(self):
        scores = score_assessment_for_prototype(dict(VALID_ANSWERS))

        self.assertEqual(scores["project_score"], 80.8)
        self.assertEqual(scores["experience_score"], 62.8)
        self.assertEqual(scores["projects_experience_score"], 77.2)


if __name__ == "__main__":
    unittest.main()