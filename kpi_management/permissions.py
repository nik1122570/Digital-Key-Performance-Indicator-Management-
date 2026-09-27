"""One explicit scope policy for forms, list queries, reports and actions."""

import frappe

READ = {"read", "select", "print", "export", "report"}
STAFF_ROLES = {"KPI Final Reviewer", "KPI Manager"}


def user_id(user=None):
    return user or frappe.session.user


def enabled(user=None):
    user = user_id(user)
    return user != "Guest" and bool(frappe.db.get_value("User", user, "enabled"))


def roles(user=None):
    return set(frappe.get_roles(user_id(user)))


def technical(user=None):
    return user_id(user) == "Administrator" or "System Manager" in roles(user)


def scope(user=None):
    # Only all-DocType permissions are the KPI organizational scope. This avoids
    # accidentally granting access from a permission intended for another app.
    result = {"Company": set(), "Department": set(), "Employee": set()}
    for row in frappe.get_all(
        "User Permission",
        filters={"user": user_id(user)},
        fields=["allow", "for_value", "apply_to_all_doctypes", "applicable_for"],
    ):
        if row.allow in result and (
            row.apply_to_all_doctypes or not row.applicable_for
        ):
            result[row.allow].add(row.for_value)
    return result


def scoped(doc, user=None):
    s = scope(user)
    return bool(
        s["Company"]
        and doc.get("company") in s["Company"]
        and (not s["Department"] or doc.get("department") in s["Department"])
        and (not s["Employee"] or doc.get("employee") in s["Employee"])
    )


def is_employee(doc, user=None):
    user = user_id(user)
    return (
        enabled(user)
        and doc.get("employee_user") == user
        and frappe.db.get_value("Employee", doc.employee, "user_id") == user
    )


def is_reviewer(doc, user=None):
    user = user_id(user)
    return (
        enabled(user)
        and "KPI Final Reviewer" in roles(user)
        and doc.get("employee_user") != user
        and frappe.db.get_value("Employee", doc.employee, "user_id") != user
        and scoped(doc, user)
    )


def is_manager(doc=None, user=None):
    return (
        enabled(user)
        and "KPI Manager" in roles(user)
        and (scoped(doc, user) if doc is not None else bool(scope(user)["Company"]))
    )


def require_employee(doc):
    mapping = frappe.db.get_value("Employee", doc.employee, "user_id", for_update=True)
    active = frappe.db.get_value("User", user_id(), "enabled", for_update=True)
    if not is_employee(doc) or mapping != user_id() or not active:
        frappe.throw(
            "Only the assigned employee's current, enabled user can self-rate. Check the assignment user snapshot if account mapping changed.",
            frappe.PermissionError,
        )


def require_reviewer(doc):
    current_employee_user = frappe.db.get_value(
        "Employee", doc.employee, "user_id", for_update=True
    )
    if not is_reviewer(doc) or current_employee_user == user_id():
        frappe.throw(
            "A non-self KPI Final Reviewer with explicit Company scope is required.",
            frappe.PermissionError,
        )


def require_manager(doc=None):
    if not is_manager(doc):
        frappe.throw(
            "KPI Manager role and explicit organizational scope are required.",
            frappe.PermissionError,
        )


def can_read(doc, user=None):
    if not enabled(user):
        return False
    return (
        technical(user)
        or doc.get("employee_user") == user_id(user)
        or bool(roles(user) & STAFF_ROLES)
        and scoped(doc, user)
    )


def review_permission(doc, ptype=None, user=None, **kwargs):
    ptype = ptype or "read"
    if ptype in READ:
        return can_read(doc, user)
    if ptype == "share":
        return False
    if ptype in {"cancel", "amend", "delete"}:
        return is_manager(doc, user)
    if ptype == "submit":
        return is_reviewer(doc, user)
    if ptype == "write":
        return is_employee(doc, user) or is_reviewer(doc, user) or is_manager(doc, user)
    return False  # Creation is exclusively through the controlled service.


def assignment_permission(doc, ptype=None, user=None, **kwargs):
    if (ptype or "read") in READ:
        return can_read(doc, user)
    if ptype == "share":
        return False
    if doc.is_new() and not doc.get("company"):
        return is_manager(user=user)
    return is_manager(doc, user)


def structure_permission(doc, ptype=None, user=None, **kwargs):
    if not enabled(user):
        return False
    if (ptype or "read") in READ and technical(user):
        return True
    if not roles(user) & STAFF_ROLES:
        return False
    companies = scope(user)["Company"]
    allowed = bool(companies) and (not doc.get("company") or doc.company in companies)
    return allowed and ((ptype or "read") in READ or "KPI Manager" in roles(user))


def scope_sql(table, user=None):
    s = scope(user)
    if not s["Company"]:
        return "1=0"
    terms = []
    for field, dtype in (
        ("company", "Company"),
        ("department", "Department"),
        ("employee", "Employee"),
    ):
        if s[dtype]:
            values = ",".join(frappe.db.escape(v) for v in sorted(s[dtype]))
            terms.append(f"{table}.`{field}` IN ({values})")
    return " AND ".join(terms)


def access_sql(table, user=None, own_only=False):
    if not enabled(user):
        return "1=0"
    if not own_only and technical(user):
        return "1=1"
    own = f"{table}.`employee_user` = {frappe.db.escape(user_id(user))}"
    if own_only or not roles(user) & STAFF_ROLES:
        return own
    return f"({own} OR ({scope_sql(table, user)}))"


def review_query(user=None):
    return access_sql("`tabKPI Review`", user)


def assignment_query(user=None):
    return access_sql("`tabKPI Structure Assignment`", user)


def audit_query(user=None):
    return access_sql("`tabKPI Audit Event`", user)


def audit_permission(doc, ptype=None, user=None, **kwargs):
    return (ptype or "read") in READ and can_read(doc, user)


def structure_query(user=None):
    if enabled(user) and technical(user):
        return "1=1"
    companies = scope(user)["Company"]
    if not enabled(user) or not roles(user) & STAFF_ROLES or not companies:
        return "1=0"
    values = ",".join(frappe.db.escape(v) for v in sorted(companies))
    return f"(COALESCE(`tabKPI Structure`.company, '') = '' OR `tabKPI Structure`.company IN ({values}))"

