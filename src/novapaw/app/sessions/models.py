"""Session data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Session:
    """Session data model.
    
    Attributes:
        id: Session identifier (usually date-based: YYYY-MM-DD)
        created_at: Session creation timestamp
        closed_at: Session closure timestamp (None if active)
        conversation_path: Path to conversation records
        summary: Session summary (generated on close)
    """
    id: str
    created_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None
    conversation_path: Optional[str] = None
    summary: Optional[str] = None
    
    @property
    def is_active(self) -> bool:
        """Check if session is still active."""
        return self.closed_at is None
    
    def close(self) -> None:
        """Close the session."""
        self.closed_at = datetime.now()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "conversation_path": self.conversation_path,
            "summary": self.summary,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Create Session from dictionary."""
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            conversation_path=data.get("conversation_path"),
            summary=data.get("summary"),
        )
