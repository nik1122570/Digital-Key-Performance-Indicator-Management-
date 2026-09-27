# Operations and maintenance

## Daily operation

The Frappe daily scheduler runs `kpi_management.scheduler.daily`: generation, reminders, then notification dispatch. Keep workers running. `kpi_management.scheduler.generate` and `kpi_management.notifications.dispatch` can also be run with `bench --site SITE execute ...` for controlled recovery; these functions commit transactions and must not be called inside another business transaction.

The generator checks every submitted Assignment, including expired ones, and only full closed calendar periods starting on/after Generation From Date. A missing job day is recovered on the next run. Self due date starts from actual Draft creation; final due date starts from each valid employee handoff. Assignment expiry never makes an already-eligible historical review invalid.

Inspect `logs/kpi_management.log` / the site's configured logger output for created/skipped/blocked/failed counts, Frappe Error Log for exceptions, KPI Assignment Structure Validity for coverage/user changes, and KPI Notification Outbox for delivery problems. The audit history includes generation exceptions. The logger location can vary with Bench/site configuration.

A disabled/mismatched employee account is an exception, not a proxy-rating opportunity. Inform the responsible manager and correct the agreement/account mapping through an audited process.

## Notification retry

Review transactions insert outbox records, then enqueue delivery after commit. Daily dispatch provides catch-up. In-app alerts and queued email use a deterministic recipient/record/event/stage key; reminders additionally key by day. Email sending remains subject to Frappe Email Queue retries. Delivery is not a claim of inbox receipt.

A pre-due reminder is generated on the configured lead day; overdue notices run daily. Returned Reviews keep the original self deadline and get a new final deadline after the next handoff.

An outbox item retries up to 10 dispatch attempts. A technical administrator should diagnose the Error Log, correct the outgoing-email/worker/account issue, then reset the failed item's attempts/status to Pending for a controlled retry. Do not delete/recreate a Review to retry a notification. Disabled recipients or revoked scope produce Suppressed entries, not leaked messages.

## Correction sequences

- **Return:** final reviewer records a reason; final values are archived in audit history and cleared. The employee must send again.
- **N/A/reinstate:** a scoped, non-self final reviewer records a reason. The Review returns to self stage; current final entries/acknowledgement are invalidated. All N/A remains an unscored Draft and alerts managers.
- **Incorrect completed Review:** manager cancels with a reason, then uses Amend Review. The old record remains cancelled; the new revision requires fresh entries.
- **Incorrect source agreement:** inspect dependents; individually cancel completed Reviews and archive/remove Drafts with reasons. Cancel and amend the Assignment/Structure in dependency order. Use Amend with Corrected Assignment for cancelled Review history. For a deleted Draft interval, use Recover Closed Period with a correction reason after the source is fixed.
- **Private evidence on deleted Drafts:** files are reattached to the immutable KPI Audit Event in the same transaction. The original audit JSON retains the record contents and source references.

Submitted agreements have fixed intervals. There is no editable end date after submission, automatic partial period or proration. For a planned future role change, create a non-overlapping agreement on a calendar boundary; resolve mid-period gaps explicitly with HR. Do not add Allow on Submit to bypass this policy.

## Scaling and upgrades

This initial release enumerates periods per Assignment and loads report results within the requested filters. For large installations, benchmark expected employee/period volume on staging, apply report date/company filters, and consider batched scheduled work before enabling a large historical backfill. Preserve the locking and uniqueness contracts when optimizing.

Routine indexes are created by `after_migrate`. New schema changes should be versioned, migrated and rehearsed against a restored staging database. Regenerate metadata/views with the tools only when changing the corresponding generators; commit generated JSON alongside controller/script changes. Rebuild the Print Format JSON after editing the source Jinja template.

Useful commands from the app repository root:

```sh
python tools/build_metadata.py
python tools/build_views.py
python -m unittest discover -s tests -v
```

Never run test-suite fixture creation on a live business site. Keep staging emails suppressed until delivery tests are explicitly ready.

