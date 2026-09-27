import frappe
from frappe.model.document import Document
from kpi_management.context import current


class KPIAuditEvent(Document):
    def before_insert(self):
        if current() != "audit":
            frappe.throw(
                "Audit records are created only by KPI services.",
                frappe.PermissionError,
            )

    def validate(self):
        if not self.is_new():
            frappe.throw("KPI audit records are immutable.")

    def on_trash(self):
        frappe.throw("KPI audit records must be retained.")

