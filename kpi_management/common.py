import frappe
from kpi_management import domain
from kpi_management.context import action, current

IDENTITY = (
    "employee_user",
    "employee_name",
    "company",
    "department",
    "designation",
    "reporting_line",
    "structure_version",
)
SNAPSHOT = (
    "kpi_component",
    "objective",
    "metric",
    "indicator",
    "perspective",
    "perspective_label",
    "target_number",
    "target_choice",
    "target_date",
    "target_text",
    "duration_unit",
    "currency",
    "target_display",
)
SYSTEM_FIELDS = {
    "name",
    "doctype",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "parent",
    "parenttype",
    "parentfield",
    "idx",
}


def checked(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (ValueError, KeyError) as exc:
        frappe.throw(str(exc))


def lock(doctype, name):
    # Identifiers are exclusively passed by trusted Python callers.
    if doctype not in {
        "Employee",
        "Designation",
        "KPI Structure Assignment",
        "KPI Review",
        "KPI Structure",
    }:
        raise ValueError("Unsupported lock")
    found = frappe.db.sql(
        f"SELECT name FROM `tab{doctype}` WHERE name=%s FOR UPDATE", (name,)
    )
    if not found:
        frappe.throw(f"{doctype} does not exist", frappe.DoesNotExistError)


def lock_assignment(name):
    employee = frappe.db.get_value("KPI Structure Assignment", name, "employee")
    if not employee:
        frappe.throw("Assignment not found", frappe.DoesNotExistError)
    lock("Employee", employee)
    lock("KPI Structure Assignment", name)
    return frappe.get_doc("KPI Structure Assignment", name, for_update=True)


def audit(doc, event_type, reason="", payload=None):
    values = {
        "doctype": "KPI Audit Event",
        "event_type": event_type,
        "reference_doctype": doc.doctype,
        "reference_name": doc.name,
        "employee": doc.get("employee"),
        "actor": frappe.session.user,
        "reason": reason,
        "payload": frappe.as_json(payload or {}),
        "assignment_name": doc.get("kpi_structure_assignment"),
        "period_start": doc.get("period_start"),
        "period_end": doc.get("period_end"),
    }
    for key in IDENTITY[:5]:
        values[key] = doc.get(key)
    with action("audit"):
        return frappe.get_doc(values).insert(ignore_permissions=True)


def positive_int(value, label, minimum=1):
    n = checked(domain.decimal, value, 0)
    if n < minimum or n > 2147483647:
        frappe.throw(
            f"{label} must be an integer of at least {minimum}, within the Int field range"
        )
    return int(n)


def no_direct_mutation(doc):
    if not current(doc):
        frappe.throw(
            "Use the KPI action buttons/API; direct document edits are not permitted.",
            frappe.PermissionError,
        )

