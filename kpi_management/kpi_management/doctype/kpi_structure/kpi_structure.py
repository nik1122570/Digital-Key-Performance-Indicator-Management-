import re
import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from kpi_management import domain
from kpi_management.common import checked, lock
from kpi_management.permissions import require_manager, scope


class KPIStructure(Document):
    def save(self, *args, **kwargs):
        if self.designation:
            lock("Designation", self.designation)
        return super().save(*args, **kwargs)

    def autoname(self):
        prefix = re.sub(r"[^A-Z0-9]+", "-", self.designation.upper()).strip("-")[:95]
        self.name = make_autoname(f"{prefix}-KPI-.####")

    def validate(self):
        require_manager()
        old = self.get_doc_before_save()
        for company in (self.company, old.company if old else None):
            if company and company not in scope()["Company"]:
                frappe.throw(
                    "Company is outside your explicit scope.", frappe.PermissionError
                )
        if self.effective_to and domain.day(self.effective_from) > domain.day(
            self.effective_to
        ):
            frappe.throw("Structure Effective From must not follow Effective To.")
        self.version = old.version if old else 0
        for row in self.components:
            if not row.kpi_component:
                continue
            component = frappe.get_doc("KPI Component", row.kpi_component)
            for key in ("objective", "metric", "indicator"):
                row.set(key, component.get(key))
            row.perspective = row.perspective or component.perspective
            row.perspective_label = frappe.db.get_value(
                "KPI Perspective", row.perspective, "perspective_name"
            )
            row.target_display = checked(domain.display_value, row.as_dict(), "target")
            checked(domain.decimal, row.weight, 2)
        self.total_weight = float(
            sum(
                (checked(domain.decimal, r.weight, 2) for r in self.components),
                domain.Decimal(0),
            )
        )

    def before_submit(self):
        lock("Designation", self.designation)
        checked(domain.validate_weights, [r.as_dict() for r in self.components])
        for row in self.components:
            if frappe.db.get_value("KPI Component", row.kpi_component, "disabled"):
                frappe.throw(f"Component {row.kpi_component} is disabled.")
            if not row.perspective or frappe.db.get_value(
                "KPI Perspective", row.perspective, "disabled"
            ):
                frappe.throw("An enabled Perspective is required for every row.")
        versions = frappe.db.sql(
            """SELECT version FROM `tabKPI Structure`
            WHERE designation=%s AND COALESCE(company,'')=%s FOR UPDATE""",
            (self.designation, self.company or ""),
        )
        self.version = max((int(r[0] or 0) for r in versions), default=0) + 1

    def before_cancel(self):
        require_manager()
        if self.company and self.company not in scope()["Company"]:
            frappe.throw("Company is outside your scope.", frappe.PermissionError)
        lock("KPI Structure", self.name)
        if frappe.db.sql(
            "SELECT name FROM `tabKPI Structure Assignment` WHERE kpi_structure=%s AND docstatus=1 LIMIT 1 FOR UPDATE",
            self.name,
        ):
            frappe.throw(
                "Cancel dependent submitted Assignments deliberately before cancelling this Structure."
            )

    def on_trash(self):
        require_manager()
        if self.docstatus:
            frappe.throw("Retain submitted and cancelled Structures for audit.")

