"""Integration tests for the Typer CLI / composition root."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from poe2_rpc.__version__ import __version__
from poe2_rpc.cli import app

runner = CliRunner()


def test_cli_version_prints_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "once" in result.stdout
    assert "validate-config" in result.stdout


def test_cli_validate_config_exits_zero() -> None:
    """validate-config with --no-discord should exit 0 and print resolved settings."""
    result = runner.invoke(app, ["validate-config", "--no-discord"])
    assert result.exit_code == 0, result.stdout
    # Settings JSON should contain at least the discord_app_id key
    assert "discord_app_id" in result.stdout


def test_cli_validate_config_no_discord_skips_ipc() -> None:
    """With --no-discord, no PypresencePublisher (and thus no AioPresence) is instantiated."""
    with patch("poe2_rpc.cli.PypresencePublisher") as mock_publisher:
        result = runner.invoke(app, ["validate-config", "--no-discord"])
        assert result.exit_code == 0, result.stdout
        mock_publisher.assert_not_called()


def test_cli_once_runs_one_iteration() -> None:
    """`once` calls Orchestrator.run_once() exactly once via build_orchestrator factory."""
    fake_orch = MagicMock()
    with patch("poe2_rpc.cli.build_orchestrator", return_value=fake_orch):
        result = runner.invoke(app, ["once"])
    assert result.exit_code == 0, result.stdout
    fake_orch.run_once.assert_called_once()
    fake_orch.run.assert_not_called()


def test_cli_run_invokes_run_loop() -> None:
    """`run` calls Orchestrator.run() (the continuous loop)."""
    fake_orch = MagicMock()
    with patch("poe2_rpc.cli.build_orchestrator", return_value=fake_orch):
        result = runner.invoke(app, ["run"])
    assert result.exit_code == 0, result.stdout
    fake_orch.run.assert_called_once()
    fake_orch.run_once.assert_not_called()
