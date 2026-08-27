"""Controlled, sandboxed local terminal execution runner for agent tools."""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shlex
import subprocess
import time
from typing import Any, Sequence

logger = logging.getLogger(__name__)


class TerminalExecutionError(Exception):
    """Raised when command validation, security policy, or sandbox setup fails."""


@dataclass(frozen=True)
class TerminalCommandResult:
    """Result of sandboxed terminal execution."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    truncated: bool = False


# Security allowlists
ALLOWED_BINARIES: set[str] = {
    "ffmpeg",
    "ffprobe",
    "python",
    "python3",
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "grep",
    "file",
    "stat",
    "echo",
}

ALLOWED_ENV_VARS: set[str] = {
    "PATH",
    "HOME",
    "TMPDIR",
    "LC_ALL",
    "LANG",
    "PYTHONPATH",
}


class SandboxedTerminalRunner:
    """Executes safe, sandboxed commands in an isolated production workspace."""

    def __init__(
        self,
        production_id: str,
        base_dir: Path | None = None,
        timeout_seconds: int = 15,
        max_output_bytes: int = 65536,
    ) -> None:
        self.production_id = production_id
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.workspace_dir = (
            (base_dir / production_id)
            if base_dir
            else Path(f"/tmp/croviq-agent/{production_id}")
        )
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_env(self) -> dict[str, str]:
        """Create sanitized environment containing only approved non-sensitive variables."""
        sanitized: dict[str, str] = {
            "TMPDIR": str(self.workspace_dir),
        }
        for k, v in os.environ.items():
            if k in ALLOWED_ENV_VARS:
                # Do not pass through if it looks like a secret path/credential
                if "secret" in k.lower() or "token" in k.lower() or "cred" in k.lower():
                    continue
                sanitized[k] = v
        # Ensure minimal PATH
        if "PATH" not in sanitized:
            sanitized["PATH"] = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"
        return sanitized

    def _validate_command(self, raw_command: str) -> list[str]:
        """Parse and strictly validate command binary against allowlist."""
        if not raw_command or not raw_command.strip():
            raise TerminalExecutionError("Command must be non-empty")

        try:
            tokens = shlex.split(raw_command.strip())
        except ValueError as exc:
            raise TerminalExecutionError(f"Failed to parse command line: {exc}") from exc

        if not tokens:
            raise TerminalExecutionError("Parsed command resulted in empty tokens")

        binary = Path(tokens[0]).name
        if binary not in ALLOWED_BINARIES:
            raise TerminalExecutionError(
                f"Binary '{binary}' is not in allowlisted binaries: {sorted(ALLOWED_BINARIES)}"
            )

        # Check for dangerous patterns
        for token in tokens[1:]:
            if token.startswith(";") or token.startswith("&") or token.startswith("|"):
                raise TerminalExecutionError("Chained command operators are forbidden in arguments")

        return tokens

    def run(self, command: str) -> TerminalCommandResult:
        """Run command within sandboxed workspace with strict timeout and output bounds."""
        tokens = self._validate_command(command)
        env = self._sanitize_env()

        start_time = time.perf_counter()
        timed_out = False
        exit_code = -1
        stdout = ""
        stderr = ""
        truncated = False

        try:
            process = subprocess.run(
                tokens,
                cwd=str(self.workspace_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            exit_code = process.returncode
            stdout = process.stdout
            stderr = process.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = -1
            stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = f"Command timed out after {self.timeout_seconds}s"
        except Exception as exc:
            exit_code = -1
            stderr = f"Execution failed: {type(exc).__name__}: {exc}"

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Output truncation
        if len(stdout) > self.max_output_bytes:
            stdout = stdout[: self.max_output_bytes] + "\n...[OUTPUT TRUNCATED]"
            truncated = True
        if len(stderr) > self.max_output_bytes:
            stderr = stderr[: self.max_output_bytes] + "\n...[OUTPUT TRUNCATED]"
            truncated = True

        return TerminalCommandResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
            truncated=truncated,
        )
