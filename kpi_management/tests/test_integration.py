"""Run ONLY on an isolated v15 test site with ERPNext, HRMS and SF KPI installed.

These tests use real Frappe documents and transactions. They have not been run
in the authoring workspace, which has no Frappe/MariaDB runtime.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from kpi_management import api, reviews
from kpi_management.permissions import can_read


class TestKPIIntegration(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.token = frappe.generate_hash(length=8)
        self.company = frappe.get_doc(
            {
                "doctype": "Company",
                "company_name": "_Test KPI " + self.token,
                "abbr": self.token[:5].upper(),
                "default_currency": "TZS",
                "country": "Tanzania",
            }
        ).insert()
        self.designation = frappe.get_doc(
            {
                "doctype": "Designation",
                "designation_name": "_Test KPI Role " + self.token,
            }
        ).insert()
        self.manager = self.make_user("manager", ["KPI Manager"])
        self.reviewer = self.make_user("reviewer", ["KPI Final Reviewer"])
        self.employee_user = self.make_user("employee", ["Employee"])
        self.outsider = self.make_user("outsider", ["Employee", "KPI Final Reviewer"])
        for user in [self.manager, self.reviewer]:
            frappe.get_doc(
                {
                    "doctype": "User Permission",
                    "user": user,
                    "allow": "Company",
                    "for_value": self.company.name,
                    "apply_to_all_doctypes": 1,
                }
            ).insert(ignore_permissions=True)
            frappe.clear_cache(user=user)
        self.employee = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "KPI Test",
                "last_name": self.token,
                "company": self.company.name,
                "designation": self.designation.name,
                "gender": "Male",
                "date_of_birth": "1990-01-01",
                "date_of_joining": "2020-01-01",
                "status": "Active",
                "user_id": self.employee_user,
                "create_user_permission": 0,
            }
        ).insert()
        frappe.set_user(self.manager)
        self.perspective = frappe.get_doc(
            {
                "doctype": "KPI Perspective",
                "perspective_name": "_Test KPI Perspective " + self.token,
            }
        ).insert()
        components = []
        for i, w in enumerate([40, 30, 20, 10], 1):
            component = frappe.get_doc(
                {
                    "doctype": "KPI Component",
                    "objective": f"_Test {self.token} Component {i}",
                    "metric": "Meet the agreed quantity.",
                    "indicator": "Number",
                    "perspective": self.perspective.name,
                }
            ).insert()
            components.append(
                {"kpi_component": component.name, "weight": w, "target_number": 10}
            )
        self.structure = frappe.get_doc(
            {
                "doctype": "KPI Structure",
                "designation": self.designation.name,
                "company": self.company.name,
                "effective_from": "2024-01-01",
                "effective_to": "2024-12-31",
                "components": components,
            }
        ).insert()
        self.structure.submit()
        self.assignment = frappe.get_doc(
            {
                "doctype": "KPI Structure Assignment",
                "employee": self.employee.name,
                "kpi_structure": self.structure.name,
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "review_frequency": "Quarterly",
                "self_due_days": 7,
                "final_due_days": 7,
            }
        ).insert()
        self.assignment.submit()
        self.review = reviews.create_review(
            self.assignment.name, "2024-04-01", "2024-06-30"
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def make_user(self, tag, roles):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": f"kpi-{tag}-{self.token}@example.test",
                "first_name": "KPI " + tag,
                "enabled": 1,
                "user_type": "System User",
                "send_welcome_email": 0,
                "roles": [{"role": r} for r in roles],
            }
        ).insert(ignore_permissions=True)
        return user.name

    def refresh_review(self):
        self.review = frappe.get_doc("KPI Review", self.review.name)
        return self.review

    def self_assess(self, exclude=False):
        frappe.set_user(self.employee_user)
        doc = self.refresh_review()
        entries = [
            {
                "name": r.name,
                "actual_number": 10,
                "self_rating": r.original_weight * 0.8,
                "employee_comment": "Assessment evidence retained.",
            }
            for r in doc.items
            if not r.not_applicable
        ]
        api.record_self(
            doc.name, doc.modified, entries, {"employee_summary": "Quarter completed."}
        )
        doc = self.refresh_review()
        api.send_for_final(doc.name, doc.modified)
        return self.refresh_review()

    def finish(self):
        self.self_assess()
        frappe.set_user(self.reviewer)
        doc = self.refresh_review()
        entries = [
            {
                "name": r.name,
                "final_rating": r.original_weight,
                "reviewer_comment": "Verified above self assessment.",
            }
            for r in doc.items
            if not r.not_applicable
        ]
        api.record_final(
            doc.name, doc.modified, entries, {"final_summary": "Targets reviewed."}
        )
        doc = self.refresh_review()
        api.complete(doc.name, doc.modified)
        return self.refresh_review()

    def test_full_review_workflow_and_official_total(self):
        doc = self.finish()
        self.assertEqual(doc.docstatus, 1)
        self.assertEqual(doc.workflow_state, "Completed")
        self.assertEqual(doc.final_total, 100)
        self.assertEqual(doc.rating_category, "Outstanding")
        self.assertEqual(doc.self_sent_by, self.employee_user)
        self.assertEqual(doc.final_reviewed_by, self.reviewer)

    def test_zero_is_valid_but_blank_is_incomplete(self):
        frappe.set_user(self.employee_user)
        with self.assertRaises(frappe.ValidationError):
            api.send_for_final(self.review.name, self.review.modified)
        entries = [
            {
                "name": r.name,
                "actual_number": 0,
                "self_rating": 0,
                "employee_comment": "Zero result.",
            }
            for r in self.review.items
        ]
        api.record_self(
            self.review.name,
            self.review.modified,
            entries,
            {"employee_summary": "No output."},
        )
        doc = self.refresh_review()
        api.send_for_final(doc.name, doc.modified)
        doc = self.refresh_review()
        self.assertEqual(doc.self_total, 0)
        self.assertTrue(doc.self_complete)

    def test_direct_write_and_proxy_self_are_rejected(self):
        frappe.set_user(self.manager)
        with self.assertRaises(frappe.PermissionError):
            api.record_self(self.review.name, self.review.modified, [], {})
        doc = self.refresh_review()
        doc.items[0].original_weight = 99
        with self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)
        with self.assertRaises(frappe.PermissionError):
            doc.submit()

    def test_scope_for_form_list_and_report(self):
        from kpi_management.reports import execute

        frappe.set_user(self.outsider)
        self.assertFalse(can_read(self.review))
        self.assertFalse(
            frappe.get_list(
                "KPI Review", filters={"name": self.review.name}, pluck="name"
            )
        )
        self.assertEqual(
            execute("KPI Review Completion Status", {"employee": self.employee.name})[
                1
            ],
            [],
        )
        with self.assertRaises(frappe.PermissionError):
            api.capabilities(self.review.name)

    def test_exclusion_invalidates_handoff_and_renormalizes(self):
        self.self_assess()
        frappe.set_user(self.reviewer)
        doc = self.refresh_review()
        api.set_applicability(
            doc.name, doc.modified, doc.items[2].name, 1, "Not in role this period."
        )
        doc = self.refresh_review()
        self.assertEqual(doc.workflow_state, "Pending Self Rating")
        self.assertEqual([r.effective_weight for r in doc.items], [50, 37.5, 0, 12.5])
        self.assertEqual(doc.self_accepted_revision, -1)
        self.assertEqual(doc.applicability_revision, 1)
        self.assertFalse(any(r.final_rating_entered for r in doc.items))

    def test_duplicate_period_and_cancelled_history_require_amendment(self):
        with self.assertRaises(frappe.ValidationError):
            reviews.create_review(self.assignment.name, "2024-04-01", "2024-06-30")
        self.finish()
        frappe.set_user(self.manager)
        doc = self.refresh_review()
        api.cancel(doc.name, doc.modified, "Correct recorded assessment.")
        doc = self.refresh_review()
        with self.assertRaises(frappe.ValidationError):
            reviews.create_review(self.assignment.name, "2024-04-01", "2024-06-30")
        new = api.amend(doc.name, doc.modified, "Fresh assessment required.")
        self.assertEqual(new["docstatus"], 0)
        self.assertEqual(new["amended_from"], doc.name)
        self.assertEqual(new["review_revision"], 1)
        self.assertFalse(
            any(
                r["self_rating_entered"] or r["final_rating_entered"]
                for r in new["items"]
            )
        )

    def test_dependency_cancellation_blocked(self):
        with self.assertRaises(frappe.ValidationError):
            self.assignment.cancel()
        with self.assertRaises(frappe.ValidationError):
            self.structure.cancel()

    def test_stale_request_rejected(self):
        frappe.set_user(self.employee_user)
        api.record_self(
            self.review.name,
            self.review.modified,
            [],
            {"employee_summary": "First update"},
        )
        with self.assertRaises(frappe.TimestampMismatchError):
            api.record_self(
                self.review.name,
                self.review.modified,
                [],
                {"employee_summary": "Stale update"},
            )

    def test_deleted_draft_not_silently_recreated(self):
        frappe.set_user(self.manager)
        api.delete_draft(
            self.review.name,
            self.review.modified,
            "Wrong agreement; correction needed.",
        )
        self.assertFalse(frappe.db.exists("KPI Review", self.review.name))
        self.assertTrue(
            frappe.db.exists(
                "KPI Audit Event",
                {
                    "reference_name": self.review.name,
                    "event_type": "Draft deleted for correction",
                },
            )
        )
        with self.assertRaises(frappe.ValidationError):
            reviews.create_review(self.assignment.name, "2024-04-01", "2024-06-30")
        result = api.recover_period(
            self.assignment.name,
            "2024-04-01",
            "2024-06-30",
            "Source checked and correction completed.",
        )
        self.assertEqual(result["docstatus"], 0)

    def test_disabled_component_does_not_break_existing_agreement(self):
        component = frappe.get_doc(
            "KPI Component", self.structure.components[0].kpi_component
        )
        component.disabled = 1
        component.save()
        other = reviews.create_review(self.assignment.name, "2024-07-01", "2024-09-30")
        self.assertEqual(other.docstatus, 0)
        self.assertEqual(other.items[0].target_number, 10)

    def test_private_evidence_access_and_audited_deletion(self):
        from frappe.utils.file_manager import save_file

        frappe.set_user(self.employee_user)
        evidence = save_file(
            "kpi-test-evidence.txt",
            b"Synthetic evidence only",
            "KPI Review",
            self.review.name,
            is_private=1,
        )
        self.assertTrue(evidence.is_downloadable())
        frappe.set_user(self.outsider)
        protected = frappe.get_doc("File", evidence.name)
        self.assertFalse(protected.is_downloadable())
        with self.assertRaises(frappe.PermissionError):
            protected.get_content()
        frappe.set_user(self.manager)
        doc = self.refresh_review()
        api.delete_draft(doc.name, doc.modified, "Preserve evidence during correction.")
        archived = frappe.get_doc("File", evidence.name)
        self.assertEqual(archived.attached_to_doctype, "KPI Audit Event")
        self.assertTrue(archived.is_private)
        content = archived.get_content()
        self.assertEqual(
            content.decode() if isinstance(content, bytes) else content,
            "Synthetic evidence only",
        )

    def test_public_kpi_evidence_rejected_before_write(self):
        frappe.set_user(self.employee_user)
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "File",
                    "file_name": "kpi-public-test.txt",
                    "content": "Synthetic public test",
                    "is_private": 0,
                    "attached_to_doctype": "KPI Review",
                    "attached_to_name": self.review.name,
                }
            ).insert()

