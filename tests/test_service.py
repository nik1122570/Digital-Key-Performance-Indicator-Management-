import importlib
import sys
import types
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from unittest.mock import patch
from test_permissions import Attr, stub_frappe
from kpi_management.context import action, current


class Row:
    def __init__(self, **values):
        self.__dict__.update(values)

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def set(self, key, value):
        setattr(self, key, value)

    def as_dict(self):
        return dict(self.__dict__)

    def __getattr__(self, key):
        return None


class TestReviewActions(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fake = stub_frappe()
        self.fake.utils = types.ModuleType("frappe.utils")
        self.fake.utils.add_days = lambda d, n: (
            (datetime.fromisoformat(str(d)) + timedelta(days=n)).date().isoformat()
        )
        self.fake.utils.get_datetime = lambda d: datetime.fromisoformat(str(d))
        self.fake.utils.now_datetime = lambda: datetime(2026, 7, 1, 10)
        self.fake.utils.today = lambda: "2026-07-01"
        notifications = types.ModuleType("kpi_management.notifications")
        notifications.queue_event = lambda *a, **k: None
        self.stack.enter_context(
            patch.dict(
                sys.modules,
                {
                    "frappe": self.fake,
                    "frappe.utils": self.fake.utils,
                    "kpi_management.notifications": notifications,
                },
            )
        )
        import kpi_management.common, kpi_management.permissions, kpi_management.reviews

        importlib.reload(kpi_management.common)
        importlib.reload(kpi_management.permissions)
        self.r = importlib.reload(kpi_management.reviews)
        for method in [
            "require_employee",
            "require_reviewer",
            "require_manager",
            "sources",
            "audit",
        ]:
            self.stack.enter_context(patch.object(self.r, method, lambda *a, **k: None))
        self.doc = Row(
            name="KPR-1",
            docstatus=0,
            workflow_state="Pending Self Rating",
            employee_user="employee@example.test",
            employee="EMP-1",
            applicability_revision=0,
            self_accepted_revision=-1,
            employee_summary="Delivered objectives.",
            modified="2026-07-01 09:00:00",
            kpi_structure_assignment="KSA-1",
            items=[],
        )
        self.doc.items = [
            Row(
                name=f"ROW-{i}",
                idx=i,
                structure_item_id=f"S-{i}",
                original_weight=w,
                indicator="Number",
                actual_number=0,
                actual_choice=None,
                actual_date=None,
                actual_text=None,
                actual_entered=0,
                self_rating=0,
                self_rating_entered=0,
                final_rating=0,
                final_rating_entered=0,
                not_applicable=0,
                employee_comment="",
                reviewer_comment="",
            )
            for i, w in [(1, 40), (2, 60)]
        ]
        self.doc.save = lambda **kwargs: self.r.recalculate(self.doc)
        self.fake.get_doc = lambda *args: Row(final_due_days=7)

    def test_context_not_spoofable_by_document_flags(self):
        self.doc.flags = Attr(kpi_action="complete")
        self.assertIsNone(current(self.doc))
        with action("complete", "KPR-1"):
            self.assertEqual(current(self.doc), "complete")
        self.assertIsNone(current(self.doc))

    def test_explicit_zero_is_valid_and_marked(self):
        self.r.save_entries(
            self.doc,
            [
                dict(
                    name="ROW-1",
                    actual_number=0,
                    self_rating=0,
                    employee_comment="No output",
                )
            ],
            {},
        )
        row = self.doc.items[0]
        self.assertEqual(row.actual_entered, 1)
        self.assertEqual(row.self_rating_entered, 1)
        self.assertEqual(row.actual_number, 0)

    def test_absent_rating_or_actual_rejected(self):
        for entry in [
            dict(name="ROW-1", actual_number=0),
            dict(name="ROW-1", self_rating=0),
        ]:
            with self.assertRaises(ValueError):
                self.r.save_entries(self.doc, [entry], {})

    def test_client_entered_flag_and_snapshot_rejected(self):
        for key in [
            "self_rating_entered",
            "original_weight",
            "indicator",
            "not_applicable",
        ]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.r.save_entries(
                    self.doc,
                    [dict(name="ROW-1", actual_number=1, self_rating=1, **{key: 1})],
                    {},
                )

    def test_duplicate_rows_rejected(self):
        entry = dict(name="ROW-1", actual_number=1, self_rating=1)
        with self.assertRaises(ValueError):
            self.r.save_entries(self.doc, [entry, entry], {})

    def test_clear_entry_invalidates_completion(self):
        self.r.save_entries(
            self.doc, [dict(name="ROW-1", actual_number=1, self_rating=1)], {}
        )
        self.r.save_entries(self.doc, [dict(name="ROW-1", clear=1)], {})
        self.assertEqual(self.doc.items[0].actual_entered, 0)
        self.assertEqual(self.doc.items[0].self_rating_entered, 0)

    def test_self_cannot_write_final_stage(self):
        self.doc.workflow_state = "Pending Final Rating"
        with self.assertRaises(ValueError):
            self.r.save_entries(self.doc, [], {})

    def test_exclusion_reopens_and_clears_final(self):
        self.doc.workflow_state = "Pending Final Rating"
        self.doc.self_accepted_revision = 0
        for row in self.doc.items:
            row.final_rating_entered = 1
            row.final_rating = 10
        self.r.applicability(self.doc, "ROW-1", 1, "Role changed")
        self.assertEqual(self.doc.workflow_state, "Pending Self Rating")
        self.assertEqual(self.doc.applicability_revision, 1)
        self.assertEqual(self.doc.self_accepted_revision, -1)
        self.assertEqual(self.doc.items[1].effective_weight, 100)
        self.assertTrue(all(not r.final_rating_entered for r in self.doc.items))

    def test_reinstatement_requires_fresh_self_entry(self):
        row = self.doc.items[0]
        row.not_applicable = 1
        row.actual_entered = 1
        row.self_rating_entered = 1
        self.r.applicability(self.doc, "ROW-1", 0, "Work now applicable")
        self.assertEqual(row.actual_entered, 0)
        self.assertEqual(row.self_rating_entered, 0)

    def test_all_excluded_blocks_handoff(self):
        for row in self.doc.items:
            row.not_applicable = 1
        with self.assertRaises(ValueError):
            self.r.validate_self(self.doc)

    def test_final_variance_requires_comment(self):
        for row in self.doc.items:
            row.actual_entered = 1
            row.self_rating_entered = 1
            row.final_rating_entered = 1
            row.employee_comment = "Done"
            row.self_rating = 10
            row.final_rating = 20
        self.doc.self_sent_by = self.doc.employee_user
        self.doc.self_accepted_revision = 0
        self.doc.final_summary = "Done"
        with self.assertRaises(ValueError):
            self.r.validate_final(self.doc)

    def test_low_result_requires_improvement_actions(self):
        for row in self.doc.items:
            row.actual_entered = 1
            row.self_rating_entered = 1
            row.final_rating_entered = 1
            row.employee_comment = "Done"
            row.self_rating = 10
            row.final_rating = 10
        self.doc.self_sent_by = self.doc.employee_user
        self.doc.self_accepted_revision = 0
        self.doc.final_summary = "Done"
        with self.assertRaises(ValueError):
            self.r.validate_final(self.doc)
        self.doc.improvement_actions = "Weekly support and milestone review"
        self.r.validate_final(self.doc)

    def test_old_acknowledgement_rejected(self):
        for row in self.doc.items:
            row.actual_entered = 1
            row.self_rating_entered = 1
            row.employee_comment = "Done"
        self.doc.self_sent_by = self.doc.employee_user
        self.doc.self_accepted_revision = 0
        self.doc.applicability_revision = 1
        with self.assertRaises(ValueError):
            self.r.validate_final(self.doc)


if __name__ == "__main__":
    unittest.main()

