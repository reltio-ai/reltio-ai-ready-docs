#!/usr/bin/env python3
"""
sanitize.py — Redact sensitive information from docs.md and index.md
before pushing to the public GitHub repository.

Addresses all findings from the Pre-Publication Security Risk Report
(Critical, High, Medium). Runs as a post-processing step after docs.md
and index.md are generated, before github_sync.py pushes to GitHub.

Usage:
    python3 sanitize.py                  # Sanitize files in place
    python3 sanitize.py --dry-run        # Show what would change, don't modify
    python3 sanitize.py --verify         # Check that no sensitive patterns remain

Pipeline integration:
    sync.py  ->  sanitize.py  ->  github_sync.py
"""

import re
import sys
import os

FILES_TO_SANITIZE = ["docs.md", "index.md"]

# ============================================================================
# REPLACEMENT RULES
#
# Each rule has:
#   id          — finding ID from the security report
#   description — what it fixes
#   find        — exact string or regex pattern
#   replace     — replacement value
#   is_regex    — if True, treat `find` as a regex (default False)
#
# Order matters: more specific / longer patterns go first to prevent
# partial matches when shorter patterns overlap.
# ============================================================================

RULES = [
    # ============================ CRITICAL ============================

    # C-1: Hardcoded Maven repo credential (password + username)
    {
        "id": "C-1",
        "description": "Hardcoded Maven repo password",
        "find": "pbBmG3jbdYUazoj7",
        "replace": "{password}",
    },
    {
        "id": "C-1b",
        "description": "Internal Maven username",
        "find": "read.only.workflow",
        "replace": "{username}",
    },

    # C-2: AWS IAM Access Key ID in pre-signed S3 URL
    {
        "id": "C-2a",
        "description": "AWS IAM Access Key ID",
        "find": "AKIAIMVSSDXKTO4I7LPQ",
        "replace": "AKIAIOSFODNN7EXAMPLE",
    },
    {
        "id": "C-2b",
        "description": "AWS pre-signed URL signature",
        "find": "f5cfdd89be90560a5899c82725e81e7987457d52fda9f960b0605785d5de60dc",
        "replace": "{signature}",
    },

    # ============================== HIGH ==============================

    # H-1: Real AWS Account IDs (5 distinct values)
    {
        "id": "H-1a",
        "description": "AWS Account ID 930358522410",
        "find": "930358522410",
        "replace": "123456789012",
    },
    {
        "id": "H-1b",
        "description": "AWS Account ID 634947810771",
        "find": "634947810771",
        "replace": "123456789012",
    },
    {
        "id": "H-1c",
        "description": "AWS Account ID 438691793027",
        "find": "438691793027",
        "replace": "123456789012",
    },
    {
        "id": "H-1d",
        "description": "AWS Account ID 713795429718",
        "find": "713795429718",
        "replace": "123456789012",
    },
    {
        "id": "H-1e",
        "description": "AWS Account ID 641923904298",
        "find": "641923904298",
        "replace": "123456789012",
    },

    # H-2: Live STS External ID in IAM trust policy
    {
        "id": "H-2",
        "description": "STS External ID in IAM trust policy",
        "find": "018a2b7c-77e7-712a-b671-385bdb86317c",
        "replace": "{your-external-id}",
    },

    # H-3: Real employee emails
    {
        "id": "H-3a",
        "description": "Employee email (sergey.zagorodin)",
        "find": "sergey.zagorodin@reltio.com",
        "replace": "user@example.com",
    },
    {
        "id": "H-3b",
        "description": "Employee email (pradeep.krishnappa)",
        "find": "pradeep.krishnappa@reltio.com",
        "replace": "user@example.com",
    },

    # H-4: Internal dev hostnames (longer/more specific first)
    {
        "id": "H-4a",
        "description": "Internal dev hostname idev-01-sfdc-sbc-api",
        "find": r"idev-01-sfdc-sbc-api\.reltio\.com",
        "replace": "{environment}.reltio.com",
        "is_regex": True,
    },
    {
        "id": "H-4b",
        "description": "Internal dev hostname idev-01-ih",
        "find": r"idev-01-ih\.reltio\.com",
        "replace": "{environment}.reltio.com",
        "is_regex": True,
    },
    {
        "id": "H-4c",
        "description": "Internal dev hostname idev-01-dev",
        "find": r"idev-01-dev\.reltio\.com",
        "replace": "{environment}.reltio.com",
        "is_regex": True,
    },
    {
        "id": "H-4d",
        "description": "Internal dev hostname idev-02",
        "find": r"idev-02\.reltio\.com",
        "replace": "{environment}.reltio.com",
        "is_regex": True,
    },
    {
        "id": "H-4e",
        "description": "Production hostname eu03-prod",
        "find": "eu03-prod.reltio.com",
        "replace": "{environment}.reltio.com",
    },

    # H-4: Internal env name in URL paths (not just hostnames)
    {
        "id": "H-4f",
        "description": "Internal env name idev-01-dev in URL path",
        "find": "/idev-01-dev/",
        "replace": "/{environment}/",
    },

    # H-4: Internal IAM user
    {
        "id": "H-4g",
        "description": "Internal IAM user in ARN",
        "find": "akzj-s-ssca6264",
        "replace": "{iam-user}",
    },

    # H-4: Internal SQS queue name
    {
        "id": "H-4h",
        "description": "Internal SQS queue name",
        "find": "gabriel_standard_q",
        "replace": "{queue-name}",
    },

    # H-4: Internal Snowpipe identifier
    {
        "id": "H-4i",
        "description": "Internal Snowpipe queue identifier",
        "find": r"sf-snowpipe-AIDA2MMMF4VLMNI5KESTV-bHVbiwsnUnY6icU-zr52Q",
        "replace": "sf-snowpipe-{your-snowpipe-id}",
    },

    # H-4: Internal node group name
    {
        "id": "H-4j",
        "description": "Internal node group name",
        "find": "etalon-idev-02-jobs",
        "replace": "{nodesGroup}",
    },

    # H-4: Developer tenant IDs (order: longest first)
    {
        "id": "H-4k",
        "description": "Developer tenant ID apanchenko123",
        "find": "apanchenko123",
        "replace": "{tenantId}",
    },
    {
        "id": "H-4l",
        "description": "Developer tenant ID woods123",
        "find": "woods123",
        "replace": "{tenantId}",
    },
    {
        "id": "H-4m",
        "description": "Developer tenant ID mgupta (in task name)",
        "find": "tenant mgupta",
        "replace": "tenant {tenantId}",
    },
    {
        "id": "H-4n",
        "description": "Developer tenant ID mgupta (JSON field)",
        "find": '"tenantId": "mgupta"',
        "replace": '"tenantId": "{tenantId}"',
    },
    {
        "id": "H-4o",
        "description": "Developer tenant ID mgupta (URL path)",
        "find": "/mgupta/",
        "replace": "/{tenantId}/",
    },

    # H-5: Internal S3 bucket names
    {
        "id": "H-5a",
        "description": "Internal S3 bucket reltio-api-tasks-internal",
        "find": "reltio-api-tasks-internal",
        "replace": "{your-bucket-name}",
    },
    {
        "id": "H-5b",
        "description": "Internal S3 bucket reltio-data-exports-integration-test",
        "find": "reltio-data-exports-integration-test",
        "replace": "{your-bucket-name}",
    },

    # H-6: Internal Nexus/Maven repo URLs
    {
        "id": "H-6",
        "description": "Internal Nexus/Maven repo URL",
        "find": "repo-dev.reltio.com",
        "replace": "{artifact-repository-host}",
    },

    # ============================= MEDIUM =============================

    # M-1: GCP internal service account email
    {
        "id": "M-1",
        "description": "GCP internal service account email",
        "find": "data-pipeline-hub@idev-01.iam.gserviceaccount.com",
        "replace": "{your-service-account}@{your-project}.iam.gserviceaccount.com",
    },

    # M-2: Private IP from nslookup output
    {
        "id": "M-2",
        "description": "Private IP from nslookup output",
        "find": "10.0.0.18",
        "replace": "10.0.0.x",
    },

    # M-3: EC2 instance IDs (regex)
    {
        "id": "M-3a",
        "description": "Real EC2 instance IDs",
        "find": r"\bi-[0-9a-f]{10,17}\b",
        "replace": "i-1234567890abcdef0",
        "is_regex": True,
    },

    # M-3: Kubernetes pod names (regex — specific prefixes)
    {
        "id": "M-3b",
        "description": "Kubernetes pod names (dataload-*)",
        "find": r"dataload-[a-z0-9]{8,10}-[a-z0-9]{5}",
        "replace": "dataload-xxxxx-xxxxx",
        "is_regex": True,
    },
    {
        "id": "M-3c",
        "description": "Kubernetes pod names (dataprocess-*)",
        "find": r"dataprocess-[a-z0-9]{8,10}-[a-z0-9]{5}",
        "replace": "dataprocess-xxxxx-xxxxx",
        "is_regex": True,
    },
    {
        "id": "M-3d",
        "description": "Kubernetes pod names (api-* in JSON context)",
        "find": r'"api-[a-z0-9]{7,10}-[a-z0-9]{5}"',
        "replace": '"api-xxxxx-xxxxx"',
        "is_regex": True,
    },

    # M-4: Google search URL with author browser fingerprint
    #      Replace entire Google search URL with direct AWS docs link
    {
        "id": "M-4",
        "description": "Google search URL with browser fingerprint (rlz param)",
        "find": r"https://www\.google\.com/search\?q=aws\+secrets\+manager&rlz=[^)]+",
        "replace": "https://aws.amazon.com/secrets-manager/",
        "is_regex": True,
    },

    # ========================= ADDITIONAL =============================

    # Staging doc URLs (from previous audit — not in security report
    # but should not appear in public docs)
    {
        "id": "EXTRA-1",
        "description": "Staging documentation URL",
        "find": "docstaging.reltio.com",
        "replace": "docs.reltio.com",
    },
]

