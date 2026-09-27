"""Review domain service. Every write locks Employee -> Assignment -> Review."""

import frappe
from frappe.utils import add_days, get_datetime, now_datetime, today
from kpi_management import domain
from kpi_management.common import IDENTITY, SNAPSHOT, audit, checked, lock, lock_assignment
from kpi_management.context import action
from kpi_management.permissions import (
    can_read,
    require_employee,
    require_manager,
    require_reviewer,
)

SELF = "Pending Self Rating"
FINAL = "Pending Final Rating"
SELF_FIELDS = (
    "actual_number",
    "actual_choice",
    "actual_date",
    "actual_text",
    "employee_comment",
    "self_rating",
)
FINAL_FIELDS = ("final_rating", "reviewer_comment")


def locked_review(name, modified=None):
    ref = frappe.get_doc("KPI Review", name)
    if not can_read(ref):
        frappe.throw("Review access denied.", frappe.PermissionError)
    lock_assignment(ref.kpi_structure_assignment)
    lock("KPI Review", name)
    doc = frappe.get_doc("KPI Review", name, for_update=True)
    if modified is not None and get_datetime(modified) != get_datetime(doc.modified):
        frappe.throw(
            "The Review changed. Reload it before continuing.",
            frappe.TimestampMismatchError,
        )
    return doc


def draft(doc, stage=None):
    if doc.docstatus != 0:
        frappe.throw("Only a Draft Review can be changed.")
    if stage and doc.workflow_state != stage:
        frappe.throw(f"This action requires {stage}.")


def sources(doc):
    assignment = frappe.get_doc(
        "KPI Structure Assignment", doc.kpi_structure_assignment, for_update=True
    )
    structure = frappe.get_doc(
        "KPI Structure", assignment.kpi_structure, for_update=True
    )
    key = checked(
        domain.eligible,
        assignment.as_dict(),
        structure.as_dict(),
        doc.period_start,
        doc.period_end,
        today(),
    )
    if (
        doc.period_key != key
        or doc.review_frequency != assignment.review_frequency
        or doc.kpi_structure != structure.name
        or doc.employee != assignment.employee
    ):
        frappe.throw("Review source or period mismatch.")
    for field in IDENTITY:
        if str(doc.get(field) or "") != str(assignment.get(field) or ""):
            frappe.throw(f"The immutable Assignment snapshot differs: {field}.")
    source_rows = {r.name: r for r in structure.components}
    if len(doc.items) != len(source_rows) or len(
        {r.structure_item_id for r in doc.items}
    ) != len(doc.items):
        frappe.throw("Review items must exactly match the submitted Structure.")
    for row in doc.items:
        source = source_rows.get(row.structure_item_id)
        if not source or row.idx != source.idx:
            frappe.throw("Review row identities/order do not match the Structure.")
        for key in SNAPSHOT:
            a, b = row.get(key), source.get(key)
            if key == "target_number":
                equal = domain.decimal(a or 0) == domain.decimal(b or 0)
            else:
                equal = str(a or "") == str(b or "")
            if not equal:
                frappe.throw(
                    f"Immutable Structure snapshot differs on row {row.idx}: {key}."
                )
        if domain.decimal(row.original_weight) != domain.decimal(source.weight):
            frappe.throw("Original weights cannot be changed.")
    return assignment, structure


def recalculate(doc):
    rows, totals = checked(domain.calculate, [r.as_dict() for r in doc.items])
    for row, values in zip(doc.items, rows):
        for key, value in values.items():
            row.set(key, float(value))
    for key, value in totals.items():
        doc.set(key, float(value) if value is not None else None)
    doc.rating_category = (
        domain.category(doc.final_total)
        if doc.docstatus == 1 and doc.final_complete
        else ""
    )


def validate_self(doc):
    active = [r for r in doc.items if not r.not_applicable]
    if not active:
        frappe.throw(
            "No applicable components: revise applicability before sending this Review."
        )
    for row in active:
        if (
            not row.actual_entered
            or not row.self_rating_entered
            or not (row.employee_comment or "").strip()
        ):
            frappe.throw(
                f"Row {row.idx}: enter the actual result, self rating and employee comment."
            )
        checked(domain.typed_value, row.as_dict(), "actual")
        checked(domain.valid_rating, row.self_rating, row.original_weight)
    if not (doc.employee_summary or "").strip():
        frappe.throw("Employee Summary is required.")


