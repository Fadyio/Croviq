#!/usr/bin/env python3
"""Croviq Security Audit: automated, reproducible repository security checks.

Performs:
1. Current tracked tree secret scan
2. Git commit history secret scan
3. Git-tracked .env file protection verification
4. Frontend build artifact secret scan
5. Agent terminal security invariants
"""

import os
from pathlib import Path
import re
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent

# High-confidence secret patterns (excluding test/dummy keys like AIzaSyDummyClientKey...)
SECRET_PATTERNS = [
    (r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "Private Key"),
    (r"(?i)\bghp_[A-Za-z0-9_]{36,}\b", "GitHub Personal Access Token"),
    (r"(?i)\bgithub_pat_[A-Za-z0-9_]{82}\b", "GitHub Fine-Grained PAT"),
    (r"(?i)\bAKIA[0-9A-Z]{16}\b", "AWS Access Key"),
    (r"(?i)\bsk-[A-Za-z0-9]{32,}\b", "OpenAI / Anthropic Secret Key"),
    (r"(?i)\bgsk_[A-Za-z0-9]{32,}\b", "Groq Secret Key"),
    (r'(?i)"private_key_id"\s*:\s*"[0-9a-f]{40}"', "Google Service Account Private Key ID"),
    (r'(?i)"private_key"\s*:\s*"-----BEGIN PRIVATE KEY-----', "Google Service Account JSON Private Key"),
]

# Patterns for fake / dummy testing keys to ignore
IGNORE_SUBSTRINGS = [
    "AIzaSyDummyClientKeyForLocalTesting00",
    "mock_v4_signature",
    "mock_v4_signed_read",
    "test_sha_123",
    "testsrc=",
    "-----BEGIN PRIVATE KEY-----...",
]


def check_tracked_files_for_secrets() -> tuple[bool, list[str]]:
    """Scan all git-tracked files for secret patterns."""
    findings: list[str] = []
    try:
        tracked_files = subprocess.check_output(
            ["git", "ls-files"], cwd=REPO_ROOT, text=True
        ).splitlines()
    except Exception as e:
        return False, [f"Failed to list tracked files: {e}"]

    for rel_path in tracked_files:
        full_path = REPO_ROOT / rel_path
        if not full_path.is_file():
            continue
        # Skip binary files or lockfiles
        if rel_path.endswith((".png", ".webp", ".jpg", ".ico", ".lock", "pnpm-lock.yaml", "uv.lock")):
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for pattern, secret_type in SECRET_PATTERNS:
            matches = re.finditer(pattern, content)
            for m in matches:
                matched_text = m.group(0)
                line_no = content[: m.start()].count("\n") + 1
                line_text = content.splitlines()[line_no - 1] if line_no <= len(content.splitlines()) else matched_text
                if any(ign in line_text for ign in IGNORE_SUBSTRINGS) or any(ign in matched_text for ign in IGNORE_SUBSTRINGS):
                    continue
                findings.append(f"{rel_path}:{line_no} -> {secret_type} match")

    return len(findings) == 0, findings


def check_git_history_for_secrets() -> tuple[bool, list[str]]:
    """Scan git commit history for probable real secrets."""
    findings: list[str] = []
    try:
        # Check last 50 commits diffs for private keys or live API keys
        diff_output = subprocess.check_output(
            ["git", "log", "-p", "-n", "50"],
            cwd=REPO_ROOT,
            text=True,
            errors="ignore",
        )
    except Exception as e:
        return False, [f"Failed to inspect git history: {e}"]

    for pattern, secret_type in SECRET_PATTERNS:
        matches = re.finditer(pattern, diff_output)
        for m in matches:
            matched_text = m.group(0)
            if any(ign in matched_text for ign in IGNORE_SUBSTRINGS):
                continue
            findings.append(f"Historical commit contains: {secret_type}")

    return len(findings) == 0, findings


