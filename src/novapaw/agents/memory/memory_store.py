"""
NovaPaw Memory Store (V2.0)
Core engine for reading, validating, resolving conflicts, and writing YAML+MD memory files.
"""
import os
import re
import uuid
import yaml
from datetime import date, datetime
from typing import List, Optional, Tuple
from pathlib import Path

from .memory_schema import MemoryEntry, MemoryFile, MemorySource, MemoryStatus, MemoryTag
from pydantic import ValidationError


class MemoryStoreError(Exception):
    """Base exception for memory store operations."""
    pass


class EntityBindingError(MemoryStoreError):
    """P0: Isolated pronoun detected in entity field."""
    pass


class BufferOverflowError(MemoryStoreError):
    """Buffer exceeds safe threshold for LLM injection."""
    pass


class MemoryStore:
    """Manages a single memory file (e.g., long_term.md, daily/2026-04-08.md)."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._data = MemoryFile()

    # ------------------------------------------------------------------
    # I/O Operations
    # ------------------------------------------------------------------
    def load(self) -> MemoryFile:
        """Parse YAML frontmatter + Markdown buffer from file."""
        if not self.file_path.exists():
            return MemoryFile()

        content = self.file_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)

        if len(parts) < 3:
            # No valid frontmatter, treat entire file as buffer
            self._data = MemoryFile(buffer_text=content.strip())
            return self._data

        yaml_raw = parts[1].strip()
        md_buffer = parts[2].strip()

        try:
            raw_entries = yaml.safe_load(yaml_raw) or []
            if not isinstance(raw_entries, list):
                raw_entries = [raw_entries]

            valid_entries = []
            for item in raw_entries:
                if isinstance(item, dict):
                    try:
                        # Auto-fill defaults if missing
                        item.setdefault("id", str(uuid.uuid4())[:8])
                        item.setdefault("status", "milestone")
                        item.setdefault("archived", False)
                        valid_entries.append(MemoryEntry(**item))
                    except ValidationError as e:
                        print(f"⚠️ Skipped invalid entry in {self.file_path.name}: {e}")
            self._data = MemoryFile(entries=valid_entries, buffer_text=md_buffer)

        except yaml.YAMLError as e:
            print(f"⚠️ YAML parse failed in {self.file_path.name}: {e}")
            self._data = MemoryFile(buffer_text=content.strip())

        return self._data

    def save(self, compact_buffer: bool = False) -> None:
        """Write validated entries + buffer back to file."""
        if not self._data.entries and not self._data.buffer_text.strip():
            return

        # Serialize entries
        yaml_dump = yaml.dump(
            [e.model_dump(exclude={"archived"}) for e in self._data.entries if not e.archived],
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False
        )

        buffer_text = self._data.buffer_text.strip()
        if compact_buffer and len(buffer_text) > 500:
            buffer_text = "# 📝 缓冲区 (已压缩)\n- 触发 Heartbeat Compaction 清理过长日志。"

        output = f"---\n{yaml_dump}\n---\n\n# 📝 缓冲区 / 原始上下文\n{buffer_text}\n"
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(output, encoding="utf-8")

    # ------------------------------------------------------------------
    # Mutation & Conflict Resolution
    # ------------------------------------------------------------------
    def add_entry(self, entry: MemoryEntry) -> MemoryEntry:
        """Add new entry, apply conflict resolution rules."""
        self.load()

        # P0 Check
        if re.search(r"^(他|她|它|对方|这人|那家伙)\b", entry.content):
            raise EntityBindingError("P0: Content contains isolated pronouns. Use full entity names.")

        # Append & Resolve
        self._data.entries.append(entry)
        self._resolve_conflicts()
        return entry

    def append_to_buffer(self, text: str) -> None:
        """Append raw observation/log to buffer. Warns if bloated."""
        self.load()
        if not self._data.buffer_text.endswith("\n"):
            self._data.buffer_text += "\n"
        self._data.buffer_text += f"- {datetime.now().strftime('%Y-%m-%d %H:%M')}: {text.strip()}\n"
        
        if len(self._data.buffer_text) > 1500:
            print("⚠️ Buffer bloated (>1.5k). Schedule compaction in next Heartbeat.")

    def _resolve_conflicts(self) -> None:
        """
        Conflict Resolution Algorithm:
        1. Group by (entity, tag)
        2. Sort by authority DESC -> date DESC
        3. Keep top 3, mark rest as archived=True
        """
        from collections import defaultdict
        groups = defaultdict(list)

        for entry in self._data.entries:
            key = (entry.entity, tuple(entry.tags))
            groups[key].append(entry)

        to_keep = []
        for key, items in groups.items():
            sorted_items = sorted(
                items, 
                key=lambda x: (x.authority, x.date), 
                reverse=True
            )
            for i, item in enumerate(sorted_items):
                if i >= 3:  # Keep max 3 per group
                    item.archived = True
                to_keep.append(item)

        self._data.entries = [e for e in to_keep if not e.archived]

    def promote_buffer_items(self, new_entries: List[MemoryEntry]) -> None:
        """Promote verified hypotheses/observations from buffer to structured entries."""
        self.load()
        for entry in new_entries:
            self.add_entry(entry)
        # Clear buffer after successful promotion
        self._data.buffer_text = ""
