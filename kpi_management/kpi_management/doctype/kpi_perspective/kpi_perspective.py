import frappe
from frappe.model.document import Document
from kpi_management.permissions import require_manager


class KPIPerspective(Document):
    def validate(self):
        require_manager()
        self.perspective_name = (self.perspective_name or "").strip()
        if not self.perspective_name or len(self.perspective_name) > 140:
            frappe.throw("Perspective name must contain 1–140 characters.")

    def on_trash(self):
        require_manager()

