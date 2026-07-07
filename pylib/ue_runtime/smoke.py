"""
Aggregated smoke check for installed task-runtime projects.

This command is intentionally read-only and process-local. It gives humans and
CI one stable endpoint that covers the standard service checks an installed
project should pass after scaffold, install, or bundle adoption.
"""

from pathlib import Path


SMOKE_SCHEMA_VERSION = "ue-task-runtime-smoke/v1"


def run_runtime_smoke(service, target_root=None):
    default_root = service.context.repo_root if service.context else "."
    target_root = Path(target_root or default_root).resolve()
    checks = []

    descriptor = service.descriptor()
    checks.append(_check("about", descriptor["readiness"]["ok"], descriptor["schema_version"]))

    validation = service.validate_report()
    validation_payload = validation.as_dict()
    checks.append(_check("validate", validation.ok, validation_payload["schema_version"], issue_count=validation.issue_count))

    boundary = service.boundary_report()
    boundary_payload = boundary.as_dict()
    checks.append(_check("boundary", boundary.ok, boundary_payload["schema_version"], issue_count=boundary.issue_count))

    readiness = service.readiness_report()
    readiness_payload = readiness.as_dict()
    checks.append(_check("doctor", readiness.ok, readiness_payload["schema_version"], issue_count=readiness.issue_count))

    install_audit = service.install_audit(target_root)
    checks.append(_check(
        "install-audit",
        install_audit["ok"],
        install_audit["schema_version"],
        issue_count=install_audit["issue_count"],
    ))

    return {
        "schema_version": SMOKE_SCHEMA_VERSION,
        "ok": all(check["ok"] for check in checks),
        "target_root": str(target_root),
        "check_count": len(checks),
        "checks": checks,
        "reports": {
            "about": descriptor,
            "validate": validation_payload,
            "boundary": boundary_payload,
            "doctor": readiness_payload,
            "install_audit": install_audit,
        },
    }


def _check(name, ok, schema_version, issue_count=0):
    return {
        "name": name,
        "ok": bool(ok),
        "schema_version": schema_version,
        "issue_count": int(issue_count or 0),
    }
