# Acceptance and integration checklist

The v2.0 specification is the business baseline. **No scenario below is marked as site-accepted.** Local automated coverage is evidence for part of a scenario; it does not establish that a deployed site passes it. The deploying developer and business owner must record the actual result and evidence for all 45 scenarios.

## Execution order

1. Run the local suite, then `bench --site TEST_SITE run-tests --app kpi_management` on a disposable v15 site.
2. Configure separate employee, other employee, scoped reviewer, unscoped reviewer, manager, and technical-admin users. Also test one employee holding reviewer and manager roles.
3. Test native forms, resource REST, custom APIs, query reports/CSV exports, print endpoints, direct private-file URLs and zip downloads. Sharing must not widen app scope.
4. Run concurrent requests using the probe below and test stale edits in two browser tabs.
5. Generate short, long, excluded, returned and cancelled scorecards through Frappe's own PDF engine. Verify pagination, repeated headers, page numbers and privacy.
6. Exercise scheduler recovery/outbox retries with outgoing email suppressed; then deliberately test delivery. Record counts and boundary periods.

## Concurrent HTTP probes

Set `KPI_TEST_SITE` and `KPI_TEST_TOKEN` in your local environment. The token must belong to the scoped test KPI Manager; do not commit it. `KPI_TEST_TOKEN` has the normal `api_key:api_secret` form. The tool does not print credentials.

For an eligible closed period with no existing Review/history:

```sh
python tools/concurrency_probe.py --confirm-isolated-test-site duplicate-review --assignment TEST_ASSIGNMENT --start 2024-04-01 --end 2024-06-30
```

For two valid Draft Assignments for the same employee with overlapping dates (neither submitted):

```sh
python tools/concurrency_probe.py --confirm-isolated-test-site assignment-overlap --drafts DRAFT_A DRAFT_B
```

Expect exactly one success and a business/concurrency rejection for the other. Verify the resulting database count, then test both amendment races and a simultaneous employee-entry/applicability change. These probes have not been executed in the authoring environment.

## Scenario register