# ============================================================================
# VERIFICATION PATTERNS
#
# After sanitization, these patterns should NOT appear in the output.
# Used by --verify mode. Each is a (regex_pattern, description) tuple.
# ============================================================================

VERIFY_PATTERNS = [
    (r"pbBmG3jbdYUazoj7", "C-1: Maven password"),
    (r"read\.only\.workflow", "C-1: Maven username"),
    (r"AKIAIMVSSDXKTO4I7LPQ", "C-2: AWS Access Key ID"),
    (r"930358522410", "H-1: AWS Account ID"),
    (r"634947810771", "H-1: AWS Account ID"),
    (r"438691793027", "H-1: AWS Account ID"),
    (r"713795429718", "H-1: AWS Account ID"),
    (r"641923904298", "H-1: AWS Account ID"),
    (r"018a2b7c-77e7-712a-b671-385bdb86317c", "H-2: STS External ID"),
    (r"sergey\.zagorodin@reltio\.com", "H-3: Employee email"),
    (r"pradeep\.krishnappa@reltio\.com", "H-3: Employee email"),
    (r"idev-0\d+-?[a-z-]*\.reltio\.com", "H-4: Internal dev hostname"),
    (r"/idev-0\d+-?[a-z-]*/", "H-4: Internal env name in URL path"),
    (r"eu03-prod\.reltio\.com", "H-4: Production hostname"),
    (r"etalon-idev-", "H-4: Internal node group"),
    (r"apanchenko123", "H-4: Developer tenant ID"),
    (r"woods123", "H-4: Developer tenant ID"),
    (r'"tenantId":\s*"mgupta"', "H-4: Developer tenant ID (mgupta)"),
    (r"tenant mgupta", "H-4: Developer tenant ID (mgupta)"),
    (r"reltio-api-tasks-internal", "H-5: Internal S3 bucket"),
    (r"reltio-data-exports-integration-test", "H-5: Internal S3 bucket"),
    (r"repo-dev\.reltio\.com", "H-6: Internal Maven repo URL"),
    (r"data-pipeline-hub@idev-01\.iam", "M-1: GCP service account"),
    (r"10\.0\.0\.18", "M-2: Private IP"),
    (r"docstaging\.reltio\.com", "EXTRA: Staging URL"),
    (r"gabriel_standard_q", "H-4: Internal SQS queue"),
    (r"akzj-s-ssca6264", "H-4: Internal IAM user"),
    (r"sf-snowpipe-AIDA2MMMF4VLMNI5KESTV", "H-4: Internal Snowpipe ID"),
]


