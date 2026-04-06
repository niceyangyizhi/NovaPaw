# -*- coding: utf-8 -*-
"""Tests for daily memory artifact helpers."""
from __future__ import annotations

import json

import pytest

from novapaw.app.memory.daily_memory import (
    build_daily_memory_guidance,
    load_recent_daily_memories,
    save_daily_memory_artifact,
)


@pytest.mark.asyncio
async def test_save_and_load_recent_daily_memories(tmp_path, monkeypatch) -> None:
    """Daily memory artifacts should persist independently and load newest first."""
    monkeypatch.setattr(
        "novapaw.app.memory.daily_memory.MEMORY_DAILY_DIR",
        tmp_path / "daily",
    )

    await save_daily_memory_artifact(
        session_id="2026-04-04",
        summary="整理了 TASK-001 和 heartbeat 的关键结论。",
        content="整理了 TASK-001 和 heartbeat 的关键结论。",
        generated_at="2026-04-04T23:00:00",
        source_message_count=12,
    )
    await save_daily_memory_artifact(
        session_id="2026-04-05",
        summary="完成 session 改造，并修复 UI 会话标题。",
        content="完成 session 改造，并修复 UI 会话标题。",
        generated_at="2026-04-05T23:00:00",
        source_message_count=20,
    )

    memories = await load_recent_daily_memories(limit=3)
    assert [memory["date"] for memory in memories] == [
        "2026-04-05",
        "2026-04-04",
    ]


def test_build_daily_memory_guidance_zh() -> None:
    """Chinese guidance should include date-tagged summaries."""
    prompt = build_daily_memory_guidance(
        [
            {
                "date": "2026-04-05",
                "summary": "完成 session 改造，并修复 UI 会话标题。",
            },
            {
                "date": "2026-04-04",
                "summary": "整理了 heartbeat 与主动消息发送的关键判断。",
            },
        ],
        language="zh",
    )
    assert "最近日记忆" in prompt
    assert "- 2026-04-05:" in prompt
    assert "session 改造" in prompt