| ID | Scenario | Expected result | Supplied coverage | Site result / evidence |
|---|---|---|---|---|
| U01 | Inspect Component metadata | Non-submittable; exactly the five business fields specified; no lifecycle Status or target/scoring fields. | Local metadata tests | NOT RUN |
| U02 | Disable a used Component | Blocked for new Structures; existing submitted snapshots and reviews retain their agreed meaning. | Bench test supplied | NOT RUN |
| U03 | Inspect Perspective | Non-submittable; referenced records cannot be deleted. | Implementation supplied; staging required | NOT RUN |
| U04 | Submit Structure totals 99.99, 100, 100.01 | Only exactly 100.00 submits; reject zero/negative weights and duplicate components. | Local scoring/weight tests | NOT RUN |
| U05 | Same Component in two roles | Distinct Structure targets are saved without changing the master. | Implementation supplied; staging required | NOT RUN |
| U06 | Enter all seven indicator types | Correct target control, stored value, display and matching actual-result control. | Local typed-value tests; UI pending | NOT RUN |
| U07 | Enter zero, No, percent 95 and Duration 2 Weeks | All explicit values remain distinct from missing input; percent remains 95; no unit conversion. | Local explicit-zero and typed-value tests | NOT RUN |
| U08 | Submit with missing unit/currency or extra target storage | Server blocks invalid row even through API/import. | Local typed-value tests | NOT RUN |
| U09 | Submit wrong designation/company or draft Structure | Assignment submission blocked. | Controller checks; staging required | NOT RUN |
| U10 | Submit overlapping Assignments concurrently | Exactly one succeeds; inclusive overlap enforced across frequencies. | Concurrent HTTP probe supplied | NOT RUN |
| U11 | Assignment covers 1 April–30 June; rate in July | Q2 review allowed; present-day expiry does not block historical eligibility. | Local period tests; Bench fixture uses expired agreement | NOT RUN |
| U12 | Assignment starts 15 April | No Q2 review; Q3 eligible if fully covered; no prorated target. | Local calendar tests | NOT RUN |
| U13 | Assignment contains no full review period | Assignment submission blocked with a clear period message. | Local calendar tests | NOT RUN |
| U14 | Use cancelled source or open/future period | Create, rating actions and final submission blocked. | Local eligibility tests | NOT RUN |
| U15 | Edit current Component or Employee text | Submitted Structure, Assignment and Review snapshots unchanged; HR mismatch reported. | Implementation supplied; staging required | NOT RUN |
| U16 | Remove deprecated schema/features | No Scoring Band or Assignment Target Override DocType, report, scheduler branch or UI action remains. | Local schema tests | NOT RUN |
| U17 | Scheduler inserts blank Review | Draft, Pending Self Rating; no mandatory final fields prevent creation. | Bench fixture creates blank Draft | NOT RUN |
| U18 | Another employee edits actuals/self-rating | Denied through UI, REST and custom actions, regardless of shared access. | Local policy tests; live HTTP pending | NOT RUN |
| U19 | Manager or reviewer tries proxy self-rating | Denied, including users with multiple roles. | Local actor tests; Bench proxy test | NOT RUN |
| U20 | Blank rating versus explicit zero | Blank blocks handoff; deliberately entered zero succeeds with comment and other required fields. | Local zero/flag tests; Bench test | NOT RUN |
| U21 | Employee sends a valid self-rating | Remains docstatus 0, moves to Pending Final Rating, records employee identity/time and revision. | Bench workflow test supplied | NOT RUN |
| U22 | Final reviewer edits employee input | Denied; self inputs remain unchanged. | Narrow payload and actor tests | NOT RUN |
| U23 | Submit with incomplete self/final rating, missing variance comment or required plan | Blocked through every submission path. | Local stage guards; Bench test | NOT RUN |
| U24 | Return then resubmit | Reason logged; final values invalidated; employee acknowledges again before completion. | Local return logic; staging required | NOT RUN |
| U25 | Valid Complete and Submit | Docstatus 1, Completed, calculated totals/category and actual reviewer recorded; normal editing locked. | Bench workflow test supplied | NOT RUN |
| U26 | Exclude 20 of 100 original weight | Use section 14 example: effective weights 50, 37.5, 0, 12.5; Self 80; Final 83.75. | Local specification-example test | NOT RUN |
| U27 | Change N/A after employee handoff | Atomic return, revision increment, prior acknowledgement invalid, final fields cleared; fresh employee handoff required. | Local service test; Bench test supplied | NOT RUN |
| U28 | Reinstate excluded component | Actual and self entry flags invalidated for that row; new completion required. | Local service test | NOT RUN |
| U29 | All rows excluded or one row remains | All excluded stays unscored Draft; one remaining row gets effective weight 100. | Local scoring and stage tests | NOT RUN |
| U30 | Equal thirds and maximum raw ratings | 33.34 + 33.33 + 33.33; total 100.00 exactly; deterministic tie-break. | Local exact-rounding test + 1,000 randomized cases | NOT RUN |
| U31 | Negative, over-limit, NaN, infinite or excess-precision rating | Server rejects; client totals cannot override calculations. | Local invalid-rating tests | NOT RUN |
| U32 | Category boundary values | 0, 39.99, 40, 59.99, 60, 70.99, 71, 89.99, 90, 100 each map correctly. | Local category-boundary tests | NOT RUN |
| U33 | Rerun/concurrent scheduler, including retry after notification failure | One Review per logical slot; no duplicate notification key. | Concurrent HTTP probe; live retry test pending | NOT RUN |
| U34 | Missed scheduler days and expired Assignment | Catch up all eligible closed periods from generation date; original period dates retained. | Local period enumeration; live scheduler pending | NOT RUN |
| U35 | Leap year, month/year end, Q4 and H2 rollover | Canonical boundaries and opening dates correct in site timezone. | Local leap/calendar tests | NOT RUN |
| U36 | Cancel and amend a completed Review | Original retained at docstatus 2; new revision Draft with fresh acknowledgements; scheduler does not regenerate it. | Bench cancellation/amendment test supplied | NOT RUN |
| U37 | Backdated replacement Assignment or concurrent amendment | No second live assessment for the same measurement interval. | Locks/current reads; live concurrent amendment pending | NOT RUN |
| U38 | Reviewer role without explicit Company scope | Forms, lists, exports, prints, attachments and reports deny access. | Local scope tests; full live endpoints pending | NOT RUN |
| U39 | Reviewer rates own Review or tampers with row/snapshot | Denied despite multiple roles; source rows and snapshots remain intact. | Local actor/payload tests; Bench direct edit test | NOT RUN |
| U40 | Employee user_id changes or account disabled | Identity/access exception raised; no silent transfer or proxy self-rating. | Local account tests | NOT RUN |
| U41 | Cancel linked Structure or Assignment | Dependency checks block; no silent cascade or historical deletion. | Bench dependency test supplied | NOT RUN |
| U42 | Concurrent self save and applicability action | Stale operation rejected; neither change overwrites the other or preserves an invalid acknowledgement. | Bench stale-request test; mixed concurrent UI/API pending | NOT RUN |
| U43 | Management and annual reports | Only Completed submitted totals by default; counts, frequency and excluded weight shown; permission scope enforced. | Scoped SQL implemented; live report UAT pending | NOT RUN |
| U44 | Print short and long Reviews, with N/A and cancelled revisions | Readable A4; repeated headers; correct labels, weights, totals and acknowledgement records. | Synthetic HTML templates rendered; native PDF UAT pending | NOT RUN |
| U45 | Reminder retries and returned Reviews | No duplicate same-day stage message; original self deadline preserved and new final deadline visible. | Dedup/stage keys implemented; live retry UAT pending | NOT RUN |

## Acceptance record

- Deployed commit/tag and archive checksum:
- Frappe / ERPNext / HRMS versions:
- MariaDB version and transaction isolation:
- Test site and timezone:
- Integration output and concurrency results:
- Identity/scope matrix and attachment/export evidence:
- PDF samples and browser evidence:
- Generation cutoff and expected/actual first batch:
- Remaining defects and resolution:
- Developer verification date:
- HR/business acceptance and production release approval:

Do not mark release acceptance complete while any critical or high-severity defect remains or a required scenario lacks evidence.

