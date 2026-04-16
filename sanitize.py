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

    # CRED-1: Base64-encoded OAuth credential reltio_ui:makita (Scan v2)
    {
        "id": "CRED-1",
        "description": "Base64 OAuth credential reltio_ui:makita",
        "find": "cmVsdGlvX3VpOm1ha2l0YQ==",
        "replace": "<BASE64_CREDENTIALS_PLACEHOLDER>",
    },

    # CRED-2: Base64-encoded OAuth credential reltio_ui:secret (Scan v2)
    {
        "id": "CRED-2",
        "description": "Base64 OAuth credential reltio_ui:secret",
        "find": "cmVsdGlvX3VpOnNlY3JldA==",
        "replace": "<BASE64_CREDENTIALS_PLACEHOLDER>",
    },

    # CRED-1 related: Internal auth-test endpoint
    {
        "id": "CRED-1b",
        "description": "Internal auth-test endpoint",
        "find": "auth-test.reltio.com",
        "replace": "{auth-server}.reltio.com",
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

    # TOKEN-1: Bearer token used across 161 API examples (Scan v2)
    {
        "id": "TOKEN-1",
        "description": "Bearer token 204938ca (161 occurrences)",
        "find": "204938ca-2cf7-44b0-b11a-1b4c59984512",
        "replace": "{your-access-token}",
    },
    # TOKEN-1 space-injected variant (formatting artifact, 11+ lines)
    {
        "id": "TOKEN-1s",
        "description": "Bearer token 204938ca with spaces injected",
        "find": r"204938\s*ca-2\s*cf7-44\s*b0-b11a-1\s*b4c59984512",
        "replace": "{your-access-token}",
        "is_regex": True,
    },
    # TOKEN-1 variant — last 2 digits differ (line 54692)
    {
        "id": "TOKEN-1v1",
        "description": "Bearer token 204938ca variant (ends 10)",
        "find": "204938ca-2cf7-44b0-b11a-1b4c59984510",
        "replace": "{your-access-token}",
    },
    # TOKEN-1 variant — middle digits differ (line 34557)
    {
        "id": "TOKEN-1v2",
        "description": "Bearer token 204838ca variant (middle differs)",
        "find": "204838ca-2cf7-44b0-b11a-1b4c58984512",
        "replace": "{your-access-token}",
    },

    # TOKEN-2: Bearer token in 11 API examples (Scan v2)
    {
        "id": "TOKEN-2",
        "description": "Bearer token c3f28fdd (11 occurrences)",
        "find": "c3f28fdd-e082-4f90-8840-9896914eaf41",
        "replace": "{your-access-token}",
    },
    # TOKEN-2 space-injected variant (line 55481)
    {
        "id": "TOKEN-2s",
        "description": "Bearer token c3f28fdd with spaces injected",
        "find": r"c3f28fdd-e082-4\s+f90-8840-9896914e\s*af41",
        "replace": "{your-access-token}",
        "is_regex": True,
    },

    # TOKEN-3: Additional OAuth tokens in auth flow examples (Scan v2)
    {
        "id": "TOKEN-3a",
        "description": "Access token 24bc1fb5 in OAuth example",
        "find": "24bc1fb5-8440-4d5e-8431-53b7c9a4dc35",
        "replace": "{your-access-token}",
    },
    {
        "id": "TOKEN-3b",
        "description": "Refresh token 676742af in OAuth example",
        "find": "676742af-989b-4d40-b7cc-f69ccadd45ea",
        "replace": "{your-refresh-token}",
    },
    {
        "id": "TOKEN-3c",
        "description": "Refresh token fa7e5817 in OAuth example",
        "find": "fa7e5817-0bf6-461c-97ab-c6b7a9e0f556",
        "replace": "{your-refresh-token}",
    },

    # TOKEN-4: Additional bearer tokens found in OCD deep scan (never in any scan report)
    {
        "id": "TOKEN-4a",
        "description": "Bearer token 5925f793 (7 occurrences)",
        "find": "5925f793-c092-43ec-b3a3-65ce8e194440",
        "replace": "{your-access-token}",
    },
    {
        "id": "TOKEN-4b",
        "description": "Bearer token 5925f793 variant (ends 48)",
        "find": "5925f793-c092-43ec-b3a3-65ce8e194448",
        "replace": "{your-access-token}",
    },
    {
        "id": "TOKEN-4c",
        "description": "Bearer token 1925f793",
        "find": "1925f793-c092-43ec-b3a3-65ce8e194440",
        "replace": "{your-access-token}",
    },
    {
        "id": "TOKEN-4d",
        "description": "Bearer token b55461c0",
        "find": "b55461c0-243f-43d7-964a-5582c783fb70",
        "replace": "{your-access-token}",
    },
    {
        "id": "TOKEN-4e",
        "description": "Bearer token 18c13d18",
        "find": "18c13d18-e704-4290-a470-8108479cd464",
        "replace": "{your-access-token}",
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

    # PII-1: Employee email alexander.panchenko (Scan v2)
    {
        "id": "PII-1",
        "description": "Employee email (alexander.panchenko)",
        "find": "alexander.panchenko@reltio.com",
        "replace": "user@example.com",
    },

    # PII-2: Employee emails in entity/relation API examples (Scan v2)
    {
        "id": "PII-2a",
        "description": "Employee email (abhradeep.sengupta)",
        "find": "abhradeep.sengupta@reltio.com",
        "replace": "user@example.com",
    },
    {
        "id": "PII-2b",
        "description": "Employee email (ayush.jain)",
        "find": "ayush.jain@reltio.com",
        "replace": "user@example.com",
    },
    {
        "id": "PII-2c",
        "description": "Employee email (terence.kirk)",
        "find": "terence.kirk@reltio.com",
        "replace": "user@example.com",
    },

    # PII-3: Additional employee emails found in deep scan (not in Rafael's reports)
    {
        "id": "PII-3a",
        "description": "Employee email (andrey.hudyakov)",
        "find": "andrey.hudyakov@reltio.com",
        "replace": "user@example.com",
    },
    {
        "id": "PII-3b",
        "description": "Employee email (thirupathi.reddy)",
        "find": "thirupathi.reddy@reltio.com",
        "replace": "user@example.com",
    },
    {
        "id": "PII-3c",
        "description": "Employee email (stepan.ermakov)",
        "find": "stepan.ermakov@reltio.com",
        "replace": "user@example.com",
    },
    {
        "id": "PII-3d",
        "description": "Employee email (pavel.gizatullin)",
        "find": "pavel.gizatullin@reltio.com",
        "replace": "user@example.com",
    },
    {
        "id": "PII-3e",
        "description": "Employee email (mahalakshmi.krishnakumar)",
        "find": "mahalakshmi.krishnakumar@reltio.com",
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

    # INFRA-1: Internal Kubernetes node IP (Scan v2)
    {
        "id": "INFRA-1",
        "description": "Internal K8s node IP 10.30.32.127",
        "find": "10.30.32.127",
        "replace": "10.x.x.x",
    },

    # INFRA-2: Internal S3 bucket reltio.match.test (Scan v2)
    {
        "id": "INFRA-2",
        "description": "Internal S3 bucket reltio.match.test",
        "find": "reltio.match.test",
        "replace": "{your-s3-bucket}",
    },

    # INFRA-3: STS External ID with ASCII hyphens (Scan v2)
    {
        "id": "INFRA-3a",
        "description": "STS External ID c77f24a0 (ASCII hyphens)",
        "find": "c77f24a0-f5a6-11f0-9e2e-325096e39f47",
        "replace": "{your-external-id}",
    },
    # INFRA-3: STS External ID with Unicode non-breaking hyphens U+2011 (Scan v2)
    {
        "id": "INFRA-3b",
        "description": "STS External ID c77f24a0 (Unicode hyphens)",
        "find": "c77f24a0\u2011f5a6\u201111f0\u20119e2e\u2011325096e39f47",
        "replace": "{your-external-id}",
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
    # === Scan v1 findings ===
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

    # === Scan v2 findings ===
    (r"cmVsdGlvX3VpOm1ha2l0YQ==", "CRED-1: Base64 OAuth reltio_ui:makita"),
    (r"cmVsdGlvX3VpOnNlY3JldA==", "CRED-2: Base64 OAuth reltio_ui:secret"),
    (r"auth-test\.reltio\.com", "CRED-1: Internal auth-test endpoint"),
    (r"204938ca-2cf7-44b0-b11a-1b4c59984512", "TOKEN-1: Bearer token (161 hits)"),
    (r"204938\s*ca-2\s*cf7-44\s*b0-b11a-1\s*b4c59984512", "TOKEN-1s: Bearer token space-injected"),
    (r"204938ca-2cf7-44b0-b11a-1b4c59984510", "TOKEN-1v1: Bearer token variant (ends 10)"),
    (r"204838ca-2cf7-44b0-b11a-1b4c58984512", "TOKEN-1v2: Bearer token variant (mid differs)"),
    (r"c3f28fdd-e082-4f90-8840-9896914eaf41", "TOKEN-2: Bearer token (11 hits)"),
    (r"c3f28fdd-e082-4\s+f90-8840-9896914e\s*af41", "TOKEN-2s: Bearer token space-injected"),
    (r"24bc1fb5-8440-4d5e-8431-53b7c9a4dc35", "TOKEN-3a: Access token"),
    (r"676742af-989b-4d40-b7cc-f69ccadd45ea", "TOKEN-3b: Refresh token"),
    (r"fa7e5817-0bf6-461c-97ab-c6b7a9e0f556", "TOKEN-3c: Refresh token"),
    (r"5925f793-c092-43ec-b3a3-65ce8e194440", "TOKEN-4a: Bearer token (7 hits)"),
    (r"5925f793-c092-43ec-b3a3-65ce8e194448", "TOKEN-4b: Bearer token variant"),
    (r"1925f793-c092-43ec-b3a3-65ce8e194440", "TOKEN-4c: Bearer token"),
    (r"b55461c0-243f-43d7-964a-5582c783fb70", "TOKEN-4d: Bearer token"),
    (r"18c13d18-e704-4290-a470-8108479cd464", "TOKEN-4e: Bearer token"),
    (r"alexander\.panchenko@reltio\.com", "PII-1: Employee email"),
    (r"abhradeep\.sengupta@reltio\.com", "PII-2: Employee email"),
    (r"ayush\.jain@reltio\.com", "PII-2: Employee email"),
    (r"terence\.kirk@reltio\.com", "PII-2: Employee email"),
    (r"10\.30\.32\.127", "INFRA-1: Internal K8s node IP"),
    (r"reltio\.match\.test", "INFRA-2: Internal S3 bucket"),
    (r"c77f24a0", "INFRA-3: STS External ID (unicode or ASCII)"),

    # === Deep scan findings (not in Rafael's reports) ===
    (r"andrey\.hudyakov@reltio\.com", "PII-3: Employee email"),
    (r"thirupathi\.reddy@reltio\.com", "PII-3: Employee email"),
    (r"stepan\.ermakov@reltio\.com", "PII-3: Employee email"),
    (r"pavel\.gizatullin@reltio\.com", "PII-3: Employee email"),
    (r"mahalakshmi\.krishnakumar@reltio\.com", "PII-3: Employee email"),
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
