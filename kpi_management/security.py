import frappe
from frappe.core.doctype.file.file import File
from kpi_management.permissions import access_sql, can_read


def linked_review(file):
    if (
        file.attached_to_doctype in {"KPI Review", "KPI Audit Event"}
        and file.attached_to_name
    ):
        return frappe.get_doc(file.attached_to_doctype, file.attached_to_name)
    return None


def file_permission(doc, ptype=None, user=None, **kwargs):
    review = linked_review(doc)
    if review:
        if ptype == "share":
            return False
        return can_read(review, user)
    return None


def validate_file(doc, method=None):
    old = doc.get_doc_before_save()
    if (
        old
        and old.attached_to_doctype in {"KPI Review", "KPI Audit Event"}
        and (
            doc.attached_to_doctype != old.attached_to_doctype
            or doc.attached_to_name != old.attached_to_name
        )
    ):
        frappe.throw("KPI attachments cannot be detached or moved to another record.")
    review = linked_review(doc)
    if review:
        if not can_read(review):
            frappe.throw("Review access denied.", frappe.PermissionError)
        if not doc.is_private or (
            doc.file_url and not doc.file_url.startswith("/private/files/")
        ):
            frappe.throw("KPI evidence must be a private uploaded file.")


def validate_comment(doc, method=None):
    if (
        doc.reference_doctype in {"KPI Review", "KPI Audit Event"}
        and doc.reference_name
    ):
        if not can_read(frappe.get_doc(doc.reference_doctype, doc.reference_name)):
            frappe.throw("Review access denied.", frappe.PermissionError)


class KPIProtectedFile(File):
    """v15's private download and zip paths use File-specific owner shortcuts.

    Keep every non-KPI File behavior; recheck Review scope for KPI content.
    Install checks reject another File override so neither app silently wins.
    """

    def before_insert(self):
        # Reject public evidence before Frappe writes bytes to the filesystem.
        validate_file(self)
        return super().before_insert()

    def before_validate(self):
        # Privacy/link checks must run before core File validation can move files.
        validate_file(self)
        parent = getattr(super(), "before_validate", None)
        if parent:
            return parent()

    def is_downloadable(self):
        review = linked_review(self)
        return can_read(review) if review else super().is_downloadable()

    def on_trash(self):
        review = linked_review(self)
        if review and (review.doctype == "KPI Audit Event" or review.docstatus != 0):
            frappe.throw(
                "Retain private evidence attached to a completed/cancelled Review or immutable audit snapshot."
            )
        return super().on_trash()

    def save_file(self, *args, **kwargs):
        review = linked_review(self)
        if (
            not self.is_new()
            and review
            and (review.doctype == "KPI Audit Event" or review.docstatus != 0)
        ):
            frappe.throw(
                "Retained KPI evidence cannot be overwritten. Attach a separate correction document instead."
            )
        return super().save_file(*args, **kwargs)

    def get_content(self):
        review = linked_review(self)
        if review and not can_read(review):
            frappe.throw("Review attachment access denied.", frappe.PermissionError)
        return super().get_content()


def file_query(user=None):
    return (
        "(COALESCE(`tabFile`.attached_to_doctype,'') NOT IN ('KPI Review','KPI Audit Event')"
        " OR (`tabFile`.attached_to_doctype='KPI Review' AND EXISTS (SELECT 1 FROM `tabKPI Review` r"
        f" WHERE r.name=`tabFile`.attached_to_name AND ({access_sql('r', user)})))"
        " OR (`tabFile`.attached_to_doctype='KPI Audit Event' AND EXISTS (SELECT 1 FROM `tabKPI Audit Event` a"
        f" WHERE a.name=`tabFile`.attached_to_name AND ({access_sql('a', user)}))))"
    )

