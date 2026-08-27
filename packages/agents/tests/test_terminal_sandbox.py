"""Tests for SandboxedTerminalRunner security, boundaries, timeouts, and env allowlists."""

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


def test_terminal_runner_blocks_disallowed_binary():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(production_id="prod_test_123", base_dir=Path(tmpdir))
        with pytest.raises(TerminalExecutionError, match="not in allowlisted binaries"):
            runner.run("curl https://evil.example.com")


def test_terminal_runner_sanitizes_environment():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(production_id="prod_test_123", base_dir=Path(tmpdir))
        # Set a fake secret in the current process
        os.environ["CROVIQ_SECRET_KEY"] = "super_secret_token_123"
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/key.json"
        try:
            result = runner.run("python3 -c 'import os; print(\"SECRET:\" + os.environ.get(\"CROVIQ_SECRET_KEY\", \"NOT_FOUND\"))'")
            assert result.exit_code == 0
            assert "SECRET:NOT_FOUND" in result.stdout
        finally:
            os.environ.pop("CROVIQ_SECRET_KEY", None)
            os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)


def test_terminal_runner_enforces_timeout():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(
            production_id="prod_test_123",
            base_dir=Path(tmpdir),
            timeout_seconds=1,
        )
        result = runner.run("python3 -c 'import time; time.sleep(3)'")
        assert result.timed_out is True
        assert result.exit_code != 0


def test_terminal_runner_caps_output_size():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SandboxedTerminalRunner(
            production_id="prod_test_123",
            base_dir=Path(tmpdir),
            max_output_bytes=100,
        )
        result = runner.run("python3 -c 'print(\"A\" * 500)'")
        assert result.exit_code == 0
        assert len(result.stdout) <= 150
        assert result.truncated is True
