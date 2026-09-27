"""Narrow authenticated APIs. No arbitrary document payloads or field setters."""

import frappe
from kpi_management import reviews
from kpi_management.common import audit
from kpi_management.permissions import (
    can_read,
    is_employee,
    is_manager,
    is_reviewer,
    require_employee,
    require_manager,
)


def parse(value, expected):
    value = frappe.parse_json(value) if isinstance(value, str) else value
    if not isinstance(value, expected):
        frappe.throw("Invalid request data.")
    return value


@frappe.whitelist()
def capabilities(name):
    doc = frappe.get_doc("KPI Review", name)
    if not can_read(doc):
        frappe.throw("Review access denied.", frappe.PermissionError)
    return {
        "employee": is_employee(doc),
        "reviewer": is_reviewer(doc),
        "manager": is_manager(doc),
    }


@frappe.whitelist(methods=["POST"])
def record_self(name, modified, entries, summary=None):
    return reviews.save_entries(
        reviews.locked_review(name, modified),
        parse(entries, list),
        parse(summary or {}, dict),
    ).as_dict()


@frappe.whitelist(methods=["POST"])
def record_final(name, modified, entries, summary=None):
    return reviews.save_entries(
        reviews.locked_review(name, modified),
        parse(entries, list),
        parse(summary or {}, dict),
        final=True,
    ).as_dict()


@frappe.whitelist(methods=["POST"])
def send_for_final(name, modified):
    return reviews.send_for_final(reviews.locked_review(name, modified)).as_dict()


@frappe.whitelist(methods=["POST"])
def complete(name, modified):
    return reviews.complete(reviews.locked_review(name, modified)).as_dict()


@frappe.whitelist(methods=["POST"])
def return_to_employee(name, modified, reason):
    return reviews.return_to_employee(
        reviews.locked_review(name, modified), reason
    ).as_dict()


@frappe.whitelist(methods=["POST"])
def set_applicability(name, modified, row_name, excluded, reason):
    if str(excluded) not in {"0", "1"}:
        frappe.throw("Excluded must be 0 or 1.")
    return reviews.applicability(
        reviews.locked_review(name, modified), row_name, int(excluded), reason
    ).as_dict()


@frappe.whitelist(methods=["POST"])
def request_applicability(name, modified, row_name, reason):
    doc = reviews.locked_review(name, modified)
    reviews.draft(doc)
    require_employee(doc)
    row = next((r for r in doc.items if r.name == row_name), None)
    if not row or not (reason or "").strip():
        frappe.throw("Select a row and explain the requested change.")
    audit(
        doc,
        "Applicability requested",
        reason,
        {"structure_item_id": row.structure_item_id},
    )
    doc.add_comment(
        "Comment",
        frappe.utils.escape_html(
            f"Applicability requested for row {row.idx}: {reason}"
        ),
    )
    from kpi_management.notifications import queue_event

    queue_event(doc, "Applicability request", reviewers=True)
    return {"requested": True}


@frappe.whitelist(methods=["POST"])
def cancel(name, modified, reason):
    return reviews.cancel(reviews.locked_review(name, modified), reason).as_dict()


@frappe.whitelist(methods=["POST"])
def amend(name, modified, reason, corrected_assignment=None):
    old = reviews.locked_review(name, modified)
    require_manager(old)
    # Source corrections lock the same Employee first; never transfer identity.
    return reviews.create_review(
        corrected_assignment or old.kpi_structure_assignment,
        old.period_start,
        old.period_end,
        amended_from=old.name,
        reason=reason,
    ).as_dict()


@frappe.whitelist(methods=["POST"])
def delete_draft(name, modified, reason):
    return reviews.delete_draft(reviews.locked_review(name, modified), reason)


@frappe.whitelist(methods=["POST"])
def recover_period(assignment, period_start, period_end, correction_reason=None):
    source = frappe.get_doc("KPI Structure Assignment", assignment)
    require_manager(source)
    return reviews.create_review(
        assignment, period_start, period_end, correction_reason=correction_reason
    ).as_dict()

