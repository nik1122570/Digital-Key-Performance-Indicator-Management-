# API contract

Use Frappe session authentication/CSRF protection or a normal user API token. APIs execute as that user, not as a proxy employee. All mutating app APIs require POST and return the updated Review in Frappe's `message` wrapper, except deletion and applicability requests. No Guest endpoints exist.

Base path: `/api/method/kpi_management.api.`

| Method | Inputs beyond `name`, `modified` | Authorized actor |
|---|---|---|
| `capabilities` | `name` only; read-only GET supported | Anyone with current Review read access |
| `record_self` | `entries` array, optional `summary` object | Assigned current enabled employee, Pending Self Rating |
| `send_for_final` | None | Same employee; complete applicable self entries required |
| `record_final` | `entries` array, optional `summary` object | Scoped non-self final reviewer, Pending Final Rating |
| `complete` | None | Same reviewer; all final guards pass |
| `return_to_employee` | `reason` | Scoped non-self final reviewer, Pending Final Rating |
| `set_applicability` | `row_name`, `excluded` 0/1, `reason` | Scoped non-self final reviewer in either Draft stage |
| `request_applicability` | `row_name`, `reason` | Assigned employee; request has no automatic rating effect |
| `cancel` | `reason` | Scoped KPI Manager; submitted Review |
| `amend` | `reason`, optional `corrected_assignment` | Scoped KPI Manager; cancelled latest predecessor |
| `delete_draft` | `reason` | Scoped KPI Manager; full audit/evidence archive is retained |
| `recover_period` | `assignment`, `period_start`, `period_end`, optional `correction_reason`; no `name`/`modified` | Scoped KPI Manager; same eligibility and duplicate guards as scheduler |

`modified` must be the exact timestamp returned with the current document. Reload after a TimestampMismatchError. Do not retry with a newer timestamp without reviewing the intervening change.

## Entry examples

Employee self entry for a Number indicator (explicit zero is valid):

```json
{
  "name": "KPR-2026-00001",
  "modified": "2026-07-02 10:00:00.000000",
  "entries": [
    {
      "name": "actual-review-child-row-name",
      "actual_number": 0,
      "self_rating": 0,
      "employee_comment": "No completed output this period."
    }
  ],
  "summary": {
    "employee_summary": "Assessment entered for the quarter.",
    "development_needs": "Additional training."
  }
}
```

Use exactly one of `actual_number`, `actual_choice`, `actual_date`, `actual_text`, matching the immutable indicator. Do not send unit/currency overrides or `*_entered` flags. Ratings are raw points with a maximum equal to `original_weight` even when `effective_weight` is larger. Numeric results and scores are unrelated manual inputs.

Final entry:

```json
{
  "name": "KPR-2026-00001",
  "modified": "2026-07-03 10:00:00.000000",
  "entries": [
    {
      "name": "actual-review-child-row-name",
      "final_rating": 10,
      "reviewer_comment": "Explanation is mandatory when final differs from self."
    }
  ],
  "summary": {
    "final_summary": "Final assessment completed.",
    "strengths": "Planning discipline.",
    "improvement_actions": "Mandatory when the final total is below 60."
  }
}
```

`entries: []` can save a summary alone. `entries: [{"name": "row-name", "clear": 1}]` clears that actor's entry and its completion flags. A row update is a complete explicit entry, not an implicit default-zero patch. Save can be incomplete; handoff/submission applies all stage requirements.

## Regular resources

Use standard Frappe document APIs for masters, Structures and Assignments. Submitted records follow native cancellation/amendment constraints. Review resource reads are permitted by role/scope; Review resource writes are rejected. Use the app actions instead of generic `frappe.client.set_value`, `submit`, arbitrary JSON update or import.

For reports, use the standard Frappe query-report endpoint with one of the supplied report names. SQL predicates always reapply scope, including when caller-supplied filters request a different company or employee. Raw database/console access is trusted developer administration, outside these HTTP guarantees.

