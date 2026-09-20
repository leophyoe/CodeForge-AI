"""Tests for the codeforge CLI."""

from __future__ import annotations

from click.testing import CliRunner

from codeforge.cli import main


class TestCLI:
    def test_main_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "CodeForge AI" in result.output

    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_hardware_command(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["hardware"])
        assert result.exit_code == 0
        assert "Hardware Detection" in result.output

    def test_doctor_command(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0
        assert "Diagnostics" in result.output

    def test_search_not_implemented(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["search", "test"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_chat_not_implemented(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["chat", "hello"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output
