"""All report queries explicitly apply the same access policy as Review forms."""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import frappe
from frappe.utils import date_diff, today
from kpi_management import domain
from kpi_management.permissions import access_sql, scope_sql, roles, enabled

REPORTS = [
    "My KPI Performance",
    "KPI Reviewer Workbench",
    "KPI Review Completion Status",
    "KPI Overdue Reviews",
    "KPI Employee Annual Trend",
    "KPI Company Department Performance",
    "KPI Component Perspective Performance",
    "KPI Self vs Final Variance",
    "KPI Reviewer Distribution",
    "KPI Assignment Structure Validity",
    "KPI Review Applicability Audit",
]


def col(field, label=None, kind="Data", width=150, options=None):
    result = {
        "fieldname": field,
        "label": label or field.replace("_", " ").title(),
        "fieldtype": kind,
        "width": width,
    }
    if options:
        result["options"] = options
    return result


def filters_sql(filters, alias="r"):
    allowed = {
        "company",
        "department",
        "employee",
        "review_frequency",
        "review_year",
        "final_reviewed_by",
    }
    args, terms = {}, []
    for key in allowed:
        if filters.get(key):
            args[key] = filters[key]
            terms.append(f"{alias}.`{key}` = %({key})s")
    if filters.get("period_start"):
        args["period_start"] = filters["period_start"]
        terms.append(f"{alias}.period_start >= %(period_start)s")
    if filters.get("period_end"):
        args["period_end"] = filters["period_end"]
        terms.append(f"{alias}.period_end <= %(period_end)s")
    return (" AND " + " AND ".join(terms)) if terms else "", args


def mean(values):
    return (
        float(
            (sum((Decimal(str(v)) for v in values), Decimal(0)) / len(values)).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP
            )
        )
        if values
        else None
    )


