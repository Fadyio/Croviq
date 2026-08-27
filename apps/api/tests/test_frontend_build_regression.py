"""Regression and diagnostic tests for frontend Firebase build-time validation and bundle safety."""

import os
from pathlib import Path
import shutil
import subprocess
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WEB_DIR = REPO_ROOT / "apps" / "web"


def test_frontend_build_fails_when_firebase_env_missing():
    """Regression test for production bug: web build MUST fail if Firebase build configuration is missing.

    Must NOT silently fall back or substitute baked dummy constants.
    """
    clean_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    proc = subprocess.run(
        ["pnpm", "--filter", "@croviq/web", "build"],
        cwd=REPO_ROOT,
        env=clean_env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, "Build should have failed when Firebase env vars were missing!"
    combined_output = proc.stdout + proc.stderr
    assert "Missing required Firebase frontend build configuration" in combined_output
    assert "VITE_FIREBASE_API_KEY" in combined_output
    assert "VITE_FIREBASE_AUTH_DOMAIN" in combined_output
    assert "VITE_FIREBASE_PROJECT_ID" in combined_output


def test_frontend_build_succeeds_and_bundle_diagnostic_passes():
    """Verify web build succeeds with provided Firebase configuration and bundle contains expected safe metadata."""
    test_key = "AIzaSyTestKeyForFrontendBuildValidation00"
    test_domain = "croviq-test-diag.firebaseapp.com"
    test_project = "croviq-test-diag"

    build_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "VITE_FIREBASE_API_KEY": test_key,
        "VITE_FIREBASE_AUTH_DOMAIN": test_domain,
        "VITE_FIREBASE_PROJECT_ID": test_project,
    }

    proc = subprocess.run(
        ["pnpm", "--filter", "@croviq/web", "build"],
        cwd=REPO_ROOT,
        env=build_env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"Build failed unexpectedly: {proc.stdout}\n{proc.stderr}"

    dist_dir = WEB_DIR / "dist"
    assert dist_dir.exists(), "dist directory was not created"

    # Inspect all built JS files
    bundle_js_contents: list[str] = []
    for js_file in dist_dir.rglob("*.js"):
        content = js_file.read_text(encoding="utf-8", errors="ignore")
        bundle_js_contents.append(content)

    combined_js = "\n".join(bundle_js_contents)

    # 1. Must contain the configured public project ID and auth domain
    assert test_project in combined_js, f"Expected project ID {test_project} in built bundle"
    assert test_domain in combined_js, f"Expected auth domain {test_domain} in built bundle"

    # 2. Must NOT contain dummy fallback constants or template placeholders
    assert "AIzaSyDummyClientKeyForLocalTesting00" not in combined_js
    assert "your-firebase-web-api-key" not in combined_js
    assert "your-project.firebaseapp.com" not in combined_js
    assert "your-project-id" not in combined_js

    # 3. Must NOT contain private server secrets or private keys
    assert "-----BEGIN PRIVATE KEY-----" not in combined_js
    assert "roles/secretmanager" not in combined_js
