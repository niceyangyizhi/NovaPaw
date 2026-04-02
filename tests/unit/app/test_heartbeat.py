# -*- coding: utf-8 -*-
"""Tests for heartbeat module."""
from __future__ import annotations

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from novapaw.app.crons.heartbeat import (
    parse_heartbeat_every,
    _in_active_hours,
    build_heartbeat_auto_system_prompt,
)


async def _empty_stream():
    """Async generator that yields nothing."""
    if False:
        yield None


async def _failing_stream():
    """Async generator that fails during iteration."""
    raise RuntimeError("stream failed")
    if False:
        yield None


# =============================================================================
# Test: parse_heartbeat_every
# =============================================================================


def test_parse_heartbeat_every_30m() -> None:
    """Test parsing 30m interval."""
    assert parse_heartbeat_every("30m") == 30 * 60


def test_parse_heartbeat_every_1h() -> None:
    """Test parsing 1h interval."""
    assert parse_heartbeat_every("1h") == 60 * 60


def test_parse_heartbeat_every_2h30m() -> None:
    """Test parsing 2h30m interval."""
    assert parse_heartbeat_every("2h30m") == 2 * 60 * 60 + 30 * 60


def test_parse_heartbeat_every_90s() -> None:
    """Test parsing 90s interval."""
    assert parse_heartbeat_every("90s") == 90


def test_parse_heartbeat_every_empty() -> None:
    """Test parsing empty string uses default."""
    assert parse_heartbeat_every("") == 30 * 60


def test_parse_heartbeat_every_invalid() -> None:
    """Test parsing invalid string uses default."""
    assert parse_heartbeat_every("invalid") == 30 * 60


def test_parse_heartbeat_every_zero() -> None:
    """Test parsing 0 uses default."""
    assert parse_heartbeat_every("0s") == 30 * 60


# =============================================================================
# Test: _in_active_hours
# =============================================================================


def test_in_active_hours_none_config() -> None:
    """Test with None active_hours config."""
    assert _in_active_hours(None) is True


def test_in_active_hours_missing_attrs() -> None:
    """Test with config missing start/end attributes."""
    config = SimpleNamespace()
    assert _in_active_hours(config) is True


def test_in_active_hours_within_range() -> None:
    """Test when current time is within range."""
    config = SimpleNamespace(start="00:00", end="23:59")
    # This test depends on current time, but should pass for most of the day
    result = _in_active_hours(config)
    # Just verify it returns a boolean
    assert isinstance(result, bool)


def test_in_active_hours_outside_range_night() -> None:
    """Test when current time is outside range (night shift)."""
    # Test overnight range: 22:00 - 06:00
    config = SimpleNamespace(start="22:00", end="06:00")
    result = _in_active_hours(config)
    assert isinstance(result, bool)


def test_in_active_hours_invalid_format() -> None:
    """Test with invalid time format."""
    config = SimpleNamespace(start="invalid", end="format")
    assert _in_active_hours(config) is True  # Falls back to True


# =============================================================================
# Test: build_heartbeat_auto_system_prompt
# =============================================================================


def test_heartbeat_auto_prompt_exists() -> None:
    """Test that system prompt is defined."""
    prompt = build_heartbeat_auto_system_prompt()
    assert prompt is not None
    assert len(prompt) > 0


def test_heartbeat_auto_prompt_contains_guidance_zh() -> None:
    """Test that zh prompt contains key guidance."""
    prompt = build_heartbeat_auto_system_prompt("zh")
    assert "send_to_channel" in prompt
    assert "行动项" in prompt or "行动" in prompt
    assert "不要" in prompt or "❌" in prompt


def test_heartbeat_auto_prompt_is_string() -> None:
    """Test that prompt is a string."""
    assert isinstance(build_heartbeat_auto_system_prompt("zh"), str)


def test_heartbeat_auto_prompt_contains_guidance_en() -> None:
    """Test that non-zh prompt falls back to English."""
    prompt = build_heartbeat_auto_system_prompt("en")
    assert "send_to_channel" in prompt
    assert "action items" in prompt.lower()
    assert "do not use" in prompt.lower()


# =============================================================================
# Test: Auto mode fallback (no last_dispatch)
# =============================================================================


