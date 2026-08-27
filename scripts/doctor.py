#!/usr/bin/env python3
"""Croviq Environment Doctor: verify required local development tools and versions."""

import shutil
import subprocess
import sys
from typing import NamedTuple


class CheckResult(NamedTuple):
    tool: str
    required: str
    found: str
    ok: bool
    details: str = ""


def check_python() -> CheckResult:
    v = sys.version_info
    found = f"{v.major}.{v.minor}.{v.micro}"
    ok = (v.major, v.minor) >= (3, 12)
    return CheckResult(
        tool="python",
        required=">= 3.12",
        found=found,
        ok=ok,
        details="" if ok else "Python 3.12 or newer is required.",
    )


def check_cmd(cmd: list[str], tool_name: str, required: str, parser=None) -> CheckResult:
    exe = shutil.which(cmd[0])
    if not exe:
        return CheckResult(
            tool=tool_name,
            required=required,
            found="NOT FOUND",
            ok=False,
            details=f"Executable '{cmd[0]}' not found in PATH.",
        )
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=5).strip()
        first_line = out.splitlines()[0] if out else "found"
        found = parser(first_line) if parser else first_line
        return CheckResult(tool=tool_name, required=required, found=found, ok=True)
    except Exception as e:
        return CheckResult(
            tool=tool_name,
            required=required,
            found="ERROR",
            ok=False,
            details=str(e),
        )


def main() -> int:
    print("==================================================")
    print(" Croviq Local Development Environment Doctor")
    print("==================================================")

    results: list[CheckResult] = []

    # 1. Python
    results.append(check_python())

    # 2. uv
    results.append(
        check_cmd(["uv", "--version"], "uv", ">= 0.1.0", lambda s: s.split()[1] if len(s.split()) > 1 else s)
    )

    # 3. Node.js
    def parse_node(s: str) -> str:
        s = s.lstrip("v")
        return s

    results.append(check_cmd(["node", "--version"], "node", ">= 20.0.0", parse_node))

    # 4. pnpm
    results.append(check_cmd(["pnpm", "--version"], "pnpm", ">= 9.0.0", lambda s: s.strip()))

    # 5. FFmpeg
    results.append(
        check_cmd(["ffmpeg", "-version"], "ffmpeg", "available", lambda s: s.split()[2] if len(s.split()) > 2 else s)
    )

    # 6. FFprobe
    results.append(
        check_cmd(["ffprobe", "-version"], "ffprobe", "available", lambda s: s.split()[2] if len(s.split()) > 2 else s)
    )

    # 7. Terraform
    results.append(
        check_cmd(["terraform", "--version"], "terraform", ">= 1.5.0, < 2.0.0", lambda s: s.split()[1] if len(s.split()) > 1 else s)
    )

    all_ok = True
    print(f"{'TOOL':<14} | {'REQUIRED':<18} | {'FOUND':<18} | {'STATUS'}")
    print("-" * 65)
    for r in results:
        status = "✓ OK" if r.ok else "✗ MISSING / INVALID"
        print(f"{r.tool:<14} | {r.required:<18} | {r.found:<18} | {status}")
        if not r.ok:
            all_ok = False
            if r.details:
                print(f"  -> Reason: {r.details}")

    print("==================================================")
    if all_ok:
        print("✓ All required local development tools are installed and operational.")
        return 0
    else:
        print("✗ One or more required tools are missing or invalid.")
        print("  Please install missing dependencies and re-run 'make doctor'.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
