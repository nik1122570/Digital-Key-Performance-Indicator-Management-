import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Keep tool independent of Frappe imports.
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
module = ROOT / "kpi_management/kpi_management"
(module / "report").mkdir(exist_ok=True)
(module / "report/__init__.py").touch()
for name in REPORTS:
    slug = name.lower().replace(" ", "_")
    folder = module / "report" / slug
    folder.mkdir(exist_ok=True)
    (folder / "__init__.py").touch()
    (folder / (slug + ".py")).write_text(
        "from kpi_management.reports import execute as run_report\n\n\ndef execute(filters=None):\n    return run_report("
        + repr(name)
        + ", filters)\n"
    )
    roles = (
        ["Employee", "KPI Final Reviewer", "KPI Manager", "System Manager"]
        if name != "KPI Reviewer Workbench"
        else ["KPI Final Reviewer"]
    )
    ref = (
        "KPI Audit Event"
        if name == "KPI Review Applicability Audit"
        else "KPI Structure Assignment"
        if name == "KPI Assignment Structure Validity"
        else "KPI Review"
    )
    data = dict(
        doctype="Report",
        name=name,
        report_name=name,
        module="KPI Management",
        ref_doctype=ref,
        report_type="Script Report",
        is_standard="Yes",
        disabled=0,
        add_total_row=0,
        prepared_report=0,
        roles=[{"role": r} for r in roles],
    )
    (folder / (slug + ".json")).write_text(json.dumps(data, indent=2) + "\n")
    fields = [
        dict(
            fieldname=k,
            label=k.replace("_", " ").title(),
            fieldtype=t,
            **({"options": o} if o else {}),
        )
        for k, t, o in [
            ("company", "Link", "Company"),
            ("department", "Link", "Department"),
            ("employee", "Link", "Employee"),
        ]
    ]
    if name != "KPI Review Applicability Audit":
        fields += [
            dict(
                fieldname="review_frequency",
                label="Frequency",
                fieldtype="Select",
                options="\nMonthly\nQuarterly\nSemi-Annual",
            )
        ]
    if name not in [
        "KPI Review Applicability Audit",
        "KPI Assignment Structure Validity",
    ]:
        fields += [
            dict(
                fieldname="final_reviewed_by",
                label="Final Reviewer",
                fieldtype="Link",
                options="User",
            ),
            dict(fieldname="review_year", label="Review Year", fieldtype="Int"),
            dict(fieldname="period_start", label="Period Start From", fieldtype="Date"),
            dict(fieldname="period_end", label="Period End To", fieldtype="Date"),
        ]
    (folder / (slug + ".js")).write_text(
        "frappe.query_reports["
        + json.dumps(name)
        + "] = "
        + json.dumps({"filters": fields}, indent=2)
        + ";\n"
    )
folder = module / "print_format/kpi_scorecard"
folder.mkdir(parents=True, exist_ok=True)
pf = dict(
    doctype="Print Format",
    name="KPI Scorecard",
    doc_type="KPI Review",
    module="KPI Management",
    standard="Yes",
    custom_format=1,
    print_format_type="Jinja",
    html=(ROOT / "kpi_management/templates/kpi_scorecard.html").read_text(),
    disabled=0,
    raw_printing=0,
)
(folder / "kpi_scorecard.json").write_text(json.dumps(pf, indent=2) + "\n")
folder = module / "workspace/kpi_management"
folder.mkdir(parents=True, exist_ok=True)
content = [
    {
        "id": "kpi-header",
        "type": "header",
        "data": {"text": '<span class="h4">KPI Management</span>', "col": 12},
    },
    {
        "id": "kpi-info",
        "type": "paragraph",
        "data": {
            "text": "Agree targets, complete self assessments and finalize reviews. Official scores come from submitted Reviews.",
            "col": 12,
        },
    },
]
links = []
for category, names, kind in [
    (
        "Assessment",
        ["KPI Review", "My KPI Performance", "KPI Reviewer Workbench"],
        "mixed",
    ),
    (
        "Setup",
        [
            "KPI Perspective",
            "KPI Component",
            "KPI Structure",
            "KPI Structure Assignment",
            "KPI Settings",
        ],
        "DocType",
    ),
    ("Reports", REPORTS[2:], "Report"),
]:
    links.append({"type": "Card Break", "label": category})
    for name in names:
        typ = "Report" if name in REPORTS else "DocType"
        links.append({"type": "Link", "label": name, "link_type": typ, "link_to": name})
    content.append(
        {
            "id": category.lower(),
            "type": "card",
            "data": {"card_name": category, "col": 4},
        }
    )
workspace = dict(
    doctype="Workspace",
    name="KPI Management",
    label="KPI Management",
    title="KPI Management",
    module="KPI Management",
    icon="organization",
    public=1,
    is_hidden=0,
    sequence_id=30,
    content=json.dumps(content),
    links=links,
    roles=[
        {"role": r}
        for r in ["Employee", "KPI Final Reviewer", "KPI Manager", "System Manager"]
    ],
)
(folder / "kpi_management.json").write_text(json.dumps(workspace, indent=2) + "\n")

