"""Render synthetic scorecards without Frappe. Requires Jinja2 for developer QA."""

from pathlib import Path
from types import SimpleNamespace
import sys
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kpi_management.domain import calculate, category


def sample(long=False, cancelled=False):
    items = []
    weights = [40, 30, 20, 10] if not long else [5] * 20
    for i, w in enumerate(weights, 1):
        item = dict(
            idx=i,
            structure_item_id=f"S-{i}",
            kpi_component=f"Example KPI {i}",
            objective=f"Example KPI {i}: Complete planned service activities",
            metric="Complete the agreed service activities within the reporting period. "
            + (
                "Each activity is recorded, reviewed and confirmed using the agreed team process. "
                * 3
                if long
                else ""
            ),
            indicator="Percentage",
            target_number=95,
            target_display="95%",
            actual_number=97,
            actual_entered=1,
            perspective_label=["Customer", "Operations", "Learning"][i % 3],
            original_weight=w,
            not_applicable=int(i == 3),
            self_rating=w * 0.8,
            final_rating=w * 0.9,
            self_rating_entered=1,
            final_rating_entered=1,
            na_reason="Scope was transferred to another team for this review period."
            if i == 3
            else "",
            na_decided_by="reviewer@example.test" if i == 3 else "",
            employee_comment="Fictional assessment for layout verification.",
            reviewer_comment="Sample variance explanation.",
            duration_unit="",
            currency="",
        )
        items.append(item)
    scores, totals = calculate(items)
    for row, score in zip(items, scores):
        row.update({k: float(v) for k, v in score.items()})
    values = dict(
        name="SAMPLE-DO-NOT-IMPORT",
        docstatus=2 if cancelled else 1,
        employee_name="Sample Employee",
        employee="SAMPLE-EMPLOYEE",
        company="Example Company — synthetic data",
        department="Operations",
        designation="Service Manager",
        reporting_line="Sample Supervisor",
        review_frequency="Quarterly",
        period_key="2026-Q2",
        period_start="2026-04-01",
        period_end="2026-06-30",
        kpi_structure="SAMPLE-STRUCTURE",
        structure_version=1,
        workflow_state="Cancelled" if cancelled else "Completed",
        items=[SimpleNamespace(**r) for r in items],
        rating_category=category(totals["final_total"]),
        employee_summary="Synthetic data. This example demonstrates the scorecard layout.",
        development_needs="Continue structured weekly planning.",
        final_summary="Activities reviewed against the agreement.",
        strengths="Clear reporting.",
        improvement_actions="",
        self_sent_by="employee@example.test",
        self_sent_on="2026-07-03 10:00",
        final_reviewed_by="reviewer@example.test",
        final_reviewed_on="2026-07-06 14:00",
        review_revision=0,
        amended_from=None,
    )
    values.update({k: float(v) if v is not None else None for k, v in totals.items()})
    doc = SimpleNamespace(**values)
    doc.get = lambda key: getattr(doc, key, None)
    return doc


if __name__ == "__main__":
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/examples"
    destination.mkdir(parents=True, exist_ok=True)
    template = Environment(undefined=StrictUndefined, autoescape=True).from_string(
        (ROOT / "kpi_management/templates/kpi_scorecard.html").read_text()
    )
    frappe = SimpleNamespace(utils=SimpleNamespace(formatdate=str, format_datetime=str))
    for filename, doc in [
        ("scorecard_short", sample()),
        ("scorecard_long", sample(True)),
        ("scorecard_cancelled", sample(cancelled=True)),
    ]:
        html = template.render(doc=doc, frappe=frappe)
        wrapper = (
            '<!doctype html><html><head><meta charset="utf-8"><title>SF KPI — synthetic scorecard</title><style>body{font-family:Arial,sans-serif;max-width:740px;margin:24px auto;padding:24px}.visible-pdf{display:none}</style></head><body><div class="print-format">'
            + html
            + "</div></body></html>"
        )
        (destination / (filename + ".html")).write_text(wrapper)
        print(filename, len(html), "characters rendered")

