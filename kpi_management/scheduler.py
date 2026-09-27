import frappe
from frappe.utils import date_diff, today
from kpi_management import domain
from kpi_management.common import audit
from kpi_management.notifications import dispatch, queue_event
from kpi_management.reviews import create_review


def generate():
    """Scheduled/bench-only; commits per period. Do not call inside a request transaction."""
    settings = frappe.get_single("KPI Settings")
    counts = {"created": 0, "skipped": 0, "blocked": 0, "failed": 0}
    if not settings.enable_review_generation or not settings.generation_from_date:
        return dict(counts, disabled=True)
    names = frappe.get_all(
        "KPI Structure Assignment",
        filters={"docstatus": 1},
        order_by="employee asc, name asc",
        pluck="name",
    )
    for name in names:
        assignment = frappe.get_doc("KPI Structure Assignment", name)
        for start, end, key in domain.periods(
            assignment.start_date,
            assignment.end_date,
            assignment.review_frequency,
            closed_before=today(),
            not_before=settings.generation_from_date,
        ):
            try:
                # create_review repeats these checks while holding locks.
                existing = frappe.get_all(
                    "KPI Review",
                    filters={
                        "kpi_structure_assignment": name,
                        "period_start": start,
                        "period_end": end,
                    },
                    fields=["docstatus"],
                )
                if existing:
                    state = (
                        "skipped"
                        if any(r.docstatus != 2 for r in existing)
                        else "blocked"
                    )
                    counts[state] += 1
                    if state == "blocked":
                        queue_event(
                            assignment,
                            "Manual review amendment required",
                            managers=True,
                            day_key=today() + key,
                        )
                    frappe.db.commit()
                    continue
                create_review(name, start, end)
                frappe.db.commit()  # outbox is committed with the new Draft
                counts["created"] += 1
            except Exception:
                frappe.db.rollback()
                # A competing scheduler may have won after the first lookup.
                if frappe.db.exists(
                    "KPI Review",
                    {
                        "kpi_structure_assignment": name,
                        "period_start": start,
                        "period_end": end,
                        "docstatus": ["!=", 2],
                    },
                ):
                    counts["skipped"] += 1
                else:
                    counts["failed"] += 1
                    frappe.log_error(
                        frappe.get_traceback(), f"KPI generation: {name} / {key}"
                    )
                    audit(
                        assignment,
                        "Generation exception",
                        "See the private Error Log for diagnostics.",
                        {"period_key": key},
                    )
                    queue_event(
                        assignment,
                        "Review generation requires attention",
                        managers=True,
                        day_key=today() + key,
                    )
                frappe.db.commit()
    frappe.logger("kpi_management", allow_site=True).info(
        {"event": "generation", "date": today(), **counts}
    )
    return counts


def reminders():
    settings = frappe.get_single("KPI Settings")
    if not settings.reminders_enabled:
        return
    for name in frappe.get_all("KPI Review", filters={"docstatus": 0}, pluck="name"):
        try:
            doc = frappe.get_doc("KPI Review", name)
            final = doc.workflow_state == "Pending Final Rating"
            due = doc.final_due_date if final else doc.self_due_date
            if due and (
                date_diff(due, today()) == settings.reminder_days_before_due
                or date_diff(due, today()) < 0
            ):
                event = (
                    "Review overdue"
                    if date_diff(due, today()) < 0
                    else "Review due soon"
                )
                queue_event(
                    doc,
                    event,
                    recipients=[] if final else [doc.employee_user],
                    reviewers=final,
                    day_key=today(),
                )
                if date_diff(due, today()) < 0:
                    queue_event(
                        doc,
                        "Overdue review requires attention",
                        managers=True,
                        day_key=today(),
                    )
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(frappe.get_traceback(), "KPI reminder")
            frappe.db.commit()


def daily():
    generate()
    reminders()
    dispatch()

