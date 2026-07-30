"""Test the local RAGAS CSV preparation helpers without OpenAI calls.

FLOW: create temporary benchmark files -> create a template -> validate and
join rows -> rebuild YAML-free context -> check the written summary.

ASSUMPTION: these tests verify file handling only. They intentionally do not
call RAGAS or OpenAI, so they are fast and do not spend API credits.
"""

import csv
import tempfile
import unittest
from pathlib import Path

import generate_reference_template
import run_ragas_evaluation


class RagasFileTests(unittest.TestCase):
    """Check the manual reference and saved-context workflow."""

    def write_csv(self, path, columns, rows):
        """Write a small CSV used by one test.

        Example: two dictionaries become a two-row temporary input file.
        """
        with path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    def test_template_rows_keep_question_details(self):
        """Create blank template rows from matching 50-row source lists."""
        questions = [
            {
                "id": str(index),
                "query": f"Question {index}",
                "source_category": "Test",
                "source_document": f"source_{index}.md",
            }
            for index in range(1, 51)
        ]
        answers = [{"id": str(index)} for index in range(1, 51)]

        rows = generate_reference_template.make_template_rows(questions, answers)

        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[0]["question"], "Question 1")
        self.assertEqual(rows[0]["reference_answer"], "")

    def test_blank_reference_answer_stops_evaluation(self):
        """Reject a blank expected answer before any RAGAS evaluation call."""
        answers = [
            {
                "id": "1",
                "query": "Question",
                "llm_answer": "Saved answer",
                "llm_context_filepaths_top_3": "data/example.md",
            }
        ]
        references = [{"id": "1", "reference_answer": ""}]

        with self.assertRaisesRegex(ValueError, "Reference answer is blank"):
            run_ragas_evaluation.validate_and_join_rows(answers, references)

    def test_duplicate_reference_ids_stop_evaluation(self):
        """Reject duplicate reference IDs before any RAGAS evaluation call."""
        answers = [
            {
                "id": "1",
                "query": "Question",
                "llm_answer": "Saved answer",
                "llm_context_filepaths_top_3": "data/example.md",
            }
        ]
        references = [
            {"id": "1", "reference_answer": "Expected answer"},
            {"id": "1", "reference_answer": "Repeated answer"},
        ]

        with self.assertRaisesRegex(ValueError, "duplicate IDs"):
            run_ragas_evaluation.validate_and_join_rows(answers, references)

    def test_context_reader_removes_yaml_front_matter(self):
        """Read a temporary source file and return only its Markdown body."""
        with tempfile.TemporaryDirectory() as directory:
            source_file = Path(directory) / "source.md"
            source_file.write_text("---\ntitle: Sample\n---\nBody text", encoding="utf-8")
            original_root = run_ragas_evaluation.PROJECT_ROOT
            run_ragas_evaluation.PROJECT_ROOT = Path(directory)
            try:
                contexts = run_ragas_evaluation.read_saved_contexts("source.md")
            finally:
                run_ragas_evaluation.PROJECT_ROOT = original_root

        self.assertEqual(contexts, ["Body text"])

    def test_summary_contains_average_score(self):
        """Write a readable summary from one successful evaluation row."""
        row = {
            "id": "1",
            "question": "Question",
            "faithfulness": "1.0",
            "answer_relevancy": "0.8",
            "context_precision": "0.6",
            "context_recall": "0.4",
            "evaluation_status": "Success",
        }
        with tempfile.TemporaryDirectory() as directory:
            summary_file = Path(directory) / "summary.md"
            run_ragas_evaluation.write_summary(
                [row], "answers.csv", "references.csv", summary_file
            )
            summary = summary_file.read_text(encoding="utf-8")

        self.assertIn("faithfulness: 1.0000", summary)
        self.assertIn("ID 1 (0.7000)", summary)


if __name__ == "__main__":
    unittest.main()
