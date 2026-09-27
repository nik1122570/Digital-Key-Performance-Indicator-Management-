# SF KPI — developer handover

**Version:** 0.1.0rc1 · **Baseline:** SF Group KPI specification v2.0 (18 September 2026).

A dedicated Frappe app installed on an existing ERPNext site. It contains the KPI masters, submitted agreements and assignments, controlled employee/reviewer assessments, period generation, exclusions, audit history, reports and scorecards. No ERPNext core changes or site Server Scripts are required.

**Target:** Frappe 15 + ERPNext 15 + HRMS 15, MariaDB, Python 3.10+. Installation rejects other major versions. Version 16 and PostgreSQL require a separate compatibility qualification. Employee and Designation integration assumes the standard v15 HRMS/ERPNext masters.

**Handover status:** source implementation and local verification are complete. This is a release candidate for staging, not a production-certified deployment. No live site was changed. The authoring environment did not have Frappe, Bench, MariaDB or Redis, so real integration/concurrency tests and all site UAT remain to be executed by the deploying developer.

## Start here

1. Read [Deployment](docs/DEPLOYMENT.md), then [Architecture and implementation decisions](docs/ARCHITECTURE.md).
2. Run the local tests and the supplied Bench integration suite on an isolated test site.
3. Complete the [45-scenario acceptance checklist](docs/UAT.md), including security, concurrent requests and PDF output.
4. Configure approved roles, explicit organizational permissions and assignment data.
5. Enable generation from an explicit date only after staging acceptance. It is **off by default**. Email delivery is also off until configured and tested.

## Included

- Six main/single DocTypes: KPI Perspective, KPI Component, KPI Structure, KPI Structure Assignment, KPI Review and KPI Settings; two child tables.
- Two internal DocTypes: immutable KPI Audit Event and transactional KPI Notification Outbox.
- Native Draft / Submitted / Cancelled docstatus for Structure, Assignment and Review.
- Typed Structure targets, immutable historical snapshots, explicit zero entry and weighted manual ratings.
- Server actions for self entry, handoff, final entry, submission, return, N/A, cancellation, amendment and audited correction.
- Daily generation/catch-up, unique period revisions, overlap locks and scoped notifications.
- Eleven scoped Script Reports, a KPI workspace, employee trend view and an A4 Jinja scorecard.
- Local rule/service tests, Bench integration tests, a concurrency probe and source packaging tools.

## Local checks (no Frappe installation)

From the `kpi_management` repository root:

```sh
python -m unittest discover -s tests -v
find kpi_management -name '*.js' -print0 | xargs -0 -n1 node --check
python -m pip install build flit_core
python -m build --no-isolation
```

The local service/access tests use a small Frappe stub. They do not replace real database, browser or HTTP authorization tests. See [Verification](docs/VERIFICATION.md) for the exact executed checks and limits.

The handover archive contains the source tree, the v2.0 DOCX/PDF specification, source distributions, verification evidence and SHA-256 checksums. See [API](docs/API.md) and [Operations](docs/OPERATIONS.md) for maintenance details.
