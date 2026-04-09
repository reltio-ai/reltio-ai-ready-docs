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

# Authenticated remote URL
auth_url = GITHUB_REPO.replace("https://", f"https://x-access-token:{GITHUB_TOKEN}@")

def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR running {' '.join(cmd)}:\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

tmpdir = tempfile.mkdtemp()
try:
    # Try cloning with branch; if repo is empty/new, clone without --branch
    print(f"Cloning {GITHUB_REPO}...")
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", GITHUB_BRANCH, auth_url, tmpdir],
        capture_output=True, text=True
    )
    empty_repo = result.returncode != 0

    if empty_repo:
        print("  Repo appears empty — initializing fresh clone...")
        shutil.rmtree(tmpdir, ignore_errors=True)
        os.makedirs(tmpdir)
        run(["git", "init"], cwd=tmpdir)
        run(["git", "remote", "add", "origin", auth_url], cwd=tmpdir)
        run(["git", "checkout", "-b", GITHUB_BRANCH], cwd=tmpdir)

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

    if not changed and not empty_repo:
        print("No changes detected. Nothing to push to GitHub.")
        sys.exit(0)

    run(["git", "add"] + FILES, cwd=tmpdir)

    import datetime
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    run(["git", "commit", "-m", f"chore: weekly docs sync [{timestamp}]"], cwd=tmpdir)

    push_cmd = ["git", "push", "origin", GITHUB_BRANCH]
    if empty_repo:
        push_cmd.append("--set-upstream")
    run(push_cmd, cwd=tmpdir)
    print("Successfully pushed to GitHub.")

finally:
    shutil.rmtree(tmpdir, ignore_errors=True)
