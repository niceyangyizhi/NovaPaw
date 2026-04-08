# -*- coding: utf-8 -*-
"""Daily memory artifact storage and prompt helpers."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import aiofiles

from ...constant import DAILY_MEMORY_RECENT_LIMIT, MEMORY_DAILY_DIR

logger = logging.getLogger(__name__)

_DATE_SESSION_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _daily_memory_path(session_id: str) -> Path:
    if not _DATE_SESSION_ID_RE.match(session_id):
        raise ValueError(
            f"daily memory artifact only supports YYYY-MM-DD session ids: {session_id}",
        )
    return MEMORY_DAILY_DIR / session_id[:7] / f"{session_id}.json"


async def save_daily_memory_artifact(
    *,
    session_id: str,
    summary: str,
    content: str,
    generated_at: str,
    source_message_count: int,
) -> Path:
    """Persist one daily memory artifact for a closed daily session."""
    artifact_path = _daily_memory_path(session_id)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": session_id,
        "session_id": session_id,
        "generated_at": generated_at,
        "summary": summary,
        "content": content,
        "source_message_count": source_message_count,
    }
    async with aiofiles.open(
        artifact_path,
        "w",
        encoding="utf-8",
        errors="surrogatepass",
    ) as f:
        await f.write(json.dumps(payload, ensure_ascii=False, indent=2))
    return artifact_path


async def load_recent_daily_memories(
    *,
    limit: int = DAILY_MEMORY_RECENT_LIMIT,
    exclude_session_id: str | None = None,
) -> list[dict]:
    """Load recent daily memory artifacts, newest first."""
    if limit <= 0 or not MEMORY_DAILY_DIR.exists():
        return []

    paths = sorted(
        MEMORY_DAILY_DIR.glob("*/*.json"),
        key=lambda p: p.name,
        reverse=True,
    )
    memories: list[dict] = []
    for path in paths:
        if len(memories) >= limit:
            break
        if exclude_session_id and path.stem == exclude_session_id:
            continue
        try:
            async with aiofiles.open(
                path,
                "r",
                encoding="utf-8",
                errors="surrogatepass",
            ) as f:
                content = await f.read()
            payload = json.loads(content) if content else {}
        except Exception:
            logger.warning("Failed to load daily memory artifact: %s", path)
            continue
        if not payload.get("summary") and not payload.get("content"):
            continue
        memories.append(payload)
    return memories


def build_daily_memory_guidance(
    memories: list[dict],
    *,
    language: str = "zh",
) -> str:
    """Build a bounded system prompt section from recent daily memories."""
    if not memories:
        return ""

    lines: list[str] = []
    for memory in memories:
        date = memory.get("date") or memory.get("session_id") or "unknown-date"
        summary = (memory.get("summary") or memory.get("content") or "").strip()
        if not summary:
            continue
        lines.append(f"- {date}: {summary}")

    if not lines:
        return ""

    if language == "zh":
        return (
            "# 最近日记忆\n\n"
            "以下是最近几天已沉淀的日记忆摘要。它们是补充背景，不是刚性指令；"
            "仅在与当前请求相关时引用，避免机械重复。\n\n"
            + "\n".join(lines)
            + "\n\n"
            "⚠️ **实体隔离规则**：引用或更新这些记忆时，"
            "必须使用完整姓名（如'刘有为'、'程姗姗'），"
            "禁止使用孤立代词（她/他/对方）。"
            "多人物记录使用 `[实体] -> [行为] -> [结果]` 格式。"
        )

    return (
        "# Recent Daily Memories\n\n"
        "These summaries describe the most recent closed daily sessions. "
        "Use them as optional background when relevant to the current request, "
        "and avoid repeating them verbatim.\n\n"
        + "\n".join(lines)
        + "\n\n"
        "⚠️ **Entity Separation Rule**: When referencing or updating these "
        "memories, always use FULL NAMES. Never use isolated pronouns "
        "(she/he/they). Use `[Entity] -> [Action] -> [Result]` format."
    )
