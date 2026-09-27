"""Idempotent install/migration hooks. Never enable generation automatically."""

import frappe
from kpi_management import __version__


def before_install():
    check_dependencies()
    names = (
        "KPI Component",
        "KPI Perspective",
        "KPI Structure",
        "KPI Structure Item",
        "KPI Structure Assignment",
        "KPI Review",
        "KPI Review Item",
        "KPI Settings",
        "KPI Audit Event",
        "KPI Notification Outbox",
    )
    existing = [name for name in names if frappe.db.exists("DocType", name)]
    if existing:
        frappe.throw(
            "Existing KPI schema detected. Review and migrate it before installing: "
            + ", ".join(existing)
        )


def check_dependencies():
    import importlib

    for app in ("frappe", "erpnext", "hrms"):
        try:
            module = importlib.import_module(app)
        except ImportError:
            frappe.throw(f"Install {app} v15 before installing SF KPI.")
        major = str(getattr(module, "__version__", "")).split(".")[0]
        if major != "15":
            frappe.throw(
                f"SF KPI {__version__} targets v15. Installed {app} version: {getattr(module, '__version__', 'unknown')}."
            )
    if frappe.conf.db_type not in (None, "mariadb"):
        frappe.throw(
            "This release requires MariaDB; PostgreSQL has not been qualified."
        )
    overrides = frappe.get_hooks("override_doctype_class").get("File", [])
    if any(path != "kpi_management.security.KPIProtectedFile" for path in overrides):
        frappe.throw(
            "Another app overrides File. Merge its behavior with KPIProtectedFile and qualify private downloads before installing SF KPI."
        )
    ensure_roles()


def ensure_roles():
    for name in ("Employee", "KPI Final Reviewer", "KPI Manager"):
        if not frappe.db.exists("Role", name):
            frappe.get_doc(
                {"doctype": "Role", "role_name": name, "desk_access": 1}
            ).insert(ignore_permissions=True)


def after_install():
    after_migrate()
    defaults = {
        "enable_review_generation": 0,
        "default_self_due_days": 7,
        "default_final_due_days": 7,
        "reminders_enabled": 1,
        "reminder_days_before_due": 2,
        "email_notifications": 0,
    }
    for field, value in defaults.items():
        # Installation never overwrites prior settings if restoring/reinstalling.
        if frappe.db.get_single_value("KPI Settings", field) is None:
            frappe.db.set_single_value("KPI Settings", field, value)


def after_migrate():
    check_dependencies()
    for name, style in [
        ("Pending Self Rating", "Warning"),
        ("Pending Final Rating", "Info"),
        ("Completed", "Success"),
        ("Cancelled", "Danger"),
    ]:
        if not frappe.db.exists("Workflow State", name):
            frappe.get_doc(
                {
                    "doctype": "Workflow State",
                    "workflow_state_name": name,
                    "style": style,
                }
            ).insert(ignore_permissions=True)
    frappe.db.add_unique(
        "KPI Review",
        ["kpi_structure_assignment", "period_start", "period_end", "review_revision"],
        "kpi_period_revision_unique",
    )
    frappe.db.add_index(
        "KPI Review", ["employee", "period_start", "period_end"], "kpi_employee_period"
    )
    frappe.db.add_index(
        "KPI Review", ["docstatus", "workflow_state", "company"], "kpi_review_workbench"
    )
    frappe.db.add_index(
        "KPI Structure Assignment",
        ["employee", "docstatus", "start_date", "end_date"],
        "kpi_assignment_overlap",
    )
    frappe.db.add_index(
        "KPI Structure Assignment",
        ["kpi_structure", "docstatus"],
        "kpi_assignment_structure",
    )
    frappe.db.add_index("KPI Review", ["amended_from"], "kpi_review_amendment")
    frappe.db.add_index(
        "KPI Review", ["company", "department", "employee"], "kpi_organization"
    )
    frappe.db.add_index(
        "KPI Notification Outbox", ["status", "attempts"], "kpi_outbox_pending"
    )
    frappe.db.add_index(
        "KPI Audit Event",
        ["reference_doctype", "reference_name"],
        "kpi_audit_reference",
    )
    frappe.db.add_index(
        "KPI Audit Event",
        ["employee", "period_start", "period_end"],
        "kpi_deleted_interval",
    )
    frappe.clear_cache()


def preflight():
    """Run with bench execute after migration; returns facts, never changes data."""
    import importlib
    from frappe.utils.scheduler import is_scheduler_inactive

    result = {
        "app": __version__,
        "versions": {
            a: importlib.import_module(a).__version__
            for a in ("frappe", "erpnext", "hrms")
        },
        "timezone": frappe.db.get_single_value("System Settings", "time_zone"),
        "scheduler_inactive": is_scheduler_inactive(),
        "generation_enabled": frappe.db.get_single_value(
            "KPI Settings", "enable_review_generation"
        ),
        "generation_from_date": frappe.db.get_single_value(
            "KPI Settings", "generation_from_date"
        ),
        "active_review_workflows": frappe.get_all(
            "Workflow",
            filters={"document_type": "KPI Review", "is_active": 1},
            pluck="name",
        ),
        "file_overrides": frappe.get_hooks("override_doctype_class").get("File", []),
    }
    result["doctypes"] = {
        name: frappe.db.exists("DocType", name) is not None
        for name in (
            "KPI Component",
            "KPI Perspective",
            "KPI Structure",
            "KPI Structure Assignment",
            "KPI Review",
            "KPI Settings",
        )
    }
    result["warnings"] = []
    if result["active_review_workflows"]:
        result["warnings"].append(
            "Disable additional KPI Review Workflows: this app owns stage transitions."
        )
    if result["timezone"] != "Africa/Dar_es_Salaam":
        result["warnings"].append(
            "Confirm site timezone; calendar generation uses the configured site date."
        )
    return result