def execute(report, filters=None):
    if report not in REPORTS or not enabled():
        frappe.throw("Report access denied.", frappe.PermissionError)
    filters = frappe._dict(filters or {})
    if report == "KPI Assignment Structure Validity":
        return validity(filters)
    if report == "KPI Review Applicability Audit":
        return applicability_audit(filters)
    scope = access_sql("r", own_only=report == "My KPI Performance")
    extra, args = filters_sql(filters)
    official = report in {
        "KPI Employee Annual Trend",
        "KPI Company Department Performance",
        "KPI Component Perspective Performance",
        "KPI Self vs Final Variance",
        "KPI Reviewer Distribution",
    }
    condition = (
        "r.docstatus=1 AND r.workflow_state='Completed'"
        if official
        else "r.docstatus<>2"
    )
    if report == "KPI Reviewer Workbench":
        if "KPI Final Reviewer" not in roles():
            frappe.throw("KPI Final Reviewer role is required.", frappe.PermissionError)
        scope = scope_sql("r")
        condition = "r.docstatus=0 AND r.workflow_state='Pending Final Rating' AND r.employee_user<>%(actor)s AND NOT EXISTS (SELECT 1 FROM `tabEmployee` e WHERE e.name=r.employee AND e.user_id=%(actor)s)"
        args["actor"] = frappe.session.user
    data = frappe.db.sql(
        f"SELECT r.* FROM `tabKPI Review` r WHERE ({scope}) AND {condition}{extra} ORDER BY r.period_start,r.employee,r.name",
        args,
        as_dict=True,
    )
    for r in data:
        due = (
            r.final_due_date
            if r.workflow_state == "Pending Final Rating"
            else r.self_due_date
        )
        r.due_date = due if r.docstatus == 0 else None
        r.days_overdue = (
            max(0, date_diff(today(), due)) if r.docstatus == 0 and due else 0
        )
        r.generation_delay_days = max(
            0, date_diff(r.opened_on, domain.day(r.period_end)) - 1
        )
        if not r.self_complete:
            r.self_total = None
        if not r.final_complete:
            r.final_total = None
        r.result_status = (
            "Official"
            if r.docstatus == 1
            else (
                "No applicable components"
                if not r.applicable_weight
                else "Draft — provisional"
                if r.final_complete
                else "Incomplete"
            )
        )
    base = [
        col("name", "Review", "Link", 190, "KPI Review"),
        col("employee", kind="Link", options="Employee"),
        col("employee_name"),
        col("company", kind="Link", options="Company"),
        col("department"),
        col("review_frequency"),
        col("period_key"),
        col("workflow_state"),
        col("self_total", kind="Float"),
        col("final_total", kind="Float"),
        col("rating_category"),
        col("result_status"),
        col("excluded_weight", kind="Float"),
        col("due_date", kind="Date"),
        col("days_overdue", kind="Int"),
        col("generation_delay_days", kind="Int"),
    ]
    base += [
        col("structure_version", kind="Int"),
        col("final_reviewed_by", kind="Link", options="User"),
    ]
    if report == "KPI Overdue Reviews":
        data = [r for r in data if r.days_overdue > 0]
    if report in {"KPI Company Department Performance", "KPI Reviewer Distribution"}:
        keys = (
            ("company", "department", "review_frequency", "period_key")
            if report == "KPI Company Department Performance"
            else ("final_reviewed_by", "review_frequency", "period_key")
        )
        groups = defaultdict(list)
        for r in data:
            groups[tuple(r.get(k) for k in keys)].append(r)
        out = []
        for key, rows in groups.items():
            d = dict(zip(keys, key))
            d.update(
                review_count=len(rows),
                employee_count=len({r.employee for r in rows}),
                structure_versions=", ".join(
                    sorted(
                        {f"{r.kpi_structure} (v{r.structure_version})" for r in rows}
                    )
                ),
                average_final=mean([r.final_total for r in rows]),
                average_excluded_weight=mean([r.excluded_weight for r in rows]),
            )
            for label, fname in [
                ("Outstanding", "outstanding"),
                ("Exceeds Expectations", "exceeds"),
                ("Meets Expectations", "meets"),
                ("Improvement Needed", "improvement"),
                ("Poor", "poor"),
            ]:
                d[fname] = sum(r.rating_category == label for r in rows)
            out.append(d)
        return [col(k) for k in keys] + [
            col("review_count", kind="Int"),
            col("employee_count", kind="Int"),
            col("structure_versions", width=250),
            col("average_final", kind="Float"),
            col("average_excluded_weight", kind="Float"),
        ] + [
            col(k, kind="Int")
            for k in ("outstanding", "exceeds", "meets", "improvement", "poor")
        ], out
    if report in {
        "KPI Component Perspective Performance",
        "KPI Self vs Final Variance",
    }:
        extra, args = filters_sql(filters)
        items = frappe.db.sql(
            f"""SELECT r.name AS review, r.employee, r.company, r.department,
            r.review_frequency, r.period_key, r.structure_version, r.final_reviewed_by,
            i.kpi_component, i.perspective_label, i.indicator,
            i.target_display, i.currency, i.duration_unit, i.original_weight, i.effective_weight,
            i.self_rating, i.final_rating, i.self_points, i.final_points, i.rating_variance,
            i.not_applicable, i.na_reason, i.reviewer_comment, i.actual_number,
            i.actual_choice, i.actual_date, i.actual_text, i.actual_entered
            FROM `tabKPI Review` r JOIN `tabKPI Review Item` i ON i.parent=r.name
            WHERE ({scope}) AND r.docstatus=1 AND r.workflow_state='Completed'{extra}
            ORDER BY r.period_start,r.employee,i.idx""",
            args,
            as_dict=True,
        )
        groups = defaultdict(list)
        for item in items:
            key = tuple(
                item.get(k)
                for k in (
                    "company",
                    "department",
                    "review_frequency",
                    "period_key",
                    "kpi_component",
                    "indicator",
                    "target_display",
                    "currency",
                    "duration_unit",
                )
            )
            groups[key].append(item)
            item.raw_variance = float(
                (
                    domain.decimal(item.final_rating) - domain.decimal(item.self_rating)
                ).quantize(domain.CENT, rounding=ROUND_HALF_UP)
            )
            item.actual_display = (
                "N/A" if item.not_applicable else domain.display_value(item, "actual")
            )
        for group in groups.values():
            rate = (
                Decimal(100)
                * sum(bool(item.not_applicable) for item in group)
                / len(group)
            )
            for item in group:
                item.comparable_review_count = len(group)
                item.exclusion_rate = float(
                    rate.quantize(domain.CENT, rounding=ROUND_HALF_UP)
                )
        columns = (
            [col("review", kind="Link", options="KPI Review")]
            + [
                col(k)
                for k in (
                    "employee",
                    "company",
                    "department",
                    "review_frequency",
                    "period_key",
                    "structure_version",
                    "final_reviewed_by",
                    "kpi_component",
                    "perspective_label",
                    "indicator",
                    "target_display",
                    "actual_display",
                    "currency",
                    "duration_unit",
                )
            ]
            + [
                col(k, kind="Float")
                for k in (
                    "original_weight",
                    "effective_weight",
                    "self_rating",
                    "final_rating",
                    "raw_variance",
                    "self_points",
                    "final_points",
                    "rating_variance",
                    "exclusion_rate",
                )
            ]
            + [
                col("comparable_review_count", kind="Int"),
                col("not_applicable", kind="Check"),
                col("na_reason"),
                col("reviewer_comment"),
            ]
        )
        # Component/target-level rows intentionally retain target context. Averaging
        # unlike targets or mixing frequencies would misrepresent performance.
        return columns, items
    if report == "KPI Employee Annual Trend":
        # One official record per employee/period; never sum annual ratings.
        return (
            base,
            data,
            "Scores are per review period. Filter one frequency when comparing trends.",
        )
    if report == "My KPI Performance":
        frequencies = sorted({r.review_frequency for r in data if r.docstatus == 1})
        summary = [
            {
                "label": "Open Reviews",
                "value": sum(r.docstatus == 0 for r in data),
                "datatype": "Int",
            }
        ]
        chart = None
        if len(frequencies) == 1:
            completed = [r for r in data if r.docstatus == 1][-12:]
            chart = {
                "data": {
                    "labels": [r.period_key for r in completed],
                    "datasets": [
                        {
                            "name": "Final score",
                            "values": [r.final_total for r in completed],
                        }
                    ],
                },
                "type": "line",
            }
        return (
            base,
            data,
            "Draft results are provisional; only submitted reviews are official.",
            chart,
            summary,
        )
    return base, data


