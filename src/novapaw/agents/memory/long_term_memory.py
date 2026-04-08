# -*- coding: utf-8 -*-
"""Long-term memory module for NovaPaw.

Provides structured persistent memory storage with schema validation,
read/write interfaces, and prompt injection support.

Storage:
    ~/.novapaw/memory/long_term.json - Structured long-term facts
    ~/.novapaw/memory/long_term_schema.json - Core type definitions
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import aiofiles

from ...constant import MEMORY_DIR

logger = logging.getLogger(__name__)

LONG_TERM_PATH = MEMORY_DIR / "long_term.json"
SCHEMA_PATH = MEMORY_DIR / "long_term_schema.json"

# Minimum required fields for each entry
REQUIRED_FIELDS = {"id", "type", "content", "source", "created_at", "updated_at"}


class LongTermMemory:
    """Manage structured long-term memory entries."""

    def __init__(
        self,
        long_term_path: Path | None = None,
        schema_path: Path | None = None,
    ):
        self.long_term_path = long_term_path or LONG_TERM_PATH
        self.schema_path = schema_path or SCHEMA_PATH
        self._core_types: set[str] = set()
        self._entries: list[dict] = []
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """Lazy-load from disk on first access."""
        if self._loaded:
            return
        await self._load_schema()
        await self._load_entries()
        self._loaded = True

    async def _load_schema(self) -> None:
        """Load core types from schema file."""
        if not self.schema_path.exists():
            logger.warning("Schema file not found: %s", self.schema_path)
            return
        try:
            async with aiofiles.open(
                self.schema_path, "r", encoding="utf-8"
            ) as f:
                data = json.loads(await f.read())
            self._core_types = set(data.get("core_types", {}).keys())
            logger.debug(
                "Loaded %d core types from schema", len(self._core_types)
            )
        except Exception as e:
            logger.warning("Failed to load schema: %s", e)

    async def _load_entries(self) -> None:
        """Load all entries from long_term.json."""
        if not self.long_term_path.exists():
            logger.debug("Long-term memory file not found, starting fresh")
            self._entries = []
            return
        try:
            async with aiofiles.open(
                self.long_term_path, "r", encoding="utf-8"
            ) as f:
                data = json.loads(await f.read())
            self._entries = data.get("entries", [])
            logger.debug("Loaded %d long-term memory entries", len(self._entries))
        except Exception as e:
            logger.warning("Failed to load long-term memory: %s", e)
            self._entries = []

    async def _save_entries(self) -> None:
        """Persist entries to disk."""
        self.long_term_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": "1.0", "entries": self._entries}
        async with aiofiles.open(
            self.long_term_path, "w", encoding="utf-8"
        ) as f:
            await f.write(json.dumps(payload, ensure_ascii=False, indent=2))
        logger.debug("Saved %d entries to %s", len(self._entries), self.long_term_path)

    def _now_iso(self) -> str:
        """Current UTC time in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def is_core_type(self, type_name: str) -> bool:
        """Check if a type is a core type (requires schema to be loaded)."""
        return type_name in self._core_types

    async def write(
        self,
        *,
        type: str,
        content: str,
        source: str = "user",
        entry_id: str | None = None,
    ) -> dict:
        """Write a new long-term memory entry.

        Args:
            type: Entry type (core or custom).
            content: The memory content.
            source: Where this came from (e.g., "user", "daily_summary", "heartbeat").
            entry_id: Optional explicit ID. Auto-generated if None.

        Returns:
            The created entry dict.
        """
        await self._ensure_loaded()

        entry_id = entry_id or str(uuid.uuid4())[:12]
        now = self._now_iso()

        entry = {
            "id": entry_id,
            "type": type,
            "content": content,
            "source": source,
            "created_at": now,
            "updated_at": now,
        }

        self._entries.append(entry)
        await self._save_entries()

        type_label = "core" if self.is_core_type(type) else "custom"
        logger.info(
            "Long-term memory [%s] written: id=%s type=%s(%s)",
            source,
            entry_id,
            type,
            type_label,
        )
        return entry

    async def update(
        self,
        *,
        entry_id: str,
        content: str | None = None,
        type: str | None = None,
    ) -> dict | None:
        """Update an existing entry by ID.

        Args:
            entry_id: The entry ID to update.
            content: New content (optional).
            type: New type (optional).

        Returns:
            Updated entry or None if not found.
        """
        await self._ensure_loaded()

        for entry in self._entries:
            if entry["id"] == entry_id:
                if content is not None:
                    entry["content"] = content
                if type is not None:
                    entry["type"] = type
                entry["updated_at"] = self._now_iso()
                await self._save_entries()
                logger.info("Long-term memory updated: id=%s", entry_id)
                return entry

        logger.warning("Entry not found for update: %s", entry_id)
        return None

    async def delete(self, entry_id: str) -> bool:
        """Delete an entry by ID.

        Returns:
            True if deleted, False if not found.
        """
        await self._ensure_loaded()

        original_len = len(self._entries)
        self._entries = [e for e in self._entries if e["id"] != entry_id]
        if len(self._entries) < original_len:
            await self._save_entries()
            logger.info("Long-term memory deleted: id=%s", entry_id)
            return True

        logger.warning("Entry not found for delete: %s", entry_id)
        return False

    async def read_all(self) -> list[dict]:
        """Return all entries (newest first)."""
        await self._ensure_loaded()
        return sorted(
            self._entries,
            key=lambda e: e.get("updated_at", ""),
            reverse=True,
        )

    async def read_by_type(self, type_name: str) -> list[dict]:
        """Return entries matching a specific type."""
        await self._ensure_loaded()
        return [e for e in self._entries if e.get("type") == type_name]

    async def read_recent(self, limit: int = 20) -> list[dict]:
        """Return the most recent entries."""
        await self._ensure_loaded()
        return sorted(
            self._entries,
            key=lambda e: e.get("updated_at", ""),
            reverse=True,
        )[:limit]

    def build_prompt_section(
        self,
        entries: list[dict] | None = None,
        *,
        language: str = "zh",
        max_entries: int = 30,
    ) -> str:
        """Build a system prompt section from long-term memory entries.

        Args:
            entries: Specific entries to include. If None, reads recent ones.
            language: Language for the prompt header.
            max_entries: Maximum number of entries to include.

        Returns:
            Formatted prompt string, or empty string if no entries.
        """
        if entries is None:
            # Synchronous access for prompt building - use cached if available
            entries = sorted(
                self._entries,
                key=lambda e: e.get("updated_at", ""),
                reverse=True,
            )[:max_entries]

        if not entries:
            return ""

        lines: list[str] = []
        for entry in entries:
            entry_type = entry.get("type", "unknown")
            content = (entry.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"- [{entry_type}] {content}")

        if not lines:
            return ""

        if language == "zh":
            header = (
                "## 长期记忆（结构化事实）\n\n"
                "以下是系统记录的长期有效事实。它们是稳定背景信息，"
                "不是临时对话内容。在回答相关时应参考。\n\n"
            )
        else:
            header = (
                "## Long-Term Memory (Structured Facts)\n\n"
                "The following are long-lasting facts recorded by the system. "
                "They are stable background information, not temporary conversation content.\n\n"
            )

        return header + "\n".join(lines)

    def build_prompt_section_sync(
        self,
        *,
        language: str = "zh",
        max_entries: int = 30,
    ) -> str:
        """Synchronous version for use in prompt building.

        Reads directly from disk without async I/O. Safe for use
        during agent initialization.
        """
        try:
            if self.long_term_path.exists():
                data = json.loads(
                    self.long_term_path.read_text(encoding="utf-8")
                )
                entries = data.get("entries", [])
            else:
                entries = []
        except Exception:
            entries = []

        if not entries:
            return ""

        entries = sorted(
            entries,
            key=lambda e: e.get("updated_at", ""),
            reverse=True,
        )[:max_entries]

        lines: list[str] = []
        for entry in entries:
            entry_type = entry.get("type", "unknown")
            content = (entry.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"- [{entry_type}] {content}")

        if not lines:
            return ""

        if language == "zh":
            header = (
                "## 长期记忆（结构化事实）\n\n"
                "以下是系统记录的长期有效事实。它们是稳定背景信息，"
                "不是临时对话内容。在回答相关时应参考。\n\n"
            )
        else:
            header = (
                "## Long-Term Memory (Structured Facts)\n\n"
                "The following are long-lasting facts recorded by the system. "
                "They are stable background information, not temporary conversation content.\n\n"
            )

        return header + "\n".join(lines)


# Singleton instance
_LONG_TERM_MEMORY: LongTermMemory | None = None


def get_long_term_memory() -> LongTermMemory:
    """Get or create the singleton long-term memory instance."""
    global _LONG_TERM_MEMORY
    if _LONG_TERM_MEMORY is None:
        _LONG_TERM_MEMORY = LongTermMemory()
    return _LONG_TERM_MEMORY
