# -*- coding: utf-8 -*-
"""Tests for daily session resolution."""
from __future__ import annotations

from datetime import datetime

import pytest

from novapaw.app.runner.session import SafeJSONSession


def test_daily_session_path_uses_month_subdir(tmp_path) -> None:
    """Daily sessions should be stored under YYYY-MM/session.json."""
    session = SafeJSONSession(save_dir=str(tmp_path))
    path = session._get_save_path("2026-04-03", user_id="ignored")  # noqa: SLF001
    assert path.endswith("2026-04/2026-04-03.json")


@pytest.mark.asyncio
async def test_resolve_active_session_initial_creation(tmp_path) -> None:
    """First resolution should create today's active session."""
    session = SafeJSONSession(save_dir=str(tmp_path))
    resolution = await session.resolve_active_session(
        requested_session_id="ding:alice",
        now=datetime(2026, 4, 3, 9, 0, 0),
    )
    assert resolution.session_id == "2026-04-03"
    assert resolution.created is True
    assert resolution.rolled_over is False
    assert resolution.previous_session_id is None


@pytest.mark.asyncio
async def test_resolve_active_session_same_day_reuses_existing(tmp_path) -> None:
    """Resolving again on the same day should reuse the current session."""
    session = SafeJSONSession(save_dir=str(tmp_path))
    await session.resolve_active_session(
        requested_session_id="ding:alice",
        now=datetime(2026, 4, 3, 9, 0, 0),
    )
    resolution = await session.resolve_active_session(
        requested_session_id="console:bob",
        now=datetime(2026, 4, 3, 12, 0, 0),
    )
    assert resolution.session_id == "2026-04-03"
    assert resolution.created is False
    assert resolution.rolled_over is False


@pytest.mark.asyncio
async def test_resolve_active_session_rolls_over_next_day(tmp_path) -> None:
    """Cross-day access should roll over to a new active session."""
    session = SafeJSONSession(save_dir=str(tmp_path))
    await session.resolve_active_session(
        requested_session_id="ding:alice",
        now=datetime(2026, 4, 3, 22, 0, 0),
    )
    resolution = await session.resolve_active_session(
        requested_session_id="console:bob",
        now=datetime(2026, 4, 4, 9, 0, 0),
    )
    assert resolution.session_id == "2026-04-04"
    assert resolution.created is True
    assert resolution.rolled_over is True
    assert resolution.previous_session_id == "2026-04-03"