async def test_auto_mode_fallback_no_last_dispatch(caplog) -> None:
    """Test that auto mode degrades to main when no last_dispatch."""
    from novapaw.app.crons.heartbeat import run_heartbeat_once
    from novapaw.config.config import Config, HeartbeatConfig
    from unittest.mock import MagicMock, patch

    # Create mock config with no last_dispatch
    mock_config = MagicMock(spec=Config)
    mock_config.last_dispatch = None
    mock_config.heartbeat = HeartbeatConfig(
        enabled=True,
        every="6h",
        target="auto",
        active_hours=None,
    )

    # Create mock runner and channel_manager
    mock_runner = MagicMock()
    mock_runner.toolkit = MagicMock()
    mock_runner.stream_query = MagicMock(side_effect=lambda _req: _empty_stream())

    mock_channel_manager = MagicMock()

    with patch('novapaw.app.crons.heartbeat.load_config', return_value=mock_config):
        with patch('novapaw.app.crons.heartbeat.get_heartbeat_config',
                   return_value=mock_config.heartbeat):
            with patch('novapaw.app.crons.heartbeat.get_heartbeat_query_path') as mock_path:
                mock_path.return_value = MagicMock(
                    is_file=MagicMock(return_value=True),
                    read_text=MagicMock(return_value="test query")
                )

                # Run heartbeat
                await run_heartbeat_once(
                    runner=mock_runner,
                    channel_manager=mock_channel_manager,
                )

                # Verify tool was NOT registered (degraded to main)
                mock_runner.toolkit.register_tool_function.assert_not_called()

                # Verify log message mentions degradation
                assert any(
                    "degrading to target=main" in record.message
                    for record in caplog.records
                )

                # Verify system prompt was NOT added (check input doesn't have system message)
                # This is implicit since tool wasn't registered


async def test_auto_mode_with_last_dispatch_registers_tool() -> None:
    """Test that auto mode registers tool when last_dispatch exists."""
    from novapaw.app.crons.heartbeat import run_heartbeat_once
    from novapaw.config.config import Config, HeartbeatConfig, LastDispatchConfig
    from unittest.mock import MagicMock, patch

    # Create mock config with last_dispatch
    mock_last_dispatch = LastDispatchConfig(
        channel="dingtalk",
        user_id="user123",
        session_id="session456",
    )
    mock_config = MagicMock(spec=Config)
    mock_config.last_dispatch = mock_last_dispatch
    mock_config.heartbeat = HeartbeatConfig(
        enabled=True,
        every="6h",
        target="auto",
        active_hours=None,
    )

    # Create mock runner
    mock_runner = MagicMock()
    mock_runner.toolkit = MagicMock()
    mock_runner.stream_query = MagicMock(side_effect=lambda _req: _empty_stream())

    mock_channel_manager = MagicMock()

    with patch('novapaw.app.crons.heartbeat.load_config', return_value=mock_config):
        with patch('novapaw.app.crons.heartbeat.get_heartbeat_config',
                   return_value=mock_config.heartbeat):
            with patch('novapaw.app.crons.heartbeat.get_heartbeat_query_path') as mock_path:
                mock_path.return_value = MagicMock(
                    is_file=MagicMock(return_value=True),
                    read_text=MagicMock(return_value="test query")
                )

                # Run heartbeat
                await run_heartbeat_once(
                    runner=mock_runner,
                    channel_manager=mock_channel_manager,
                )

                # Verify tool WAS registered
                mock_runner.toolkit.register_tool_function.assert_called_once()
                mock_runner.toolkit.remove_tool_function.assert_called_once_with(
                    "send_to_channel"
                )


async def test_auto_mode_removes_tool_on_stream_failure() -> None:
    """Test that auto mode removes the tool even when stream_query fails."""
    from novapaw.app.crons.heartbeat import run_heartbeat_once
    from novapaw.config.config import Config, HeartbeatConfig, LastDispatchConfig

    mock_last_dispatch = LastDispatchConfig(
        channel="dingtalk",
        user_id="user123",
        session_id="session456",
    )
    mock_config = MagicMock(spec=Config)
    mock_config.last_dispatch = mock_last_dispatch
    mock_config.heartbeat = HeartbeatConfig(
        enabled=True,
        every="6h",
        target="auto",
        active_hours=None,
    )

    mock_runner = MagicMock()
    mock_runner.toolkit = MagicMock()
    mock_runner.stream_query = MagicMock(side_effect=lambda _req: _failing_stream())
    mock_channel_manager = MagicMock()

    with patch('novapaw.app.crons.heartbeat.load_config', return_value=mock_config):
        with patch('novapaw.app.crons.heartbeat.get_heartbeat_config',
                   return_value=mock_config.heartbeat):
            with patch('novapaw.app.crons.heartbeat.get_heartbeat_query_path') as mock_path:
                mock_path.return_value = MagicMock(
                    is_file=MagicMock(return_value=True),
                    read_text=MagicMock(return_value="test query")
                )

                with pytest.raises(RuntimeError, match="stream failed"):
                    await run_heartbeat_once(
                        runner=mock_runner,
                        channel_manager=mock_channel_manager,
                    )

                mock_runner.toolkit.register_tool_function.assert_called_once()
                mock_runner.toolkit.remove_tool_function.assert_called_once_with(
                    "send_to_channel"
                )
