# -*- coding: utf-8 -*-
"""Long-term memory tool functions for NovaPaw agents. (TASK-007 V2.0)

Updated to use MemoryStore (YAML+MD with Authority Resolution) and return ToolResponse.
"""
import os
import uuid
import logging
from datetime import date

from agentscope.tool import ToolResponse

from ..memory.memory_store import MemoryStore, EntityBindingError
from ..memory.memory_schema import MemoryEntry, MemorySource, MemoryTag

logger = logging.getLogger(__name__)

LTM_PATH = os.path.expanduser("~/.novapaw/MEMORY.md")


def create_long_term_memory_tools():
    """Create and return long-term memory tool functions.

    Returns:
        tuple: (write_tool_func, read_tool_func)
    """

    async def write_long_term_memory(
        entity: str,
        content: str,
        tags: list[str] | None = None,
    ) -> ToolResponse:
        """Write a structured fact to long-term memory (Authority 1.0).

        Use this when the user explicitly says "记住这个" or for core facts.

        Args:
            entity: Full name of the entity (e.g., "杨浩", "刘有为"). 
                    NEVER use pronouns like "他/她".
            content: The fact/memory content. Be specific.
            tags: List of tags (e.g., ["preference", "development"]).

        Returns:
            ToolResponse with confirmation message.
        """
        try:
            store = MemoryStore(LTM_PATH)
            
            # Default tags if none provided
            safe_tags = []
            if tags:
                for t in tags:
                    try:
                        safe_tags.append(MemoryTag(t))
                    except ValueError:
                        safe_tags.append(MemoryTag.PREFERENCE)
            if not safe_tags:
                safe_tags = [MemoryTag.PREFERENCE]

            # Create entry with highest authority (User Direct)
            entry = MemoryEntry(
                id=f"mem_{uuid.uuid4().hex[:8]}",
                date=date.today(),
                entity=entity,
                source=MemorySource.USER_DIRECT,
                authority=1.0,
                tags=safe_tags,
                content=content
            )

            store.add_entry(entry)
            store.save()
            msg = f"✅ 记忆已写入 [1.0 权威度]: [{entity}] {content[:50]}"
            return ToolResponse(content=[{"type": "text", "text": msg}])

        except EntityBindingError as e:
            return ToolResponse(content=[{"type": "text", "text": f"❌ P0 实体隔离拦截: {e}"}])
        except Exception as e:
            logger.error("Failed to write memory: %s", e)
            return ToolResponse(content=[{"type": "text", "text": f"❌ 写入失败: {e}"}])

    async def read_long_term_memory(
        tags: list[str] | None = None,
    ) -> ToolResponse:
        """Read entries from long-term memory.

        Args:
            tags: Filter by tags (optional).

        Returns:
            ToolResponse with formatted memory entries.
        """
        try:
            store = MemoryStore(LTM_PATH)
            data = store.load()
            
            entries = data.entries
            if tags:
                # Filter entries that contain at least one of the requested tags
                entries = [
                    e for e in entries 
                    if any(t in e.tags for t in tags)
                ]

            if not entries:
                return ToolResponse(content=[{"type": "text", "text": "📭 长期记忆为空或无匹配标签。"}])

            lines = []
            for e in sorted(entries, key=lambda x: x.date, reverse=True)[:20]:
                tag_str = ", ".join([t.value if hasattr(t, 'value') else str(t) for t in e.tags])
                lines.append(f"- **【{e.entity} | {e.date} | 权威:{e.authority}】** `[{tag_str}]` {e.content}")

            msg = f"📚 长期记忆 ({len(lines)} 条):\n\n" + "\n".join(lines)
            return ToolResponse(content=[{"type": "text", "text": msg}])
        except Exception as e:
            logger.error("Failed to read memory: %s", e)
            return ToolResponse(content=[{"type": "text", "text": f"❌ 读取失败: {e}"}])

    return write_long_term_memory, read_long_term_memory