def validity(filters):
    # No supplied filters may broaden the organizational predicate.
    predicate = access_sql("a")
    args, extra = {}, []
    for field in ("company", "department", "employee", "review_frequency"):
        if filters.get(field):
            extra.append(f"a.`{field}`=%({field})s")
            args[field] = filters[field]
    suffix = " AND " + " AND ".join(extra) if extra else ""
    assignments = frappe.db.sql(
        f"SELECT a.* FROM `tabKPI Structure Assignment` a WHERE ({predicate}) AND a.docstatus=1{suffix}",
        args,
        as_dict=True,
    )
    out = []
    for a in assignments:
        full = list(domain.periods(a.start_date, a.end_date, a.review_frequency))
        concerns = []
        if not full:
            concerns.append("No complete calendar period")
        else:
            if full[0][0] > domain.day(a.start_date):
                concerns.append("Opening partial period omitted")
            if full[-1][1] < domain.day(a.end_date):
                concerns.append("Closing partial period omitted")
        structure = frappe.db.get_value(
            "KPI Structure",
            a.kpi_structure,
            ["docstatus", "effective_from", "effective_to"],
            as_dict=True,
        )
        if not structure or structure.docstatus != 1:
            concerns.append("Structure not submitted")
        employee = frappe.db.get_value(
            "Employee",
            a.employee,
            ["user_id", "company", "designation", "status"],
            as_dict=True,
        )
        if employee.user_id != a.employee_user or not frappe.db.get_value(
            "User", a.employee_user, "enabled"
        ):
            concerns.append("Employee user unavailable or changed")
        if employee.company != a.company or employee.designation != a.designation:
            concerns.append("Current employee role differs from agreement snapshot")
        if employee.status != "Active":
            concerns.append("Employee is no longer active")
        if domain.day(a.end_date) < domain.day(today()):
            concerns.append("Expired agreement; historical reviews remain eligible")
        overlapping = frappe.db.sql(
            "SELECT name FROM `tabKPI Structure Assignment` WHERE employee=%s AND name<>%s AND docstatus=1 AND start_date<=%s AND end_date>=%s LIMIT 1",
            (a.employee, a.name, a.end_date, a.start_date),
        )
        if overlapping:
            concerns.append("Overlapping submitted assignment detected")
        exceptions = frappe.db.count(
            "KPI Audit Event",
            {"reference_name": a.name, "event_type": "Generation exception"},
        )
        if exceptions:
            concerns.append(f"{exceptions} logged generation exceptions; inspect audit")
        closed = [p for p in full if p[1] < domain.day(today())]
        missing = sum(
            not frappe.db.exists(
                "KPI Review",
                {
                    "kpi_structure_assignment": a.name,
                    "period_start": p[0],
                    "period_end": p[1],
                    "docstatus": ["!=", 2],
                },
            )
            for p in closed
        )
        out.append(
            dict(
                assignment=a.name,
                employee=a.employee,
                company=a.company,
                review_frequency=a.review_frequency,
                start_date=a.start_date,
                end_date=a.end_date,
                complete_periods=len(full),
                missing_closed_reviews=missing,
                issues="; ".join(concerns) or "No issue found",
            )
        )
    return [col("assignment", kind="Link", options="KPI Structure Assignment")] + [
        col(k) for k in ("employee", "company", "review_frequency")
    ] + [col(k, kind="Date") for k in ("start_date", "end_date")] + [
        col(k, kind="Int") for k in ("complete_periods", "missing_closed_reviews")
    ] + [col("issues", width=400)], out


