import frappe
from frappe.model.document import Document
from kpi_management.common import no_direct_mutation
from kpi_management.context import current
from kpi_management.permissions import require_manager, require_reviewer
from kpi_management.reviews import recalculate, sources, validate_final


class KPIReview(Document):
    def before_validate(self):
        no_direct_mutation(self)

    def before_insert(self):
        if current(self) != "create":
            frappe.throw(
                "Create Reviews through the generation/amendment service.",
                frappe.PermissionError,
            )

    def validate(self):
        no_direct_mutation(self)
        sources(self)
        expected = {
            0: ("Pending Self Rating", "Pending Final Rating"),
            1: ("Completed",),
            2: ("Cancelled",),
        }
        if self.workflow_state not in expected[int(self.docstatus)]:
            frappe.throw("Workflow state and document status disagree.")
        if current(self) != "create":
            old = self.get_doc_before_save()
            if not old or old.docstatus != 0:
                frappe.throw("Submitted business data is immutable.")
            if (
                old.employee != self.employee
                or old.kpi_structure_assignment != self.kpi_structure_assignment
                or old.period_start != self.period_start
                or old.period_end != self.period_end
            ):
                frappe.throw("The Review identity is immutable.")
        for row in self.items:
            if row.not_applicable and (
                not row.na_reason or not row.na_decided_by or not row.na_decided_on
            ):
                frappe.throw(
                    "Every exclusion requires a reason, reviewer and timestamp."
                )
        recalculate(self)

    def before_submit(self):
        if current(self) != "complete":
            frappe.throw(
                "Use Complete and Submit after both assessments are valid.",
                frappe.PermissionError,
            )
        require_reviewer(self)
        validate_final(self)
        if not self.final_reviewed_by or self.final_reviewed_by != frappe.session.user:
            frappe.throw("Missing final reviewer acknowledgement.")

    def before_cancel(self):
        if current(self) != "cancel":
            frappe.throw(
                "Use Cancel Review and record the reason.", frappe.PermissionError
            )
        require_manager(self)
        self.workflow_state = "Cancelled"
        self.rating_category = ""

    def on_trash(self):
        if current(self) != "delete" or self.docstatus != 0:
            frappe.throw(
                "Reviews can only be removed through the audited Draft correction action.",
                frappe.PermissionError,
            )
        require_manager(self)

