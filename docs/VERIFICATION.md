# Verification record — 0.1.0rc1

Executed in the authoring workspace on **18 September 2026**.

| Check | Result | Scope |
|---|---|---|
| Local unittest suite | **55 tests passed** | Calendar eligibility, typed values, manual scoring, zero-entry flags, category boundaries, access policy, review-action rules and package metadata |
| Randomized scoring | **1,000 cases passed** inside the suite | Applicable effective weights and full raw ratings total exactly 100; excluded rows contribute zero |
| Python syntax/metadata | **Passed** | All Python files parse; DocType/Report/Workspace/Print Format JSON parses; field orders/links and lifecycles checked |
| Ruff `F` rules | **Passed** | Undefined names, unused imports and related static checks |
| JavaScript syntax | **15 files passed** | Form scripts, shared UI and report definitions checked with Node |
| Source distribution and wheel | **Both built** | Flit sdist and wheel; app metadata/assets checked in the resulting wheel |
| Jinja rendering | **Passed** | StrictUndefined rendering of short, long and cancelled synthetic scorecards |
| Browser sample rendering | **Passed** | Isolated Chrome rendered all three HTML examples at a 900px viewport; no horizontal overflow. Short/long layouts visually inspected |
| Handover archive | **Checked during packaging** | File hashes, ZIP CRC, required files, no caches/site credentials, extraction and local tests from the extracted source |

The local policy/service tests use a small Frappe stub. They validate application decisions and inputs; they do **not** exercise Frappe's real permission stack, DocType import, transaction isolation, schema creation, scheduler workers or browser forms.

## Supplied but not executed here

- **12 Bench integration tests** using actual Frappe documents and MariaDB transactions, including lifecycle, actor separation, zero ratings, scope, exclusions, cancellation/amendment, stale writes, duplicate periods and private evidence.
- Concurrent HTTP mutation probe for duplicate Review generation and overlapping Assignment submission.
- All 45 specification scenarios in `UAT.md`, including simultaneous amendment, worker retries, direct REST/export/print/download security and site-specific permissions.
- Frappe/wkhtmltopdf scorecard output, page numbering and page breaks. Browser HTML rendering is not equivalent to native PDF qualification.
- A real install/migrate/build on the target Frappe/ERPNext/HRMS patch versions.
- Production data volume, managed-hosting behavior, SMTP delivery and compatibility with other app overrides.

The authoring workspace had no Frappe/Bench/MariaDB/Redis installation. **No production or staging site was changed.** The developer must run the supplied integration and acceptance checks on the actual deployment stack and resolve any failures before production release.

The package's outer `verification/` folder contains local test/static/build output and synthetic scorecard evidence. The final ZIP's checksum is supplied alongside it; `SHA256SUMS` records each packaged file's hash.

