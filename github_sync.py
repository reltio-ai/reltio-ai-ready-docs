#!/usr/bin/env python3
"""
Push docs.md and index.md to the public GitHub repo.
Only these two files are synced — no pipeline scripts or internal tooling.

Requires:
  GITHUB_TOKEN  - GitHub Personal Access Token (repo write scope)
  GITHUB_EMAIL  - (optional) commit author email, defaults to pipelines@reltio.com
"""

import os
import sys
import shutil
import subprocess
import tempfile
import hashlib
import datetime

GITHUB_REPO = "https://github.com/reltio-ai/reltio-ai-ready-docs.git"
GITHUB_BRANCH = "main"
FILES = ["docs.md", "index.md"]

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_EMAIL = os.environ.get("GITHUB_EMAIL", "pipelines@reltio.com")

if not GITHUB_TOKEN:
    print("ERROR: GITHUB_TOKEN environment variable required")
    sys.exit(1)

for f in FILES:
    if not os.path.exists(f):
        print(f"ERROR: {f} not found in current directory — run after sync.py")
        sys.exit(1)

# Authenticated remote URL (Bitbucket masks this value in logs automatically)
auth_url = GITHUB_REPO.replace("https://", f"https://x-access-token:{GITHUB_TOKEN}@")

def run(cmd, cwd=None):
    # Redact token from any printed error output
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.replace(GITHUB_TOKEN, "***")
        safe_cmd = [c.replace(GITHUB_TOKEN, "***") for c in cmd]
        print(f"ERROR running {' '.join(safe_cmd)}:\n{stderr}")
        sys.exit(1)
    return result.stdout.strip()

tmpdir = tempfile.mkdtemp()
try:
    print(f"Cloning {GITHUB_REPO}...")

    # Clone without --branch so it works even on empty repos
    clone_result = subprocess.run(
        ["git", "clone", "--depth", "1", auth_url, tmpdir],
        capture_output=True, text=True
    )

    if clone_result.returncode != 0:
        # Completely empty repo (no commits at all)
        print("  Empty repo detected — initializing from scratch...")
        shutil.rmtree(tmpdir, ignore_errors=True)
        os.makedirs(tmpdir)
        run(["git", "init", "--initial-branch", GITHUB_BRANCH], cwd=tmpdir)
        run(["git", "remote", "add", "origin", auth_url], cwd=tmpdir)
        is_empty = True
    else:
        # Cloned OK — make sure we're on the right branch
        current = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=tmpdir, capture_output=True, text=True
        ).stdout.strip()
        if current != GITHUB_BRANCH:
            run(["git", "checkout", "-b", GITHUB_BRANCH], cwd=tmpdir)
        is_empty = False

    run(["git", "config", "user.email", GITHUB_EMAIL], cwd=tmpdir)
    run(["git", "config", "user.name", "Bitbucket Pipelines"], cwd=tmpdir)

    changed = False
    for filename in FILES:
        src = os.path.join(os.getcwd(), filename)
        dst = os.path.join(tmpdir, filename)

        with open(src, "rb") as f:
            new_hash = hashlib.sha256(f.read()).hexdigest()

        if os.path.exists(dst):
            with open(dst, "rb") as f:
                old_hash = hashlib.sha256(f.read()).hexdigest()
            if old_hash == new_hash:
                print(f"  {filename}: unchanged, skipping")
                continue

        shutil.copy2(src, dst)
        size_mb = os.path.getsize(dst) / (1024 * 1024)
        print(f"  {filename}: updated ({size_mb:.1f} MB)")
        changed = True

    if not changed and not is_empty:
        print("No changes detected. Nothing to push to GitHub.")
        sys.exit(0)

    run(["git", "add"] + FILES, cwd=tmpdir)

    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    run(["git", "commit", "-m", f"chore: weekly docs sync [{timestamp}]"], cwd=tmpdir)
    run(["git", "push", "--set-upstream", "origin", GITHUB_BRANCH], cwd=tmpdir)
    print("Successfully pushed to GitHub.")

finally:
    shutil.rmtree(tmpdir, ignore_errors=True)
