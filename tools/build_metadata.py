"""Regenerate app-owned DocType JSON. Run from the repository root."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "kpi_management" / "kpi_management"
I = "Percentage\nNumber\nCurrency\nDuration\nYes No\nDate\nText"
FREQ = "Monthly\nQuarterly\nSemi-Annual"


def f(name, kind="Data", options=None, **kw):
    result = dict(
        fieldname=name,
        label=name.replace("_", " ")
        .title()
        .replace("Kpi", "KPI")
        .replace("Na ", "N/A "),
        fieldtype=kind,
    )
    if options is not None:
        result["options"] = options
    return {**result, **kw}


def role(name, write=0, submit=0, **kw):
    return dict(
        role=name,
        read=1,
        write=write,
        create=write,
        submit=submit,
        cancel=submit,
        amend=submit,
        report=1,
        print=1,
        export=1,
        **kw,
    )


def dt(name, fields, submit=False, child=False, single=False, **kw):
    slug = name.lower().replace(" ", "_")
    folder = ROOT / "doctype" / slug
    folder.mkdir(parents=True, exist_ok=True)
    doc = dict(
        doctype="DocType",
        name=name,
        module="KPI Management",
        custom=0,
        engine="InnoDB",
        track_changes=1,
        is_submittable=int(submit),
        istable=int(child),
        issingle=int(single),
        editable_grid=1,
        field_order=[r["fieldname"] for r in fields],
        fields=fields,
        permissions=[]
        if child
        else [
            role("KPI Manager", 1, int(submit)),
            role("System Manager", 1, int(submit)),
        ],
        sort_field="modified",
        sort_order="DESC",
        **kw,
    )
    (folder / (slug + ".json")).write_text(json.dumps(doc, indent=2) + "\n")
    (folder / "__init__.py").touch()
    controller = folder / (slug + ".py")
    if not controller.exists():
        controller.write_text(
            "from frappe.model.document import Document\n\n\nclass "
            + name.replace(" ", "")
            + "(Document):\n    pass\n"
        )


snap = [
    f("objective"),
    f("metric", "Small Text"),
    f("indicator", "Select", I),
    f("perspective", "Link", "KPI Perspective"),
    f("perspective_label"),
]
for x in snap:
    x["read_only"] = 1


def typed(prefix, readonly=False):
    items = [
        f(
            prefix + "_number",
            "Float",
            precision="6",
            depends_on="eval:['Percentage','Number','Currency','Duration'].includes(doc.indicator)",
        ),
        f(
            prefix + "_choice",
            "Select",
            "\nYes\nNo",
            depends_on="eval:doc.indicator==='Yes No'",
        ),
        f(prefix + "_date", "Date", depends_on="eval:doc.indicator==='Date'"),
        f(prefix + "_text", "Small Text", depends_on="eval:doc.indicator==='Text'"),
    ]
    if readonly:
        for x in items:
            x["read_only"] = 1
    return items


units = [
    f(
        "duration_unit",
        "Select",
        "\nHours\nDays\nWeeks\nMonths\nYears",
        depends_on="eval:doc.indicator==='Duration'",
    ),
    f("currency", "Link", "Currency", depends_on="eval:doc.indicator==='Currency'"),
]
end = [f("amended_from", "Link", read_only=1, no_copy=1)]

dt(
    "KPI Perspective",
    [
        f("perspective_name", reqd=1, unique=1, in_list_view=1),
        f("disabled", "Check", default="0"),
        f("display_order", "Int", default="0"),
    ],
    autoname="field:perspective_name",
    title_field="perspective_name",
    allow_rename=0,
)
dt(
    "KPI Component",
    [
        f("objective", reqd=1, unique=1, in_list_view=1),
        f("metric", "Small Text", reqd=1),
        f("indicator", "Select", I, reqd=1, in_list_view=1),
        f("perspective", "Link", "KPI Perspective", reqd=1),
        f("disabled", "Check", default="0"),
    ],
    autoname="field:objective",
    title_field="objective",
    allow_rename=0,
)
structure_snap = [
    dict(x, read_only=0) if x["fieldname"] == "perspective" else dict(x) for x in snap
]
dt(
    "KPI Structure Item",
    [f("kpi_component", "Link", "KPI Component", reqd=1, in_list_view=1)]
    + structure_snap
    + [f("weight", "Float", precision="2", in_list_view=1)]
    + typed("target")
    + units
    + [f("target_display", read_only=1, in_list_view=1)],
    child=True,
)
dt(
    "KPI Structure",
    [
        f("designation", "Link", "Designation", reqd=1, in_list_view=1),
        f("company", "Link", "Company"),
        f("version", "Int", read_only=1, in_list_view=1),
        f("effective_from", "Date", reqd=1),
        f("effective_to", "Date"),
        f("review_guidance", "Small Text"),
        f("components", "Table", "KPI Structure Item", reqd=1),
        f("total_weight", "Float", precision="2", read_only=1),
        f("amended_from", "Link", "KPI Structure", read_only=1, no_copy=1),
    ],
    submit=True,
)
identity = [
    f("employee_user", "Link", "User"),
    f("employee_name"),
    f("company", "Link", "Company"),
    f("department", "Link", "Department"),
    f("designation", "Link", "Designation"),
    f("reporting_line"),
    f("structure_version", "Int"),
]
for x in identity:
    x["read_only"] = 1
assignment = (
    [f("employee", "Link", "Employee", reqd=1, in_list_view=1)]
    + identity
    + [
        f("kpi_structure", "Link", "KPI Structure", reqd=1),
        f("start_date", "Date", reqd=1, in_list_view=1),
        f("end_date", "Date", reqd=1),
        f("review_frequency", "Select", FREQ, reqd=1, in_list_view=1),
        f("self_due_days", "Int", default="7", reqd=1),
        f("final_due_days", "Int", default="7", reqd=1),
        f("amended_from", "Link", "KPI Structure Assignment", read_only=1, no_copy=1),
    ]
)
dt(
    "KPI Structure Assignment",
    assignment,
    submit=True,
    autoname="format:KSA-{YYYY}-{#####}",
)
row = (
    [
        f("structure_item_id", read_only=1),
        f("kpi_component", "Link", "KPI Component", read_only=1, in_list_view=1),
    ]
    + snap
    + typed("target", True)
    + [dict(x, read_only=1) for x in units]
    + [
        f("target_display", read_only=1, in_list_view=1),
        f("original_weight", "Float", precision="2", read_only=1),
        f("effective_weight", "Float", precision="2", read_only=1, in_list_view=1),
    ]
    + typed("actual", True)
)
row += [
    f("actual_entered", "Check", hidden=1, read_only=1),
    f("employee_comment", "Small Text", read_only=1),
]
for stage in ("self", "final"):
    row += [
        f(stage + "_rating", "Float", precision="2", read_only=1),
        f(stage + "_rating_entered", "Check", hidden=1, read_only=1),
        f(stage + "_points", "Float", precision="2", read_only=1, in_list_view=1),
    ]
row += [
    f("reviewer_comment", "Small Text", read_only=1),
    f("rating_variance", "Float", precision="2", read_only=1),
    f("not_applicable", "Check", read_only=1, in_list_view=1),
    f("na_reason", "Small Text", read_only=1),
    f("na_decided_by", "Link", "User", read_only=1),
    f("na_decided_on", "Datetime", read_only=1),
]
dt("KPI Review Item", row, child=True)
review = (
    [
        f("kpi_structure_assignment", "Link", "KPI Structure Assignment"),
        f("kpi_structure", "Link", "KPI Structure"),
        f("employee", "Link", "Employee", in_list_view=1),
    ]
    + identity
    + [
        f("review_frequency", "Select", FREQ),
        f("period_key", in_list_view=1),
        f("period_start", "Date"),
        f("period_end", "Date"),
        f("review_year", "Int"),
        f("workflow_state", "Link", "Workflow State", in_list_view=1),
        f("opened_on", "Datetime"),
        f("self_due_date", "Date"),
        f("final_due_date", "Date"),
        f("items", "Table", "KPI Review Item"),
    ]
)
for name in [
    "applicable_weight",
    "excluded_weight",
    "effective_weight_total",
    "self_total",
    "final_total",
]:
    review.append(f(name, "Float", precision="2"))
review += [
    f("self_complete", "Check", hidden=1),
    f("final_complete", "Check", hidden=1),
    f("rating_category"),
    f("employee_summary", "Small Text"),
    f("development_needs", "Small Text"),
    f("final_summary", "Small Text"),
    f("strengths", "Small Text"),
    f("improvement_actions", "Small Text"),
    f("self_sent_by", "Link", "User"),
    f("self_sent_on", "Datetime"),
    f("self_accepted_revision", "Int", default="-1"),
    f("final_reviewed_by", "Link", "User"),
    f("final_reviewed_on", "Datetime"),
    f("applicability_revision", "Int", default="0"),
    f("review_revision", "Int", default="0"),
    f("amended_from", "Link", "KPI Review", no_copy=1),
]
for x in review:
    x["read_only"] = 1
# Inputs use dedicated server actions to distinguish a blank field from an explicit zero.
dt("KPI Review", review, submit=True, autoname="format:KPR-{YYYY}-{#####}")
p = ROOT / "doctype/kpi_review/kpi_review.json"
data = json.loads(p.read_text())
data["permissions"] = [
    role("Employee", write=1),
    role("KPI Final Reviewer", write=1, submit=1),
    role("KPI Manager", write=1, submit=1),
    role("System Manager", write=1, submit=1),
]
p.write_text(json.dumps(data, indent=2) + "\n")
dt(
    "KPI Settings",
    [
        f("enable_review_generation", "Check", default="0"),
        f("generation_from_date", "Date"),
        f("default_self_due_days", "Int", default="7", reqd=1),
        f("default_final_due_days", "Int", default="7", reqd=1),
        f("reminders_enabled", "Check", default="1"),
        f("reminder_days_before_due", "Int", default="2"),
        f(
            "email_notifications",
            "Check",
            default="0",
            description="Enable after outgoing email and recipient permissions have been tested.",
        ),
    ],
    single=True,
)
dt(
    "KPI Audit Event",
    [
        f("event_type"),
        f("reference_doctype", "Link", "DocType"),
        f("reference_name"),
        f("employee", "Link", "Employee"),
    ]
    + identity[:5]
    + [
        f("actor", "Link", "User"),
        f("reason", "Small Text"),
        f("payload", "Code", "JSON"),
    ],
    autoname="hash",
)
p = ROOT / "doctype/kpi_audit_event/kpi_audit_event.json"
data = json.loads(p.read_text())
data["permissions"] = [
    role("KPI Manager"),
    role("KPI Final Reviewer"),
    role("Employee"),
    role("System Manager"),
]
p.write_text(json.dumps(data, indent=2) + "\n")
dt(
    "KPI Notification Outbox",
    [
        f("dedup_key", unique=1, reqd=1),
        f("recipient", "Link", "User", reqd=1),
        f("reference_doctype", "Link", "DocType", reqd=1),
        f("reference_name", reqd=1),
        f("event_type", reqd=1),
        f("status", "Select", "Pending\nSent\nFailed\nSuppressed", default="Pending"),
        f("attempts", "Int", default="0"),
        f("last_error", "Small Text"),
        f("notification_created", "Check", default="0"),
        f("email_queued", "Check", default="0"),
    ],
    autoname="hash",
)
p = ROOT / "doctype/kpi_notification_outbox/kpi_notification_outbox.json"
data = json.loads(p.read_text())
data["permissions"] = [role("System Manager")]
p.write_text(json.dumps(data, indent=2) + "\n")
# Access is further constrained by Python permission hooks and controlled actions.
for name in [
    "KPI Component",
    "KPI Perspective",
    "KPI Structure",
    "KPI Structure Assignment",
]:
    slug = name.lower().replace(" ", "_")
    p = ROOT / "doctype" / slug / (slug + ".json")
    data = json.loads(p.read_text())
    data["permissions"].append(role("KPI Final Reviewer"))
    if name != "KPI Structure":
        data["permissions"].append(role("Employee"))
    p.write_text(json.dumps(data, indent=2) + "\n")
p = ROOT / "doctype/kpi_review/kpi_review.json"
data = json.loads(p.read_text())
for permission in data["permissions"]:
    permission["create"] = 0
p.write_text(json.dumps(data, indent=2) + "\n")
p = ROOT / "doctype/kpi_audit_event/kpi_audit_event.json"
data = json.loads(p.read_text())
data["fields"] += [
    f("assignment_name"),
    f("period_start", "Date"),
    f("period_end", "Date"),
]
data["field_order"] = [field["fieldname"] for field in data["fields"]]
p.write_text(json.dumps(data, indent=2) + "\n")
for dtype in ["KPI Structure Item", "KPI Review Item"]:
    slug = dtype.lower().replace(" ", "_")
    p = ROOT / "doctype" / slug / (slug + ".json")
    data = json.loads(p.read_text())
    for field in data["fields"]:
        if field["fieldname"] == "target_display":
            field["fieldtype"] = "Small Text"
    p.write_text(json.dumps(data, indent=2) + "\n")
p = ROOT / "doctype/kpi_review/kpi_review.json"
data = json.loads(p.read_text())
index = data["field_order"].index("items")
data["fields"].insert(index, f("assessment_overview", "HTML", read_only=1))
data["field_order"] = [field["fieldname"] for field in data["fields"]]
for field in data["fields"]:
    if field["fieldname"] == "items":
        field["label"] = "Detailed Assessment Rows"
p.write_text(json.dumps(data, indent=2) + "\n")

