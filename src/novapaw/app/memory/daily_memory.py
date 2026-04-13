# -*- coding: utf-8 -*-
"""Daily memory artifact storage and prompt helpers."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date
from pathlib import Path

from ...agents.memory.memory_schema import (
    MemoryEntry,
    MemorySource,
    MemoryStatus,
    MemoryTag,
)
from ...agents.memory.memory_store import MemoryStore
from ...constant import DAILY_MEMORY_RECENT_LIMIT, MEMORY_DAILY_DIR

logger = logging.getLogger(__name__)

_DATE_SESSION_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_daily_session_id(session_id: str) -> None:
    if not _DATE_SESSION_ID_RE.match(session_id):
        raise ValueError(
            f"daily memory artifact only supports YYYY-MM-DD session ids: {session_id}",
        )


def _daily_memory_path(session_id: str) -> Path:
    _validate_daily_session_id(session_id)
    return MEMORY_DAILY_DIR / f"{session_id}.md"


def _legacy_daily_memory_path(session_id: str) -> Path:
    _validate_daily_session_id(session_id)
    return MEMORY_DAILY_DIR / session_id[:7] / f"{session_id}.json"


def _persist_daily_memory_artifact_sync(
    *,
    session_id: str,
    summary: str,
    content: str,
    generated_at: str,
    source_message_count: int,
) -> Path:
    artifact_path = _daily_memory_path(session_id)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)

    summary_text = (summary or content or "").strip()
    buffer_text = (content or summary or "").strip()

    store = MemoryStore(str(artifact_path))
    entry = MemoryEntry(
        id=f"daily_{session_id.replace('-', '')}",
        date=date.fromisoformat(session_id),
        entity="杨浩",
        source=MemorySource.DAILY_SUMMARY,
        authority=0.6,
        tags=[MemoryTag.REVIEW],
        status=MemoryStatus.MILESTONE,
        content=summary_text or "当日无可提炼摘要。",
    )
    store._data.entries = [entry]  # noqa: SLF001 - internal write path
    store._data.buffer_text = (
        f"generated_at: {generated_at}\n"
        f"source_message_count: {source_message_count}\n\n"
        f"{buffer_text}"
    ).strip()
    store.save()

    legacy_path = _legacy_daily_memory_path(session_id)
    if legacy_path.exists():
        legacy_path.unlink()
        if legacy_path.parent.exists() and not any(legacy_path.parent.iterdir()):
            legacy_path.parent.rmdir()

    return artifact_path


async def save_daily_memory_artifact(
    *,
    session_id: str,
    summary: str,
    content: str,
    generated_at: str,
    source_message_count: int,
) -> Path:
    """Persist one daily memory artifact for a closed daily session."""
    return await asyncio.to_thread(
        _persist_daily_memory_artifact_sync,
        session_id=session_id,
        summary=summary,
        content=content,
        generated_at=generated_at,
        source_message_count=source_message_count,
    )


def _extract_buffer_metadata(buffer_text: str) -> tuple[str, int, str]:
    generated_at = ""
    source_message_count = 0
    remaining_lines: list[str] = []

    for idx, line in enumerate(buffer_text.splitlines()):
        stripped = line.strip()
        if idx == 0 and stripped.startswith("generated_at:"):
            generated_at = stripped.split(":", 1)[1].strip()
            continue
        if idx <= 1 and stripped.startswith("source_message_count:"):
            raw_count = stripped.split(":", 1)[1].strip()
            try:
                source_message_count = int(raw_count)
            except ValueError:
                source_message_count = 0
            continue
        remaining_lines.append(line)

    return generated_at, source_message_count, "\n".join(remaining_lines).strip()


def _load_md_daily_memory(path: Path) -> dict | None:
    store = MemoryStore(str(path))
    data = store.load()

    active_entries = [entry for entry in data.entries if not entry.archived]
    primary_entry = active_entries[0] if active_entries else None
    generated_at, source_message_count, buffer_content = _extract_buffer_metadata(
        data.buffer_text,
    )

    summary = primary_entry.content.strip() if primary_entry else ""
    content = buffer_content or summary
    if not summary and not content:
        return None

    session_id = path.stem
    return {
        "date": session_id,
        "session_id": session_id,
        "generated_at": generated_at,
        "summary": summary,
        "content": content,
        "source_message_count": source_message_count,
    }


def _migrate_legacy_json_file(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to load legacy daily memory artifact: %s", path)
        return None

    session_id = payload.get("session_id") or path.stem
    try:
        artifact_path = _persist_daily_memory_artifact_sync(
            session_id=session_id,
            summary=payload.get("summary", ""),
            content=payload.get("content", ""),
            generated_at=payload.get("generated_at", ""),
            source_message_count=payload.get("source_message_count", 0),
        )
    except Exception:
        logger.warning(
            "Failed to migrate legacy daily memory artifact: %s",
            path,
            exc_info=True,
        )
        return None

    return _load_md_daily_memory(artifact_path)


def _cleanup_or_migrate_legacy_json_file(path: Path) -> dict | None:
    """Ensure one legacy JSON file is either migrated or removed."""
    session_id = path.stem
    target_md_path = _daily_memory_path(session_id)

    if target_md_path.exists():
        try:
            path.unlink()
            if path.parent.exists() and not any(path.parent.iterdir()):
                path.parent.rmdir()
        except Exception:
            logger.warning(
                "Failed to remove legacy daily memory artifact: %s",
                path,
                exc_info=True,
            )
        return None

    return _migrate_legacy_json_file(path)


async def load_recent_daily_memories(
    *,
    limit: int = DAILY_MEMORY_RECENT_LIMIT,
    exclude_session_id: str | None = None,
) -> list[dict]:
    """Load recent daily memory artifacts, newest first."""
    if limit <= 0 or not MEMORY_DAILY_DIR.exists():
        return []

    legacy_json_paths = sorted(
        MEMORY_DAILY_DIR.glob("*/*.json"),
        key=lambda p: p.stem,
        reverse=True,
    )
    for legacy_path in legacy_json_paths:
        try:
            await asyncio.to_thread(_cleanup_or_migrate_legacy_json_file, legacy_path)
        except Exception:
            logger.warning(
                "Failed to cleanup legacy daily memory artifact: %s",
                legacy_path,
                exc_info=True,
            )

    md_paths = sorted(
        MEMORY_DAILY_DIR.glob("*.md"),
        key=lambda p: p.stem,
        reverse=True,
    )
    paths: list[Path] = md_paths
    memories: list[dict] = []
    seen_session_ids: set[str] = set()

    for path in paths:
        if len(memories) >= limit:
            break

        session_id = path.stem
        if exclude_session_id and session_id == exclude_session_id:
            continue
        if session_id in seen_session_ids:
            continue

        try:
            payload = await asyncio.to_thread(
                _load_md_daily_memory if path.suffix == ".md" else _migrate_legacy_json_file,
                path,
            )
        except Exception:
            logger.warning("Failed to load daily memory artifact: %s", path)
            continue

        if not payload:
            continue

        memories.append(payload)
        seen_session_ids.add(session_id)

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