def validate_final(doc):
    validate_self(doc)
    if (
        not doc.self_sent_by
        or doc.self_sent_by != doc.employee_user
        or doc.self_accepted_revision != doc.applicability_revision
    ):
        frappe.throw(
            "The employee must acknowledge the current applicability and self assessment."
        )
    for row in doc.items:
        if row.not_applicable:
            continue
        if not row.final_rating_entered:
            frappe.throw(
                f"Row {row.idx}: a final rating is required; zero must be entered explicitly."
            )
        checked(domain.valid_rating, row.final_rating, row.original_weight)
        if (
            domain.decimal(row.final_rating) != domain.decimal(row.self_rating)
            and not (row.reviewer_comment or "").strip()
        ):
            frappe.throw(
                f"Row {row.idx}: explain the variance between self and final ratings."
            )
    recalculate(doc)
    if not (doc.final_summary or "").strip():
        frappe.throw("Final Summary is required.")
    if doc.final_total < 60 and not (doc.improvement_actions or "").strip():
        frappe.throw("Improvement Actions are required when Final Total is below 60.")


def clear_final(doc):
    for row in doc.items:
        row.final_rating = 0
        row.final_rating_entered = 0
        row.reviewer_comment = ""
    for key in (
        "final_summary",
        "strengths",
        "improvement_actions",
        "final_reviewed_by",
        "final_reviewed_on",
        "final_due_date",
        "self_sent_by",
        "self_sent_on",
    ):
        doc.set(key, None)
    doc.self_accepted_revision = -1
    doc.workflow_state = SELF


def check_slot(assignment, start, end, amended_from=None, correction_reason=None):
    deleted = frappe.db.sql(
        """SELECT name FROM `tabKPI Audit Event`
        WHERE event_type='Draft deleted for correction' AND employee=%s
        AND period_start<=%s AND period_end>=%s LIMIT 1 FOR UPDATE""",
        (assignment.employee, end, start),
    )
    if deleted and not (amended_from or correction_reason):
        frappe.throw(
            "A Draft was deleted for correction in this interval. Use Recover Closed Period with a correction reason after fixing the source."
        )
    records = frappe.db.sql(
        """SELECT name, docstatus, review_revision FROM `tabKPI Review`
        WHERE kpi_structure_assignment=%s AND period_start=%s AND period_end=%s FOR UPDATE""",
        (assignment.name, start, end),
        as_dict=True,
    )
    if any(r.docstatus != 2 for r in records):
        frappe.throw("A non-cancelled Review already occupies this period.")
    if records and not amended_from:
        frappe.throw(
            "Manual Amendment Required: cancelled Review history exists for this period."
        )
    others = frappe.db.sql(
        """SELECT name, docstatus FROM `tabKPI Review`
        WHERE employee=%s AND period_start<=%s AND period_end>=%s
          AND kpi_structure_assignment<>%s FOR UPDATE""",
        (assignment.employee, end, start, assignment.name),
        as_dict=True,
    )
    if any(r.docstatus != 2 for r in others):
        frappe.throw(
            "Another Assignment already has a live Review for this employee and interval."
        )
    if others and not amended_from:
        frappe.throw(
            "Historical review exists on another Assignment; use the controlled source-correction amendment."
        )
    return max([r.review_revision for r in records], default=-1) + 1