def apply_rules(content, rules, dry_run=False):
    """Apply all sanitization rules to content. Returns (new_content, log_entries)."""
    log = []
    for rule in rules:
        rid = rule["id"]
        desc = rule["description"]
        find = rule["find"]
        repl = rule["replace"]
        is_regex = rule.get("is_regex", False)

        if is_regex:
            matches = re.findall(find, content)
            count = len(matches)
            if count > 0:
                if not dry_run:
                    content = re.sub(find, repl, content)
                log.append(f"  [{rid}] {desc}: {count} replacement(s)")
        else:
            count = content.count(find)
            if count > 0:
                if not dry_run:
                    content = content.replace(find, repl)
                log.append(f"  [{rid}] {desc}: {count} replacement(s)")

    return content, log


def verify_clean(content, filename):
    """Check that no sensitive patterns remain. Returns list of violations."""
    violations = []
    for pattern, desc in VERIFY_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            # Find line numbers for context
            lines = []
            for i, line in enumerate(content.split("\n"), 1):
                if re.search(pattern, line):
                    lines.append(i)
                    if len(lines) >= 3:
                        break
            line_info = ", ".join(str(l) for l in lines)
            if len(lines) < len(matches):
                line_info += f" (+{len(matches) - len(lines)} more)"
            violations.append(f"  FAIL: {desc} — {len(matches)} match(es) at line(s) {line_info}")
    return violations


