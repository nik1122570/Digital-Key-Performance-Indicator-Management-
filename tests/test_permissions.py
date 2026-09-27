"""Policy tests use a small Frappe stub; real database tests live in kpi_management/tests."""

import importlib
import sys
import types
import unittest
from unittest.mock import patch


class Attr(dict):
    def __getattr__(self, key):
        return self.get(key)


def stub_frappe():
    fake = types.ModuleType("frappe")
    fake.session = Attr(user="employee@example.test")
    fake.records = {}
    fake.grants = {}
    fake.user_roles = {}
    fake.get_roles = lambda user=None: fake.user_roles.get(
        user or fake.session.user, []
    )
    fake.get_all = lambda dtype, filters=None, fields=None, **kw: fake.grants.get(
        (filters or {}).get("user"), []
    )

    def get_value(doctype, name, field):
        return fake.records.get((doctype, name), {}).get(field)

    fake.db = Attr(
        get_value=get_value, escape=lambda value: "'" + value.replace("'", "''") + "'"
    )
    fake.PermissionError = PermissionError
    fake.ValidationError = ValueError
    fake.TimestampMismatchError = RuntimeError
    fake.DoesNotExistError = KeyError
    fake._dict = Attr

    def throw(message, exc=ValueError):
        raise exc(message)

    fake.throw = throw
    return fake


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.fake = stub_frappe()
        self.patch = patch.dict(sys.modules, {"frappe": self.fake})
        self.patch.start()
        import kpi_management.permissions

        self.p = importlib.reload(kpi_management.permissions)
        for user in [
            "employee@example.test",
            "reviewer@example.test",
            "manager@example.test",
            "outsider@example.test",
            "admin@example.test",
        ]:
            self.fake.records["User", user] = {"enabled": 1}
        self.fake.records["Employee", "EMP-1"] = {"user_id": "employee@example.test"}
        self.doc = Attr(
            employee="EMP-1",
            employee_user="employee@example.test",
            company="A",
            department="D1",
        )
        self.fake.user_roles["reviewer@example.test"] = ["KPI Final Reviewer"]
        self.fake.user_roles["manager@example.test"] = ["KPI Manager"]
        self.fake.user_roles["admin@example.test"] = ["System Manager"]

    def tearDown(self):
        self.patch.stop()

    def grant(self, user, kind, value, all_doctypes=True):
        self.fake.grants.setdefault(user, []).append(
            Attr(
                allow=kind,
                for_value=value,
                apply_to_all_doctypes=all_doctypes,
                applicable_for="" if all_doctypes else "Sales Invoice",
            )
        )

    def test_own_assessment_only(self):
        self.assertTrue(self.p.is_employee(self.doc, "employee@example.test"))
        self.assertFalse(self.p.is_employee(self.doc, "manager@example.test"))
        self.assertFalse(self.p.is_employee(self.doc, "admin@example.test"))

    def test_changed_or_disabled_identity_blocks_self(self):
        self.fake.records["Employee", "EMP-1"]["user_id"] = "new@example.test"
        self.assertFalse(self.p.is_employee(self.doc, "employee@example.test"))
        self.fake.records["Employee", "EMP-1"]["user_id"] = "employee@example.test"
        self.fake.records["User", "employee@example.test"]["enabled"] = 0
        self.assertFalse(self.p.is_employee(self.doc, "employee@example.test"))

    def test_role_alone_does_not_grant_scope(self):
        self.assertFalse(self.p.is_reviewer(self.doc, "reviewer@example.test"))
        self.assertFalse(self.p.is_manager(self.doc, "manager@example.test"))

    def test_company_department_employee_intersection(self):
        u = "reviewer@example.test"
        self.grant(u, "Company", "A")
        self.assertTrue(self.p.is_reviewer(self.doc, u))
        self.grant(u, "Department", "D2")
        self.assertFalse(self.p.is_reviewer(self.doc, u))
        self.grant(u, "Department", "D1")
        self.assertTrue(self.p.is_reviewer(self.doc, u))
        self.grant(u, "Employee", "EMP-2")
        self.assertFalse(self.p.is_reviewer(self.doc, u))
        self.grant(u, "Employee", "EMP-1")
        self.assertTrue(self.p.is_reviewer(self.doc, u))

    def test_no_self_final_even_with_reviewer_role(self):
        u = "employee@example.test"
        self.fake.user_roles[u] = ["Employee", "KPI Final Reviewer"]
        self.grant(u, "Company", "A")
        self.assertFalse(self.p.is_reviewer(self.doc, u))

    def test_other_app_permission_does_not_grant_access(self):
        self.grant("reviewer@example.test", "Company", "A", False)
        self.assertFalse(self.p.is_reviewer(self.doc, "reviewer@example.test"))

    def test_list_filters_match_access_boundaries(self):
        u = "reviewer@example.test"
        self.grant(u, "Company", "A's Company")
        sql = self.p.access_sql("r", u)
        self.assertIn("A''s Company", sql)
        self.assertIn("employee_user", sql)
        self.assertIn("1=0", self.p.scope_sql("r", "outsider@example.test"))

    def test_technical_read_does_not_grant_rating(self):
        self.assertTrue(self.p.can_read(self.doc, "admin@example.test"))
        self.assertFalse(self.p.is_reviewer(self.doc, "admin@example.test"))

    def test_sharing_cannot_override_review_hooks(self):
        self.assertFalse(
            self.p.review_permission(self.doc, "read", "outsider@example.test")
        )
        self.assertFalse(
            self.p.review_permission(self.doc, "share", "employee@example.test")
        )

    def test_scope_denies_other_company(self):
        self.grant("manager@example.test", "Company", "B")
        self.assertFalse(self.p.is_manager(self.doc, "manager@example.test"))


if __name__ == "__main__":
    unittest.main()

