"""
NovaPaw Memory Schema (V2.0 - Unified YAML+MD Architecture)
Defines strong types, enums, and Pydantic validation for all memory layers.
"""
from enum import Enum
from datetime import date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
import re


class MemorySource(str, Enum):
    """Authority tracking: higher = more reliable"""
    USER_DIRECT = "user_direct"          # 1.0
    MANUAL_EDIT = "manual_edit"          # 1.0
    INTERACTION_LOG = "interaction_log"  # 0.8
    WEEKLY_SUMMARY = "weekly_summary"    # 0.7
    DAILY_SUMMARY = "daily_summary"      # 0.6
    AUTO_EXTRACT = "auto_extract"        # 0.4


class MemoryTag(str, Enum):
    """Standardized categorization for funnel filtering"""
    DEVELOPMENT = "development"
    RELATIONSHIP = "relationship"
    WEALTH = "wealth"
    LEARNING = "learning"
    LIFESTYLE = "lifestyle"
    HEALTH = "health"
    REVIEW = "review"
    TOOLS = "tools"
    PREFERENCE = "preference"


class MemoryStatus(str, Enum):
    """Funnel valve: controls propagation to higher layers"""
    ROUTINE = "routine"       # Daily only, dropped at weekly/monthly
    MILESTONE = "milestone"   # Propagates to monthly/long-term
    CRITICAL = "critical"     # Propagates everywhere, full context injection


class MemoryEntry(BaseModel):
    """Atomic memory unit with metadata for conflict resolution."""
    id: str
    date: date
    entity: str
    source: MemorySource
    authority: float = Field(ge=0.0, le=1.0)
    tags: List[MemoryTag]
    content: str
    status: MemoryStatus = MemoryStatus.MILESTONE
    archived: bool = False  # Marked for removal during compaction

    model_config = ConfigDict(use_enum_values=True)

    @field_validator('entity')
    @classmethod
    def enforce_entity_isolation(cls, v: str) -> str:
        """P0 Constraint: Reject isolated pronouns in entity field."""
        pronoun_pattern = r"^(他|她|它|对方|这人|那家伙|该用户|这个人)\s*$"
        if re.search(pronoun_pattern, v):
            raise ValueError(
                f"P0 Entity Isolation Violation: '{v}' is an isolated pronoun. "
                "Must use full name (e.g., '刘有为', '杨浩')."
            )
        return v.strip()

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v or len(v.strip()) < 2:
            raise ValueError("Content must be non-empty and meaningful.")
        return v.strip()


class MemoryFile(BaseModel):
    """Represents a single YAML+MD memory file structure."""
    entries: List[MemoryEntry] = Field(default_factory=list)
    buffer_text: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('buffer_text')
    @classmethod
    def limit_buffer_size(cls, v: str) -> str:
        # Increased limit to accommodate existing MEMORY.md content.
        # 10,000 chars is roughly 5k-7k tokens, which is safe for a single file buffer.
        if len(v) > 10000:
            # Don't raise error during load, just warn.
            # We will handle compaction advice in the tool or heartbeat.
            print(f"⚠️ Buffer warning: {len(v)} chars. Consider compaction.")
        return v
