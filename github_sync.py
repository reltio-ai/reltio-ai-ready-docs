#!/usr/bin/env python3
"""
Push docs.md and index.md to the public GitHub repo via GitHub REST API.
No git clone needed — works even on a brand new empty repo.

Requires:
  GITHUB_TOKEN  - GitHub Personal Access Token (repo write scope)
"""

import os
import sys
import base64
import hashlib
import datetime
import requests

GITHUB_OWNER = "reltio-ai"
GITHUB_REPO  = "reltio-ai-ready-docs"
GITHUB_BRANCH = "main"
FILES = ["docs.md", "index.md"]
README_FILE = "README.md"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("ERROR: GITHUB_TOKEN environment variable required")
    sys.exit(1)

for f in FILES:
    if not os.path.exists(f):
        print(f"ERROR: {f} not found — run after sync.py")
        sys.exit(1)

if not os.path.exists(README_FILE):
    print(f"ERROR: {README_FILE} not found in current directory")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
base_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents"
timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
sync_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")  # replace('-','--') below handles shields.io escaping

# Stamp sync date into README
with open(README_FILE, "r") as f:
    readme_content = f.read()
import re
readme_content = re.sub(
    r"!\[Last synced\]\(https://img\.shields\.io/badge/Last%20synced-[^)]*\)",
    f"![Last synced](https://img.shields.io/badge/Last%20synced-{sync_date.replace('-', '--')}-blue)",
    readme_content
)
with open(README_FILE, "w") as f:
    f.write(readme_content)
print(f"README.md: stamped sync date {timestamp}")

any_updated = False

for filename in FILES + [README_FILE]:
    print(f"Processing {filename}...")

    with open(filename, "rb") as f:
        content_bytes = f.read()

    content_b64 = base64.b64encode(content_bytes).decode()
    new_sha = hashlib.sha256(content_bytes).hexdigest()

    # Check if file already exists (to get its SHA for update)
    url = f"{base_url}/{filename}"
    resp = requests.get(url, headers=headers, params={"ref": GITHUB_BRANCH})

    if resp.status_code == 200:
        existing = resp.json()
        existing_sha = existing.get("sha")
        # GitHub uses blob SHA (not sha256) — always update if we can't compare easily
        payload = {
            "message": f"chore: sync {filename} [{timestamp}]",
            "content": content_b64,
            "sha": existing_sha,
            "branch": GITHUB_BRANCH,
        }
        print(f"  Updating existing {filename}...")
    elif resp.status_code == 404:
        payload = {
            "message": f"chore: add {filename} [{timestamp}]",
            "content": content_b64,
            "branch": GITHUB_BRANCH,
        }
        print(f"  Creating new {filename}...")
    else:
        print(f"ERROR: Failed to check {filename}: HTTP {resp.status_code} — {resp.text}")
        sys.exit(1)

    put_resp = requests.put(url, headers=headers, json=payload)
    if put_resp.status_code in (200, 201):
        size_mb = len(content_bytes) / (1024 * 1024)
        print(f"  {filename}: pushed ({size_mb:.1f} MB)")
        any_updated = True
    else:
        print(f"ERROR: Failed to push {filename}: HTTP {put_resp.status_code} — {put_resp.text}")
        sys.exit(1)

if any_updated:
    print(f"\nDone. Pushed to https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}")
else:
    print("Nothing to push.")