def create_review(
    assignment_name, start, end, amended_from=None, reason=None, correction_reason=None
):
    assignment = lock_assignment(assignment_name)
    if correction_reason:
        require_manager(assignment)
        if not correction_reason.strip():
            frappe.throw("A nonblank correction reason is required.")
    structure = frappe.get_doc(
        "KPI Structure", assignment.kpi_structure, for_update=True
    )
    key = checked(
        domain.eligible, assignment.as_dict(), structure.as_dict(), start, end, today()
    )
    previous = None
    if amended_from:
        previous = frappe.get_doc("KPI Review", amended_from, for_update=True)
        require_manager(previous)
        require_manager(assignment)
        if (
            previous.docstatus != 2
            or previous.employee != assignment.employee
            or previous.review_frequency != assignment.review_frequency
            or domain.day(previous.period_start) != domain.day(start)
            or domain.day(previous.period_end) != domain.day(end)
        ):
            frappe.throw(
                "Amend a cancelled Review for the same employee, frequency and exact period."
            )
        if frappe.db.sql(
            "SELECT name FROM `tabKPI Review` WHERE amended_from=%s LIMIT 1 FOR UPDATE",
            previous.name,
        ):
            frappe.throw(
                "This Review already has a successor; amend the latest cancelled revision."
            )
        if not (reason or "").strip():
            frappe.throw("An amendment reason is required.")
    revision = check_slot(assignment, start, end, amended_from, correction_reason)
    values = {
        "doctype": "KPI Review",
        "kpi_structure_assignment": assignment.name,
        "kpi_structure": structure.name,
        "employee": assignment.employee,
        "review_frequency": assignment.review_frequency,
        "period_start": start,
        "period_end": end,
        "period_key": key,
        "review_year": domain.day(start).year,
        "workflow_state": SELF,
        "opened_on": now_datetime(),
        "self_due_date": add_days(today(), assignment.self_due_days),
        "review_revision": max(
            revision, previous.review_revision + 1 if previous else 0
        ),
        "applicability_revision": 0,
        "self_accepted_revision": -1,
        "amended_from": amended_from,
    }
    values.update({field: assignment.get(field) for field in IDENTITY})
    doc = frappe.get_doc(values)
    for source in structure.components:
        item = {field: source.get(field) for field in SNAPSHOT}
        item.update(
            structure_item_id=source.name,
            original_weight=source.weight,
            not_applicable=0,
            actual_entered=0,
            self_rating_entered=0,
            final_rating_entered=0,
            self_rating=0,
            final_rating=0,
        )
        if previous and previous.kpi_structure_assignment == assignment.name:
            old = next(r for r in previous.items if r.structure_item_id == source.name)
            item.update(
                {
                    key: old.get(key)
                    for key in (
                        "not_applicable",
                        "na_reason",
                        "na_decided_by",
                        "na_decided_on",
                    )
                }
            )
        doc.append("items", item)
    with action("create"):
        doc.insert(ignore_permissions=True)
    audit(
        doc,
        "Amended" if previous else "Created",
        reason or correction_reason or "Closed calendar period",
        {"amended_from": amended_from},
    )
    from kpi_management.notifications import queue_event

    queue_event(doc, "Review ready", recipients=[doc.employee_user])
    if (
        not frappe.db.get_value("User", doc.employee_user, "enabled")
        or frappe.db.get_value("Employee", doc.employee, "user_id") != doc.employee_user
    ):
        audit(
            doc,
            "Identity exception",
            "Employee User is unavailable or differs from the Assignment snapshot.",
        )
        queue_event(doc, "Employee account requires attention", managers=True)
    return doc


def save_entries(doc, entries, summary, final=False):
    draft(doc, FINAL if final else SELF)
    (require_reviewer if final else require_employee)(doc)
    allowed = set(FINAL_FIELDS if final else SELF_FIELDS)
    rows = {r.name: r for r in doc.items}
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - allowed - {"name", "clear"}:
            frappe.throw("Unexpected rating-entry fields.")
        name = entry.get("name")
        if name not in rows or name in seen:
            frappe.throw("Invalid or duplicate review row.")
        seen.add(name)
        row = rows[name]
        if row.not_applicable:
            frappe.throw(
                "Excluded components cannot be rated. Request reinstatement first."
            )
        stage = "final" if final else "self"
        if entry.get("clear"):
            for field in allowed:
                row.set(
                    field,
                    0 if field.endswith("rating") or field.endswith("number") else None,
                )
            row.set(stage + "_rating_entered", 0)
            if not final:
                row.actual_entered = 0
            continue
        # A record action is a complete row entry, not a patch accepting default zero.
        if stage + "_rating" not in entry or entry[stage + "_rating"] in (None, ""):
            frappe.throw("Enter an explicit rating; zero is valid.")
        checked(domain.valid_rating, entry[stage + "_rating"], row.original_weight)
        if not final:
            suffix = (
                "number"
                if row.indicator in domain.NUMERIC
                else {"Yes No": "choice", "Date": "date", "Text": "text"}[row.indicator]
            )
            if "actual_" + suffix not in entry or entry["actual_" + suffix] in (
                None,
                "",
            ):
                frappe.throw("Enter an explicit actual result; zero is valid.")
            for field in SELF_FIELDS[:4]:
                row.set(
                    field, entry.get(field, 0 if field.endswith("number") else None)
                )
        for field in allowed:
            if field in entry:
                row.set(field, entry[field])
        row.set(stage + "_rating_entered", 1)
        if not final:
            checked(domain.typed_value, row.as_dict(), "actual")
            row.actual_entered = 1
    allowed_summary = (
        {"final_summary", "strengths", "improvement_actions"}
        if final
        else {"employee_summary", "development_needs"}
    )
    if not isinstance(summary, dict) or set(summary) - allowed_summary:
        frappe.throw("Unexpected summary fields.")
    for field, value in summary.items():
        doc.set(field, value)
    with action("entries", doc.name):
        doc.save(ignore_permissions=True)
    audit(
        doc,
        "Final entries saved" if final else "Self entries saved",
        payload={"rows": sorted(seen)},
    )
    return doc


