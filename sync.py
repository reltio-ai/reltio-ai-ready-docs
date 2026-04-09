#!/usr/bin/env python3
"""
Sync docs.md and index.md from reltio-docs-sync to this repo.

Uses Bitbucket API with BB_USERNAME + BB_APP_PASSWORD env vars.
Skips commit if content is unchanged.
"""

import os
import sys
import hashlib
import requests

SOURCE_REPO = "reltio-ondemand/reltio-docs-sync"
SOURCE_BRANCH = "main"
FILES = ["docs.md", "index.md"]

BB_USERNAME = os.environ.get("BB_USERNAME")
BB_APP_PASSWORD = os.environ.get("BB_APP_PASSWORD")

if not BB_USERNAME or not BB_APP_PASSWORD:
    print("ERROR: BB_USERNAME and BB_APP_PASSWORD environment variables required")
    sys.exit(1)

auth = (BB_USERNAME, BB_APP_PASSWORD)
changed = False

for filename in FILES:
    url = f"https://api.bitbucket.org/2.0/repositories/{SOURCE_REPO}/src/{SOURCE_BRANCH}/{filename}"
    print(f"Downloading {filename} from {SOURCE_REPO}...")

    response = requests.get(url, auth=auth, timeout=120)
    if response.status_code != 200:
        print(f"ERROR: Failed to download {filename}: HTTP {response.status_code}")
        sys.exit(1)

    new_content = response.content
    new_hash = hashlib.sha256(new_content).hexdigest()

    if os.path.exists(filename):
        with open(filename, "rb") as f:
            old_hash = hashlib.sha256(f.read()).hexdigest()
        if old_hash == new_hash:
            print(f"  {filename}: unchanged, skipping")
            continue

    with open(filename, "wb") as f:
        f.write(new_content)

    size_mb = len(new_content) / (1024 * 1024)
    print(f"  {filename}: updated ({size_mb:.1f} MB)")
    changed = True

if not changed:
    print("No changes detected. Nothing to commit.")
    sys.exit(0)

print("Files updated. Ready to commit.")
sys.exit(0)
