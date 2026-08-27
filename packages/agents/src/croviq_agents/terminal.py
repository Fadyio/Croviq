"""Controlled, sandboxed local terminal execution runner for agent tools."""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shlex
import subprocess
import time

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
    duration_ms: float = 0.0
    timed_out: bool = False
    truncated: bool = False


# Security allowlists: Only deterministic media inspection and workspace utilities.
# Arbitrary language interpreters (python, python3, sh, bash, node, perl, ruby)
# and network utilities (curl, wget, nc, socat, ssh) are STRICTLY FORBIDDEN
# to prevent Cloud Run metadata server credential exfiltration and arbitrary execution.
ALLOWED_BINARIES: set[str] = {
    "ffmpeg",
    "ffprobe",
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

# Environment variables permitted in the sandbox subprocess.
# All cloud credentials, secrets, tokens, and sensitive paths are stripped.
ALLOWED_ENV_VARS: set[str] = {
    "PATH",
    "LC_ALL",
    "LANG",
}

# Dangerous shell operators forbidden in arguments
FORBIDDEN_OPERATORS: tuple[str, ...] = (
    ";",
    "&",
    "|",
    "`",
    "$",
    ">",
    "<",
    "\n",
    "\r",
)


class SandboxedTerminalRunner:
    """Executes safe, sandboxed commands strictly bounded within an isolated production workspace."""

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
            (base_dir / production_id).resolve()
            if base_dir
            else Path(f"/tmp/croviq-agent/{production_id}").resolve()
        )
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_env(self) -> dict[str, str]:
        """Create sanitized environment containing only approved non-sensitive variables."""
        sanitized: dict[str, str] = {}
        for k, v in os.environ.items():
            if k in ALLOWED_ENV_VARS:
                # Do not pass through if key or value looks like a secret path/credential
                lower_k = k.lower()
                if any(sec in lower_k for sec in ("secret", "token", "cred", "auth", "key", "pass")):
                    continue
                sanitized[k] = v

        # Enforce isolated directory variables bounded strictly to workspace
        sanitized["TMPDIR"] = str(self.workspace_dir)
        sanitized["HOME"] = str(self.workspace_dir)

        # Ensure minimal PATH containing standard system binaries
        if "PATH" not in sanitized:
            sanitized["PATH"] = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"

        return sanitized

    def _validate_path_safety(self, token: str) -> None:
        """Verify an argument token cannot escape the workspace directory via traversal or absolute path."""
        # Skip pure CLI options (e.g. -v, --version, -show_entries)
        if token.startswith("-") and not (token.startswith("./") or token.startswith("../")):
            return

        # Check explicit path traversal syntax
        if ".." in token:
            resolved = (self.workspace_dir / token).resolve()
            try:
                resolved.relative_to(self.workspace_dir)
            except ValueError:
                raise TerminalExecutionError(
                    f"Path traversal outside workspace is forbidden: '{token}'"
                )

        # Check absolute paths
        if token.startswith("/"):
            resolved = Path(token).resolve()
            try:
                resolved.relative_to(self.workspace_dir)
            except ValueError:
                raise TerminalExecutionError(
                    f"Absolute path outside workspace is forbidden: '{token}'"
                )

        # Check relative files/symlinks in workspace
        candidate = self.workspace_dir / token
        if candidate.is_symlink() or candidate.exists():
            resolved = candidate.resolve()
            try:
                resolved.relative_to(self.workspace_dir)
            except ValueError:
                raise TerminalExecutionError(
                    f"Symlink target outside workspace is forbidden: '{token}'"
                )

    def _validate_command(self, raw_command: str) -> list[str]:
        """Parse and strictly validate command binary and argument boundaries."""
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

        # Check for dangerous shell operators and path escapes in arguments
        for token in tokens[1:]:
            for op in FORBIDDEN_OPERATORS:
                if op in token:
                    raise TerminalExecutionError(
                        f"Forbidden shell operator '{op}' detected in command argument: '{token}'"
                    )

            # Validate path safety for every argument token
            self._validate_path_safety(token)

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
            stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "")
            stderr = f"Command timed out after {self.timeout_seconds}s"
        except Exception as exc:
            exit_code = -1
            stderr = f"Execution failed: {type(exc).__name__}: {exc}"

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

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
