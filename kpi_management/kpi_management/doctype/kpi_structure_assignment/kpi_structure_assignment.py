import frappe
from frappe.model.document import Document
from kpi_management import domain
from kpi_management.common import lock, positive_int
from kpi_management.permissions import require_manager


class KPIStructureAssignment(Document):
    def save(self, *args, **kwargs):
        # Acquire Employee before Frappe's save path locks this document itself.
        # This covers native submit/cancel as well as explicit app services.
        if self.employee:
            lock("Employee", self.employee)
        return super().save(*args, **kwargs)

    def validate(self):
        employee = frappe.get_doc("Employee", self.employee, for_update=True)
        require_manager(
            frappe._dict(
                company=employee.company,
                department=employee.department,
                employee=employee.name,
            )
        )
        old = self.get_doc_before_save()
        if old:
            require_manager(old)
        structure = frappe.get_doc("KPI Structure", self.kpi_structure, for_update=True)
        if structure.docstatus != 1:
            frappe.throw("Select a submitted KPI Structure.")
        if structure.designation != employee.designation or (
            structure.company and structure.company != employee.company
        ):
            frappe.throw("Structure must match the Employee's designation and company.")
        if domain.day(self.start_date) > domain.day(self.end_date):
            frappe.throw("Start Date must not follow End Date.")
        if domain.day(self.start_date) < domain.day(structure.effective_from) or (
            structure.effective_to
            and domain.day(self.end_date) > domain.day(structure.effective_to)
        ):
            frappe.throw("The Structure must cover the full Assignment interval.")
        if not next(
            domain.periods(self.start_date, self.end_date, self.review_frequency), None
        ):
            frappe.throw(
                "Assignment must contain at least one complete calendar review period."
            )
        self.self_due_days = positive_int(self.self_due_days, "Self due days")
        self.final_due_days = positive_int(self.final_due_days, "Final due days")
        self.employee_user = employee.user_id
        for key in ("employee_name", "company", "department", "designation"):
            self.set(key, employee.get(key))
        self.reporting_line = employee.reports_to
        self.structure_version = structure.version

    def before_submit(self):
        lock("Employee", self.employee)
        # Serialize assignment submission against Structure cancellation.
        lock("KPI Structure", self.kpi_structure)
        self.validate()
        employee = frappe.get_doc("Employee", self.employee, for_update=True)
        if (
            employee.status != "Active"
            or not employee.user_id
            or not frappe.db.get_value(
                "User", employee.user_id, "enabled", for_update=True
            )
        ):
            frappe.throw("An active Employee linked to an enabled User is required.")
        if frappe.db.get_value(
            "User", employee.user_id, "user_type"
        ) != "System User" or "Employee" not in frappe.get_roles(employee.user_id):
            frappe.throw(
                "The assigned user needs Desk access (System User) and the Employee role for this release."
            )
        overlap = frappe.db.sql(
            """SELECT name FROM `tabKPI Structure Assignment`
            WHERE employee=%s AND docstatus=1 AND name<>%s AND start_date<=%s AND end_date>=%s LIMIT 1 FOR UPDATE""",
            (self.employee, self.name, self.end_date, self.start_date),
        )
        if overlap:
            frappe.throw(
                "An overlapping submitted Assignment already exists: " + overlap[0][0]
            )

    def before_cancel(self):
        require_manager(self)
        lock("Employee", self.employee)
        lock("KPI Structure Assignment", self.name)
        if frappe.db.sql(
            "SELECT name FROM `tabKPI Review` WHERE kpi_structure_assignment=%s AND docstatus<>2 LIMIT 1 FOR UPDATE",
            self.name,
        ):
            frappe.throw(
                "Resolve every non-cancelled Review, including Drafts, before cancelling the Assignment."
            )

    def on_trash(self):
        require_manager(self)
        if self.docstatus:
            frappe.throw("Retain submitted and cancelled Assignments for audit.")

