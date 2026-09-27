# Deployment runbook

## 1. Record the target environment

On the intended Bench, record `bench version` and `bench --site SITE list-apps`. Confirm Frappe, ERPNext and HRMS all use **version-15**, MariaDB, functioning workers/Redis, scheduler status, outgoing email if needed, installed custom apps and site timezone. The intended timezone is `Africa/Dar_es_Salaam`; the app uses the site's configured date.

Inspect existing KPI/Appraisal customizations before installing. Do not install over independently created DocTypes with these names. Plan a separate, reviewed migration if they already exist. This package does not import historical appraisals or replace the standard HRMS appraisal process.

This release uses a narrowly scoped **File controller subclass** to close v15 private-download owner/share shortcuts for KPI evidence. The install hook rejects another installed File override. If one exists, compose the two implementations and rerun the attachment tests before deployment; do not simply remove this check. All non-KPI File behavior delegates to Frappe.

Bench shares application code among its sites. Decide which sites should install SF KPI and how a code update will be qualified across them. Each site's KPI data remains separate.

## 2. Put source under your version control

Extract the handover package. The app repository root is the directory containing `pyproject.toml`, `README.md` and the inner `kpi_management/` Python package. The outer handover directory is not the app.

Use your normal private source repository. For a local first installation, initialize the extracted app as a Git repository so Bench can clone it:

```sh
cd /srv/source/kpi_management
git init -b main
git add .
git commit -m "Import SF KPI 0.1.0rc1 handover"
git tag v0.1.0rc1
```

The directory and site names below are examples; replace them with the actual installation paths and staging site name.

## 3. Install on staging first

Use a fresh isolated test site for destructive tests. For a staging copy of existing business data, first create a restorable database/files backup and prevent external emails from leaving staging.

```sh
cd /srv/frappe-bench
bench get-app file:///srv/source/kpi_management
bench --site kpi-staging.example.test backup --with-files
bench --site kpi-staging.example.test install-app kpi_management
bench --site kpi-staging.example.test migrate
bench build --app kpi_management
bench --site kpi-staging.example.test clear-cache
bench restart
bench --site kpi-staging.example.test execute kpi_management.install.preflight
```

Alternatively, use `bench get-app` with your private Git repository URL and release branch/tag, following your normal deployment mechanism. On managed Frappe hosting, add the private app through the provider's custom-app deployment workflow. Do not attempt server-shell commands where the hosting model does not expose Bench.

Inspect `preflight` output: versions, all DocTypes installed, timezone, scheduler status, generation disabled and File override. No separate active Workflow should target KPI Review: the app owns the guarded stage transitions. Do not install an additional active Workflow or Server Script for those transitions.

## 4. Configure access and test

- Give each participating employee an enabled **System User** with **Employee** role linked through Employee.user_id. This release uses Desk; it does not include a Website User portal.
- Give final reviewers **KPI Final Reviewer**. Managers receive **KPI Manager**. A manager who also rates requires both roles.
- For reviewers and managers, create explicit **Company User Permissions** with **Apply To All DocTypes** checked. Optional Department and Employee User Permissions further restrict access by intersection.
- Scope entries match explicit record names. Descendant Company/Department tree nodes are not implicitly granted by this app; add the intended nodes explicitly. This is deliberately stricter than inherited tree access.
- A role without a Company scope grants no review authority. A shared Review does not grant rating authority. The employee cannot final-rate their own Review even with additional roles.
- System Manager/Administrator can inspect records for technical administration; normal business actions still require the relevant actor, role and scope. Never use the scheduler document owner as the assessed employee.
- Configure approved Perspectives and Components, submit valid Structures, then submit dated employee Assignments. Settings supply form defaults for the due-day fields; API-created Assignments should provide the due days explicitly.

Run the Bench integration suite only on a disposable site:

```sh
bench --site kpi-test.example.test set-config allow_tests true
bench --site kpi-test.example.test run-tests --app kpi_management
```

The tests create synthetic Company, User, Employee and KPI records. They expect standard v15 masters, including Tanzania/TZS and Male Gender from ERPNext/HRMS setup. Site-specific Employee mandatory fields may require adapting the test factory. Keep those adaptations separate from app business rules. Do not use this command on production.

Run the concurrency probe against that same isolated site, then execute all scenarios in `UAT.md`. Save test output, role/scope configuration, browser evidence, private attachment denials, exports, and short/long/cancelled PDF samples.

## 5. First generation and production rollout

After staging and business acceptance:

1. Back up the production database, public/private files and exact deployed app versions; rehearse restore on staging.
2. Deploy the approved commit, install/migrate/build and restart using the same steps as staging.
3. Verify user mappings, scopes, Structures and Assignments on each site.
4. In KPI Settings, set **Generation From Date** to the earliest period start you intend to generate. Choose it deliberately: closed periods from that date will be caught up, including expired Assignments.
5. Enable review generation. Enable the Frappe scheduler/workers if needed through the normal site administration process.
6. For a monitored initial run, execute `bench --site SITE execute kpi_management.scheduler.generate`. Inspect returned counts and exception logs. Call `bench --site SITE execute kpi_management.notifications.dispatch` after the generation transaction is committed if processing the outbox manually.
7. Confirm one Draft per expected employee/period and no unexpected historical batch. Test self access and reviewer scope using real approved test identities.
8. Configure outgoing email, then enable Email Notifications only after delivery tests. In-app notifications use the outbox regardless of this setting.

## 6. Updates and rollback

Keep application changes in Git. Apply updates to staging, back up, deploy the approved commit, run `migrate`, rebuild assets, clear cache and restart. Migration hooks add indexes/idempotent states; they do not enable generation or reset existing settings.

If rollout fails, disable KPI generation and stop KPI user activity. Preserve logs, drafts, completed Reviews and the outbox. Restore the compatible **code + database + files** backup using the rehearsed site procedure. Uninstalling the app is not a rollback plan: it may remove business records. A code-only downgrade is acceptable only if schema/data compatibility has been explicitly checked.

Before removing an existing File override or changing private file storage/CDN handling, repeat all direct-download and zip-export security tests.

