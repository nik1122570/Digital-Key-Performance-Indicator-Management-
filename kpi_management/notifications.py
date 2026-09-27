"""Transactional outbox: review writes never depend on mail delivery."""

import hashlib
import frappe
from frappe.utils import get_url_to_form, today
from kpi_management.permissions import can_read, enabled, is_manager, is_reviewer


def staff(doc, reviewer=False):
    role = "KPI Final Reviewer" if reviewer else "KPI Manager"
    users = frappe.get_all(
        "Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"
    )
    predicate = is_reviewer if reviewer else is_manager
    return [user for user in set(users) if predicate(doc, user)]


def queue_event(
    doc, event, recipients=None, reviewers=False, managers=False, day_key=None
):
    users = set(recipients or [])
    if reviewers:
        users.update(staff(doc, reviewer=True))
    if managers:
        users.update(staff(doc))
    if reviewers and not users:
        users.update(staff(doc))
    for user in users:
        if not user:
            continue
        stamp = day_key or str(doc.modified or doc.creation or today())
        key = hashlib.sha256(
            f"{doc.doctype}|{doc.name}|{doc.get('workflow_state')}|{event}|{user}|{stamp}".encode()
        ).hexdigest()
        if frappe.db.exists("KPI Notification Outbox", {"dedup_key": key}):
            continue
        # The caller holds the Review/Assignment lock, so equal event keys serialize.
        frappe.get_doc(
            {
                "doctype": "KPI Notification Outbox",
                "dedup_key": key,
                "recipient": user,
                "reference_doctype": doc.doctype,
                "reference_name": doc.name,
                "event_type": event,
            }
        ).insert(ignore_permissions=True)
    if users:
        frappe.enqueue(
            "kpi_management.notifications.dispatch", queue="short", enqueue_after_commit=True
        )


def dispatch(limit=200):
    settings = frappe.get_single("KPI Settings")
    names = frappe.get_all(
        "KPI Notification Outbox",
        filters={"status": ["in", ["Pending", "Failed"]], "attempts": ["<", 10]},
        order_by="creation asc",
        limit_page_length=limit,
        pluck="name",
    )
    for name in names:
        try:
            frappe.db.sql(
                "SELECT name FROM `tabKPI Notification Outbox` WHERE name=%s FOR UPDATE",
                name,
            )
            out = frappe.get_doc("KPI Notification Outbox", name, for_update=True)
            if out.status not in {"Pending", "Failed"}:
                frappe.db.commit()
                continue
            out.attempts += 1
            doc = frappe.get_doc(out.reference_doctype, out.reference_name)
            if not enabled(out.recipient) or not can_read(doc, out.recipient):
                out.status = "Suppressed"
            else:
                # No score, employee name or review text in notification subject/body.
                subject = "KPI: " + out.event_type
                if not out.notification_created:
                    frappe.get_doc(
                        {
                            "doctype": "Notification Log",
                            "type": "Alert",
                            "subject": subject,
                            "for_user": out.recipient,
                            "document_type": doc.doctype,
                            "document_name": doc.name,
                            "from_user": "Administrator",
                        }
                    ).insert(ignore_permissions=True)
                    out.notification_created = 1
                if settings.email_notifications and not out.email_queued:
                    frappe.sendmail(
                        recipients=[out.recipient],
                        subject=subject,
                        message="A KPI action is available. Open the authenticated record: "
                        + get_url_to_form(doc.doctype, doc.name),
                        delayed=True,
                        reference_doctype=doc.doctype,
                        reference_name=doc.name,
                    )
                    out.email_queued = 1
                out.status = "Sent"
                out.last_error = ""
            out.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            # Log diagnostic detail privately; do not expose it in user notifications.
            frappe.log_error(frappe.get_traceback(), "KPI notification delivery")
            frappe.db.sql(
                """UPDATE `tabKPI Notification Outbox`
                SET status='Failed', attempts=attempts+1, last_error=%s WHERE name=%s""",
                (
                    "Delivery failed; see Error Log. Automatic retries stop after 10 attempts.",
                    name,
                ),
            )
            frappe.db.commit()