def check_env_file_tracking() -> tuple[bool, list[str]]:
    """Verify git ls-files contains no prohibited real .env files."""
    findings: list[str] = []
    try:
        tracked_files = subprocess.check_output(
            ["git", "ls-files"], cwd=REPO_ROOT, text=True
        ).splitlines()
    except Exception as e:
        return False, [f"Failed to list tracked files: {e}"]

    for f in tracked_files:
        name = Path(f).name
        if name.startswith(".env") and not name.endswith(".example"):
            findings.append(f"Prohibited tracked env file: {f}")

    return len(findings) == 0, findings


def check_frontend_build_bundle() -> tuple[bool, list[str]]:
    """Check frontend dist/ assets for server secrets."""
    findings: list[str] = []
    dist_dir = REPO_ROOT / "apps" / "web" / "dist"
    if not dist_dir.exists():
        return True, ["(apps/web/dist not built yet - skipped bundle scan)"]

    for js_file in dist_dir.rglob("*.js"):
        try:
            content = js_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern, secret_type in SECRET_PATTERNS:
            matches = re.finditer(pattern, content)
            for m in matches:
                matched_text = m.group(0)
                if any(ign in matched_text for ign in IGNORE_SUBSTRINGS):
                    continue
                findings.append(f"Frontend bundle {js_file.name} contains {secret_type}")

    return len(findings) == 0, findings


def check_terminal_sandbox_invariants() -> tuple[bool, list[str]]:
    """Verify terminal sandbox allowlist does not contain network utilities or arbitrary interpreters."""
    findings: list[str] = []
    terminal_py = REPO_ROOT / "packages" / "agents" / "src" / "croviq_agents" / "terminal.py"
    if not terminal_py.exists():
        return False, ["packages/agents/src/croviq_agents/terminal.py not found"]

    content = terminal_py.read_text(encoding="utf-8")
    # Check that python/python3/bash/sh/curl/wget are not in ALLOWED_BINARIES
    match = re.search(r"ALLOWED_BINARIES:\s*set\[str\]\s*=\s*{(.*?)}", content, re.DOTALL)
    if not match:
        return False, ["ALLOWED_BINARIES definition not found in terminal.py"]

    allowlist_str = match.group(1)
    forbidden = ["python", "python3", "bash", "sh", "curl", "wget", "nc", "socat", "node", "perl", "ruby"]
    for f in forbidden:
        if f'"{f}"' in allowlist_str or f"'{f}'" in allowlist_str:
            findings.append(f"Forbidden binary '{f}' found in terminal ALLOWED_BINARIES!")

    return len(findings) == 0, findings


def main() -> int:
    print("==================================================")
    print(" Croviq Security Audit")
    print("==================================================")

    all_passed = True

    # 1. Tracked Files Secret Scan
    ok, details = check_tracked_files_for_secrets()
    print(f"1. Current Tree Secret Scan: {'✓ PASS' if ok else '✗ FAIL'}")
    if not ok:
        all_passed = False
        for d in details:
            print(f"   -> {d}")

    # 2. Git History Secret Scan
    ok, details = check_git_history_for_secrets()
    print(f"2. Git History Secret Scan:  {'✓ PASS' if ok else '✗ FAIL'}")
    if not ok:
        all_passed = False
        for d in details:
            print(f"   -> {d}")

    # 3. Tracked Env Files
    ok, details = check_env_file_tracking()
    print(f"3. Tracked Env Files:        {'✓ PASS' if ok else '✗ FAIL'}")
    if not ok:
        all_passed = False
        for d in details:
            print(f"   -> {d}")

    # 4. Frontend Build Output
    ok, details = check_frontend_build_bundle()
    print(f"4. Frontend Bundle Secrets:  {'✓ PASS' if ok else '✗ FAIL'}")
    if not ok:
        all_passed = False
        for d in details:
            print(f"   -> {d}")

    # 5. Terminal Sandbox Invariants
    ok, details = check_terminal_sandbox_invariants()
    print(f"5. Agent Terminal Security:  {'✓ PASS' if ok else '✗ FAIL'}")
    if not ok:
        all_passed = False
        for d in details:
            print(f"   -> {d}")

    print("==================================================")
    if all_passed:
        print("✓ All automated security checks passed.")
        return 0
    else:
        print("✗ Security audit detected failures.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