def applicability_audit(filters):
    scope = access_sql("a")
    args, extra = {}, []
    for field in ("company", "department", "employee"):
        if filters.get(field):
            args[field] = filters[field]
            extra.append(f"a.`{field}`=%({field})s")
    suffix = " AND " + " AND ".join(extra) if extra else ""
    rows = frappe.db.sql(
        f"""SELECT a.name, a.reference_name, a.employee, a.company,
        a.event_type, a.actor, a.creation, a.reason, a.payload
        FROM `tabKPI Audit Event` a WHERE ({scope}) AND a.event_type IN
        ('Component excluded','Component reinstated','Applicability requested','Amended') {suffix}
        ORDER BY a.creation DESC""",
        args,
        as_dict=True,
    )
    # Audit payload stays in the protected audit form; report returns only row ID.
    for row in rows:
        payload = frappe.parse_json(row.pop("payload", None)) or {}
        row.structure_item_id = payload.get("structure_item_id")
        before = payload.get("before") or {}
        row.previous_excluded_weight = before.get("excluded_weight")
        row.previous_acknowledged_revision = before.get("self_accepted_revision")
        row.previous_applicability_revision = before.get("applicability_revision")
    return [
        col("name", kind="Link", options="KPI Audit Event"),
        col("reference_name", "Review", "Link", 190, "KPI Review"),
    ] + [
        col(k)
        for k in ("employee", "company", "event_type", "structure_item_id", "actor")
    ] + [
        col("creation", kind="Datetime"),
        col("previous_excluded_weight", kind="Float"),
        col("previous_acknowledged_revision", kind="Int"),
        col("previous_applicability_revision", kind="Int"),
        col("reason", width=300),
    ], rows

