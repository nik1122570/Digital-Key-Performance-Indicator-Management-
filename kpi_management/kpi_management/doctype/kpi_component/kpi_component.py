import frappe
from frappe.model.document import Document
from kpi_management.permissions import require_manager


class KPIComponent(Document):
    def validate(self):
        require_manager()
        self.objective = (self.objective or "").strip()
        self.metric = (self.metric or "").strip()
        if not self.objective or len(self.objective) > 140 or not self.metric:
            frappe.throw(
                "Objective must contain 1–140 characters and Metric is required."
            )
        old = self.get_doc_before_save()
        if old and old.objective != self.objective:
            frappe.throw("Create a replacement Component to change its objective/name.")
        if old and (old.indicator != self.indicator or old.metric != self.metric):
            used = frappe.db.sql(
                """SELECT i.name FROM `tabKPI Structure Item` i
                JOIN `tabKPI Structure` s ON s.name=i.parent
                WHERE i.kpi_component=%s AND s.docstatus IN (1,2) LIMIT 1""",
                self.name,
            )
            if used:
                frappe.throw(
                    "This Component has submitted history. Use a replacement Component for a changed metric or indicator."
                )

    def on_trash(self):
        require_manager()

    def before_rename(self, *args, **kwargs):
        frappe.throw("KPI Components cannot be renamed; create a replacement.")