def send_for_final(doc):
    draft(doc, SELF)
    require_employee(doc)
    sources(doc)
    validate_self(doc)
    doc.workflow_state = FINAL
    doc.self_sent_by = frappe.session.user
    doc.self_sent_on = now_datetime()
    doc.self_accepted_revision = doc.applicability_revision
    assignment = frappe.get_doc(
        "KPI Structure Assignment", doc.kpi_structure_assignment
    )
    doc.final_due_date = add_days(today(), assignment.final_due_days)
    with action("send", doc.name):
        doc.save(ignore_permissions=True)
    audit(doc, "Self assessment sent")
    from kpi_management.notifications import queue_event

    queue_event(doc, "Final review ready", reviewers=True)
    return doc


def complete(doc):
    draft(doc, FINAL)
    require_reviewer(doc)
    sources(doc)
    validate_final(doc)
    doc.workflow_state = "Completed"
    doc.final_reviewed_by = frappe.session.user
    doc.final_reviewed_on = now_datetime()
    with action("complete", doc.name):
        doc.flags.ignore_permissions = True
        doc.submit()
    audit(doc, "Completed")
    from kpi_management.notifications import queue_event

    queue_event(
        doc, "Review completed", recipients=[doc.employee_user, doc.final_reviewed_by]
    )
    if doc.final_total < 40:
        queue_event(doc, "Completed review requires attention", managers=True)
    return doc


def return_to_employee(doc, reason):
    draft(doc, FINAL)
    require_reviewer(doc)
    if not (reason or "").strip():
        frappe.throw("A return reason is required.")
    before = doc.as_dict()
    clear_final(doc)
    with action("return", doc.name):
        doc.save(ignore_permissions=True)
    audit(doc, "Returned to employee", reason, before)
    from kpi_management.notifications import queue_event

    queue_event(doc, "Self assessment needs revision", recipients=[doc.employee_user])
    return doc


def applicability(doc, row_name, excluded, reason):
    draft(doc)
    require_reviewer(doc)
    if excluded not in (0, 1) or not (reason or "").strip():
        frappe.throw("Specify applicability and a reason.")
    row = next((r for r in doc.items if r.name == row_name), None)
    if row is None:
        frappe.throw("Review row not found.")
    if int(row.not_applicable or 0) == excluded:
        frappe.throw("Applicability is unchanged.")
    before = doc.as_dict()
    row.not_applicable = excluded
    row.na_reason = reason.strip()
    row.na_decided_by = frappe.session.user
    row.na_decided_on = now_datetime()
    if not excluded:
        row.actual_entered = 0
        row.self_rating_entered = 0
    doc.applicability_revision += 1
    clear_final(doc)
    with action("applicability", doc.name):
        doc.save(ignore_permissions=True)
    audit(
        doc,
        "Component excluded" if excluded else "Component reinstated",
        reason,
        {"structure_item_id": row.structure_item_id, "before": before},
    )
    from kpi_management.notifications import queue_event

    queue_event(doc, "Review applicability changed", recipients=[doc.employee_user])
    if not doc.applicable_weight:
        queue_event(doc, "No applicable components", managers=True)
    return doc


def cancel(doc, reason):
    require_manager(doc)
    if doc.docstatus != 1 or not (reason or "").strip():
        frappe.throw("Only a submitted Review can be cancelled, with a reason.")
    with action("cancel", doc.name):
        doc.flags.ignore_permissions = True
        doc.cancel()
    audit(doc, "Cancelled", reason)
    return doc


def delete_draft(doc, reason):
    require_manager(doc)
    draft(doc)
    if not (reason or "").strip():
        frappe.throw("An administrative correction reason is required.")
    # Persist the complete draft in a protected immutable audit document before deletion.
    archive = audit(doc, "Draft deleted for correction", reason, doc.as_dict())
    # Keep private evidence with the immutable audit snapshot instead of allowing
    # Frappe's parent deletion to remove it. This transfer is server-only and atomic.
    for name in frappe.get_all(
        "File",
        filters={"attached_to_doctype": "KPI Review", "attached_to_name": doc.name},
        pluck="name",
    ):
        frappe.db.set_value(
            "File",
            name,
            {
                "attached_to_doctype": "KPI Audit Event",
                "attached_to_name": archive.name,
            },
        )
    with action("delete", doc.name):
        frappe.delete_doc("KPI Review", doc.name, ignore_permissions=True)
    return {"deleted": doc.name}

