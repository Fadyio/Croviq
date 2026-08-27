"""Comprehensive tests for SandboxedTerminalRunner security, path boundaries, timeouts, and env allowlists."""

import os
from pathlib import Path
import tempfile
import pytest

from croviq_agents.terminal import SandboxedTerminalRunner, TerminalExecutionError


def test_terminal_runner_executes_allowed_command():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(production_id="prod_test_123", base_dir=Path(tmpdir))
        result = runner.run("echo 'hello from croviq'")
        assert result.exit_code == 0
        assert "hello from croviq" in result.stdout
        assert result.timed_out is False


def test_terminal_runner_blocks_network_binaries():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(production_id="prod_test_123", base_dir=Path(tmpdir))
        for blocked in ["curl https://evil.example.com", "wget https://evil.example.com", "nc -zv 127.0.0.1 80"]:
            with pytest.raises(TerminalExecutionError, match="not in allowlisted binaries"):
                runner.run(blocked)


def test_terminal_runner_blocks_arbitrary_interpreters_for_metadata_safety():
    """Verify python, python3, bash, sh are blocked from terminal to prevent metadata token exfiltration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(production_id="prod_test_123", base_dir=Path(tmpdir))
        for interpreter in ["python", "python3", "bash", "sh", "node", "perl", "ruby"]:
            with pytest.raises(TerminalExecutionError, match="not in allowlisted binaries"):
                runner.run(f"{interpreter} -c 'print(1)'")


def test_terminal_runner_blocks_path_traversal():
    """Verify ../ traversal outside production workspace is rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(production_id="prod_test_123", base_dir=Path(tmpdir))
        with pytest.raises(TerminalExecutionError, match="Path traversal outside workspace is forbidden"):
            runner.run("cat ../../secrets.txt")


def test_terminal_runner_blocks_absolute_paths_outside_workspace():
    """Verify absolute paths outside production workspace are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(production_id="prod_test_123", base_dir=Path(tmpdir))
        with pytest.raises(TerminalExecutionError, match="Absolute path outside workspace is forbidden"):
            runner.run("cat /etc/passwd")


def test_terminal_runner_blocks_symlink_escape():
    """Verify symlinks pointing outside workspace cannot be accessed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("secret_data")

        runner = SandboxedTerminalRunner(production_id="prod_test_123", base_dir=tmp_path)
        symlink_file = runner.workspace_dir / "escape_symlink.txt"
        symlink_file.symlink_to(outside_file)

        with pytest.raises(TerminalExecutionError, match="Symlink target outside workspace is forbidden"):
            runner.run("cat escape_symlink.txt")


def test_terminal_runner_blocks_shell_operators():
    """Verify chained command operators and injections are blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(production_id="prod_test_123", base_dir=Path(tmpdir))
        for dangerous in [
            "echo hello ; rm -rf /",
            "echo hello && echo evil",
            "echo hello | grep evil",
            "echo `whoami`",
            "echo $SECRET",
        ]:
            with pytest.raises(TerminalExecutionError, match="Forbidden shell operator"):
                runner.run(dangerous)


def test_terminal_runner_sanitizes_environment():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(production_id="prod_test_123", base_dir=Path(tmpdir))
        env = runner._sanitize_env()

        # Set fake secrets in the current process
        os.environ["CROVIQ_SECRET_KEY"] = "super_secret_token_123"
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/key.json"
        os.environ["FIREBASE_ADMIN_CERT"] = "secret_cert"
        try:
            sanitized = runner._sanitize_env()
            assert "CROVIQ_SECRET_KEY" not in sanitized
            assert "GOOGLE_APPLICATION_CREDENTIALS" not in sanitized
            assert "FIREBASE_ADMIN_CERT" not in sanitized
            assert sanitized["TMPDIR"] == str(runner.workspace_dir)
            assert sanitized["HOME"] == str(runner.workspace_dir)
        finally:
            os.environ.pop("CROVIQ_SECRET_KEY", None)
            os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
            os.environ.pop("FIREBASE_ADMIN_CERT", None)


def test_terminal_runner_enforces_timeout():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(
            production_id="prod_test_123",
            base_dir=Path(tmpdir),
            timeout_seconds=1,
        )
        # Use a long-running ffmpeg lavfi generator as allowed binary
        cmd = "ffmpeg -re -f lavfi -i testsrc=duration=10:rate=1 -f null -"
        result = runner.run(cmd)
        assert result.timed_out is True
        assert result.exit_code != 0


def test_terminal_runner_caps_output_size():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(
            production_id="prod_test_123",
            base_dir=Path(tmpdir),
            max_output_bytes=100,
        )
        # Create a 1000-character test file in workspace and cat it
        test_file = runner.workspace_dir / "large.txt"
        test_file.write_text("A" * 1000)
        result = runner.run("cat large.txt")
        assert result.exit_code == 0
        assert len(result.stdout) <= 150
        assert result.truncated is True
