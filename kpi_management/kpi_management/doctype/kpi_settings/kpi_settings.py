import frappe
from frappe.model.document import Document
from kpi_management.common import positive_int
from kpi_management.permissions import require_manager


class KPISettings(Document):
    def validate(self):
        require_manager()
        if self.enable_review_generation and not self.generation_from_date:
            frappe.throw("Set Generation From Date before enabling generation.")
        self.default_self_due_days = positive_int(
            self.default_self_due_days, "Default self due days"
        )
        self.default_final_due_days = positive_int(
            self.default_final_due_days, "Default final due days"
        )
        self.reminder_days_before_due = positive_int(
            self.reminder_days_before_due, "Reminder days", 0
        )