def main():
    dry_run = "--dry-run" in sys.argv
    verify_only = "--verify" in sys.argv

    if dry_run:
        print("=" * 60)
        print("DRY RUN — no files will be modified")
        print("=" * 60)

    if verify_only:
        print("=" * 60)
        print("VERIFY MODE — checking for remaining sensitive patterns")
        print("=" * 60)

    all_clean = True
    total_rules_applied = 0

    for filename in FILES_TO_SANITIZE:
        if not os.path.exists(filename):
            print(f"SKIP: {filename} not found")
            continue

        print(f"\n{'=' * 60}")
        print(f"Processing: {filename}")
        print(f"{'=' * 60}")

        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()

        original_size = len(content)

        if verify_only:
            violations = verify_clean(content, filename)
            if violations:
                all_clean = False
                print(f"\n  {len(violations)} sensitive pattern(s) found:")
                for v in violations:
                    print(v)
            else:
                print("  CLEAN — no sensitive patterns detected")
            continue

        # Apply sanitization rules
        content, log_entries = apply_rules(content, RULES, dry_run=dry_run)

        if log_entries:
            mode = "Would apply" if dry_run else "Applied"
            print(f"\n  {mode} {len(log_entries)} rule(s):\n")
            for entry in log_entries:
                print(entry)
            total_rules_applied += len(log_entries)
        else:
            print("\n  No sensitive patterns found — file is clean")

        if not dry_run and log_entries:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            new_size = len(content)
            delta = new_size - original_size
            print(f"\n  Written: {new_size:,} bytes (delta: {delta:+,} bytes)")

        # Always verify after sanitization
        if not dry_run and log_entries:
            violations = verify_clean(content, filename)
            if violations:
                all_clean = False
                print(f"\n  WARNING: {len(violations)} pattern(s) still present after sanitization:")
                for v in violations:
                    print(v)
            else:
                print("  VERIFIED: all sensitive patterns removed")

    # Summary
    print(f"\n{'=' * 60}")
    if verify_only:
        if all_clean:
            print("RESULT: All files clean")
        else:
            print("RESULT: Sensitive patterns detected — run sanitize.py to fix")
            sys.exit(1)
    elif dry_run:
        print(f"DRY RUN COMPLETE: {total_rules_applied} rule(s) would be applied")
    else:
        if total_rules_applied > 0:
            print(f"SANITIZATION COMPLETE: {total_rules_applied} rule(s) applied")
        else:
            print("SANITIZATION COMPLETE: files already clean")
        if not all_clean:
            print("WARNING: Some patterns could not be fully removed — review output above")
            sys.exit(1)
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
