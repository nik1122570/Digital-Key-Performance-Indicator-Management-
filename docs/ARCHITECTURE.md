# Architecture and implementation decisions

## Source map

| Path | Responsibility |
|---|---|
| `kpi_management/domain.py` | Decimal scoring, exact weight normalization, typed values, calendar periods and categories; no Frappe dependency |
| `kpi_management/reviews.py` | Locked review creation, entry actions, handoff, exclusions, final completion and corrections |
| `kpi_management/api.py` | Authenticated narrow actions; write methods accept POST only |
| `kpi_management/permissions.py` | Explicit organizational scope for document, list and report access |
| `kpi_management/security.py` | Private KPI attachment/content checks and File subclass |
| `kpi_management/scheduler.py` | Daily generation, catch-up and reminders |
| `kpi_management/notifications.py` | Transactional outbox and scoped delivery/retry |
| `kpi_management/kpi_management/doctype/` | Standard DocType JSON, controllers and form scripts |
| `kpi_management/reports.py` | Shared scoped report implementations |
| `kpi_management/templates/kpi_scorecard.html` | Source Jinja scorecard template |
| `kpi_management/install.py` | Dependency checks, roles, states, indexes and preflight |
| `tests/` | Local rules, policy, service and package checks |
| `kpi_management/tests/` | Real Frappe/MariaDB integration tests for Bench |
| `tools/` | Metadata/view regeneration, concurrent-request probe, render demo and release packaging |

## Workflow and document lifecycle

Perspective and Component are nonsubmittable masters. Component has Disabled, with no business status or target fields. Structure, Assignment and Review are submittable and use standard docstatus 0/1/2.

Review uses the read-only `workflow_state` field and guarded **app actions**. It deliberately does not install a separate active Frappe Workflow record: employee entry, reviewer applicability actions in either draft stage, explicit zero confirmation, audit reasons and server-owned entry flags are handled together in one transactional service. This is the implementation choice for the specification's workflow behavior; do not layer another state machine over it.

```
Pending Self Rating (Draft)
  -> Send for Final Rating -> Pending Final Rating (Draft)
  -> Complete and Submit -> Completed (Submitted)
  -> Cancel with reason -> Cancelled

Return / applicability change -> Pending Self Rating (Draft)
Cancelled -> controlled amendment -> new Draft revision
```

`before_validate` blocks direct Review saves, even when client JSON attempts to supply action flags. A Python ContextVar provides the internal action capability; client document flags are not trusted. API methods load the persisted record and accept only narrow input fields. Direct Frappe submit/cancel cannot bypass the app actions. Built-in amendment creation is rejected; the custom amendment action creates a fresh revision with `amended_from`.

Draft totals are labelled incomplete and hidden when entry flags are missing. Zero is accepted only when supplied in the record-entry action. The dialog explicitly asks the actor to confirm values, including zeros. Source targets, row identity, ordering and weights are validated against the submitted Structure on each assessment action.

## Data and scoring

- Component meaning is reusable; typed targets belong only to Structure Items.
- Supported indicators: Percentage, Number, Currency, Duration, Yes No, Date, Text.
- Target/actual values select one storage field. Numeric values support six decimals within ±999,999,999,999.999999; original weights and raw ratings support two decimals. NaN/infinity are rejected.
- Duration uses a fixed Hours/Days/Weeks/Months/Years unit. Currency uses an explicit Currency link. Neither performs conversions.
- `target_display` uses Small Text storage rather than a 140-character Data field, avoiding truncation of narrative Text targets. This does not add a second target.
- Score calculation is manual, capped by original weight. Normalized weights use largest-remainder cents with original row order/source ID as deterministic tie-breakers. Points use Decimal half-up rounding and displayed-point sums.
- All excluded means no score and no submission. N/A changes clear final inputs/acknowledgement, increment applicability revision and return the Review to the employee. Reinstatement invalidates the row's actual/self entry flags.
- Official reports use submitted Completed Reviews. Draft and cancelled records have no official category. Raw values on excluded rows remain historical context.

## Concurrency and immutable history

Native Assignment saves acquire an Employee lock before the framework locks the Assignment. Review actions acquire Employee, Assignment and Review locks; source validation uses locking reads to avoid stale repeatable-read snapshots. Duplicate checks use current locking reads and a database unique index over Assignment + period start/end + revision. There is also an employee/overlapping-period guard across replacement Assignments. Structure versions serialize on Designation.

Interactive mutations require the current `modified` value. Competing writes return a stale-record error instead of silently overwriting. Database deadlocks/timeouts remain retriable operational errors; concurrency tests on the deployment's MariaDB version are mandatory.

Submitted business fields have no Allow on Submit. Master meaning changes after submitted use require replacement Components. Structures and Assignments cannot be cancelled while protected dependents exist. No automatic cancellation cascade is used.

The scheduler does not recreate cancelled slots or deliberately deleted Draft intervals. Amendments require the most recent cancelled predecessor and fresh ratings. Corrected-source amendments preserve employee, frequency and exact period, rebuild targets from the new submitted agreement, and never carry old scores onto new targets.

## Technical records and attachments

Two internal DocTypes support requirements without adding business configuration:

- **KPI Audit Event:** immutable action history and correction snapshots, scoped to the same employee/organization. A deleted Draft's complete JSON and private attachments are retained here before deletion. Audit records block scheduler recreation until a manager explicitly recovers the corrected period with a reason.
- **KPI Notification Outbox:** deterministic deduplication key, recipient, pending/sent/failed/suppressed state and bounded retries. It is committed with the business transaction. Workers deliver after commit; failed notification delivery never recreates a Review.

KPI files must be private local uploads. Private content reads and downloads recheck current record access; file ownership/sharing does not grant extra KPI content rights. External storage apps or other File overrides require integration review. Technical administrators with server/database access remain trusted; application guards do not attempt to restrict an administrator's direct SQL/Python execution.

## Scope and limits

This release includes Desk forms, reports and printing. It does not include a separate Website User/mobile portal, payroll/bonus integration, automatic actual-result ingestion, target proration, automatic scoring formulas, cross-site consolidation or migration from a prior KPI implementation.

Company/Department/Employee User Permissions must apply to all DocTypes; only explicit values are used. A tree permission does not silently add descendants. Shared masters are maintained by a KPI Manager with at least one explicit Company scope; company-specific transactions additionally enforce their own scope.

Account mapping changes block self-entry. Correct an erroneous agreement through the documented audited correction chain; do not silently transfer completed self-assessments to another user or add proxy self-rating.

## Primary platform references checked during development

- [Frappe apps](https://docs.frappe.io/framework/user/en/basics/apps)
- [Hooks and scheduler integration](https://docs.frappe.io/framework/user/en/python-api/hooks)
- [Document controllers](https://docs.frappe.io/framework/user/en/basics/doctypes/controllers)
- [v15 document save/submit lifecycle](https://github.com/frappe/frappe/blob/version-15/frappe/model/document.py)
- [v15 permission hooks](https://github.com/frappe/frappe/blob/version-15/frappe/permissions.py)
- [v15 private file implementation](https://github.com/frappe/frappe/blob/version-15/frappe/core/doctype/file/file.py)

These sources establish the target API design, not that this package has passed a live Frappe installation test.

