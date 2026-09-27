"""Package verified source, distributions, specification and evidence for handover."""

import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile

EXCLUDED = {
    ".git",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
    "dist",
    ".DS_Store",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--spec-docx", required=True, type=Path)
    parser.add_argument("--spec-pdf", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = "0.1.0rc1"
    label = "SF_KPI_" + version
    dest = args.destination.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    stage = dest / label
    if stage.exists():
        shutil.rmtree(stage)

    def ignore(directory, names):
        return [
            n
            for n in names
            if n in EXCLUDED or n.endswith((".pyc", ".pyo", ".egg-info"))
        ]

    shutil.copytree(root, stage / "kpi_management", ignore=ignore)
    (stage / "specification").mkdir()
    shutil.copy2(args.spec_docx, stage / "specification" / args.spec_docx.name)
    shutil.copy2(args.spec_pdf, stage / "specification" / args.spec_pdf.name)
    shutil.copytree(args.evidence, stage / "verification", ignore=ignore)
    (stage / "distributions").mkdir()
    for suffix in (".whl", ".tar.gz"):
        matches = list((root / "dist").glob("*" + suffix))
        if len(matches) != 1:
            raise RuntimeError(
                "Build exactly one current distribution of each type before packaging"
            )
        shutil.copy2(matches[0], stage / "distributions" / matches[0].name)
    (stage / "START_HERE.md").write_text("""# SF KPI developer handover — 0.1.0rc1

Open **kpi_management/README.md** first, then **kpi_management/docs/DEPLOYMENT.md**.

This is the source release candidate for the SF Group KPI specification v2.0.
Target: Frappe / ERPNext / HRMS v15, MariaDB. No site has been deployed by this handover.

- `kpi_management/`: complete app source; this is the directory to put under Git and install with Bench.
- `specification/`: the authoritative v2.0 DOCX and PDF.
- `distributions/`: built Python source archive and wheel; normal Bench deployment uses the source repository.
- `verification/`: local test/static/build evidence and synthetic scorecard HTML/screenshots.
- `kpi_management/docs/UAT.md`: all 45 business scenarios and staging result register.
- `SHA256SUMS`: hashes of every other packaged file.

55 local tests passed, including 1,000 randomized scoring cases. The package also
includes 12 Bench integration tests and a concurrency probe. Those live-stack
tests and site UAT still need to be run by the developer before production release.

Generation and email notifications start disabled. Configure explicit Company
scope for reviewers/managers, then enable generation from an intentional date
after staging acceptance. See the deployment guide for the File override check.

Verify the outer ZIP against its companion .sha256 file. After extraction, use
`sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS` (macOS).
""")
    files = sorted(p for p in stage.rglob("*") if p.is_file())
    sums = "".join(
        hashlib.sha256(p.read_bytes()).hexdigest()
        + "  "
        + p.relative_to(stage).as_posix()
        + "\n"
        for p in files
    )
    (stage / "SHA256SUMS").write_text(sums)
    archive = dest / (label + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(stage.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(dest))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert not any(
            any(part in EXCLUDED for part in Path(name).parts) for name in z.namelist()
        )
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dest / (label + ".zip.sha256")).write_text(digest + "  " + archive.name + "\n")
    print(
        f"{archive}\n{archive.stat().st_size:,} bytes; {len(files) + 1} files; SHA256 {digest}"
    )


if __name__ == "__main__":
    main()

