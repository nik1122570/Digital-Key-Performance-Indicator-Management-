import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestPackage(unittest.TestCase):
    def setUp(self):
        self.metadata = {}
        for path in (ROOT / "kpi_management/kpi_management/doctype").glob("*/*.json"):
            doc = json.loads(path.read_text())
            self.metadata[doc["name"]] = doc

    def test_json_and_python_syntax(self):
        for path in ROOT.rglob("*.json"):
            with self.subTest(file=path):
                json.loads(path.read_text())
        for path in ROOT.rglob("*.py"):
            with self.subTest(file=path):
                ast.parse(path.read_text(), filename=str(path))

    def test_lifecycles(self):
        for name in ["KPI Component", "KPI Perspective", "KPI Settings"]:
            self.assertEqual(self.metadata[name]["is_submittable"], 0)
        for name in ["KPI Structure", "KPI Structure Assignment", "KPI Review"]:
            self.assertEqual(self.metadata[name]["is_submittable"], 1)
            self.assertIn("amended_from", self.metadata[name]["field_order"])

    def test_removed_features_absent(self):
        self.assertNotIn("KPI Scoring Band", self.metadata)
        self.assertNotIn("KPI Assignment Target Override", self.metadata)
        fields = self.metadata["KPI Component"]["field_order"]
        self.assertEqual(
            set(fields), {"objective", "metric", "indicator", "perspective", "disabled"}
        )
        for name in ["KPI Structure Item", "KPI Review Item"]:
            self.assertNotIn("target_value_2", self.metadata[name]["field_order"])

    def test_field_order_and_child_links(self):
        for name, doc in self.metadata.items():
            fields = doc["fields"]
            self.assertEqual(doc["field_order"], [f["fieldname"] for f in fields])
            self.assertEqual(len(fields), len(set(doc["field_order"])))
            for field in fields:
                if field["fieldtype"] == "Table":
                    self.assertEqual(self.metadata[field["options"]]["istable"], 1)
                self.assertFalse(field.get("allow_on_submit"), (name, field))

    def test_review_payload_not_directly_editable(self):
        self.assertTrue(
            all(f.get("read_only") for f in self.metadata["KPI Review"]["fields"])
        )
        self.assertTrue(
            all(f.get("read_only") for f in self.metadata["KPI Review Item"]["fields"])
        )

    def test_scheduler_disabled_by_default(self):
        fields = {f["fieldname"]: f for f in self.metadata["KPI Settings"]["fields"]}
        self.assertEqual(fields["enable_review_generation"]["default"], "0")

    def test_reports_and_print_format(self):
        reports = list((ROOT / "kpi_management/kpi_management/report").glob("*/*.json"))
        self.assertEqual(len(reports), 11)
        for p in reports:
            self.assertTrue(p.with_suffix(".py").exists())
            self.assertTrue(p.with_suffix(".js").exists())
        p = ROOT / "kpi_management/kpi_management/print_format/kpi_scorecard/kpi_scorecard.json"
        self.assertEqual(
            json.loads(p.read_text())["html"],
            (ROOT / "kpi_management/templates/kpi_scorecard.html").read_text(),
        )

    def test_no_secrets_or_generated_bytecode(self):
        # Distribution check intentionally skips local interpreter caches.
        for path in ROOT.rglob("*"):
            self.assertNotIn(
                path.name, [".env", "site_config.json", "common_site_config.json"]
            )


if __name__ == "__main__":
    unittest.main()

