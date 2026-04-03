"""Session manager.

Handles session lifecycle:
- Create new session (daily)
- Close old session (triggers memory summary)
- Switch between sessions
- Track session state
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Session


class SessionManager:
    """Manage session lifecycle."""
    
    def __init__(self, sessions_dir: str = "~/.novapaw/sessions"):
        self.sessions_dir = Path(sessions_dir).expanduser()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: Optional[Session] = None
    
    @property
    def current_session(self) -> Optional[Session]:
        """Get current active session."""
        return self._current_session
    
    def get_month_dir(self, date: Optional[datetime] = None) -> Path:
        """Get month directory for given date."""
        date = date or datetime.now()
        month_dir = self.sessions_dir / date.strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)
        return month_dir
    
    def get_session_path(self, session_id: str) -> Path:
        """Get file path for a session."""
        # Parse date from session_id (YYYY-MM-DD format)
        try:
            date = datetime.strptime(session_id, "%Y-%m-%d")
            month_dir = self.get_month_dir(date)
            return month_dir / f"{session_id}.json"
        except ValueError:
            # Fallback to current month
            return self.get_month_dir() / f"{session_id}.json"
    
    def create_session(self, session_id: Optional[str] = None) -> Session:
        """Create a new session.
        
        Args:
            session_id: Optional session ID. Defaults to today's date (YYYY-MM-DD).
        
        Returns:
            Created session.
        """
        if session_id is None:
            session_id = datetime.now().strftime("%Y-%m-%d")
        
        session = Session(id=session_id)
        session_path = self.get_session_path(session_id)
        session.conversation_path = str(session_path).replace(".json", "_conv.json")
        
        # Save session metadata
        self._save_session(session)
        
        # Create conversation file
        conv_path = Path(session.conversation_path)
        conv_path.parent.mkdir(parents=True, exist_ok=True)
        conv_path.write_text("[]")
        
        self._current_session = session
        return session
    
    def load_session(self, session_id: str) -> Optional[Session]:
        """Load an existing session.
        
        Args:
            session_id: Session ID to load.
        
        Returns:
            Loaded session or None if not found.
        """
        session_path = self.get_session_path(session_id)
        if not session_path.exists():
            return None
        
        data = json.loads(session_path.read_text())
        session = Session.from_dict(data)
        self._current_session = session
        return session
    
    def close_session(self, session: Optional[Session] = None) -> None:
        """Close a session.
        
        Args:
            session: Session to close. Defaults to current session.
        """
        session = session or self._current_session
        if session is None:
            return
        
        session.close()
        self._save_session(session)
        
        # Trigger memory summary (TODO: implement)
        # self._trigger_memory_summary(session)
        
        if self._current_session == session:
            self._current_session = None
    
    def get_or_create_today_session(self) -> Session:
        """Get today's session or create if not exists."""
        today = datetime.now().strftime("%Y-%m-%d")
        session = self.load_session(today)
        if session is None:
            session = self.create_session(today)
        return session
    
    def _save_session(self, session: Session) -> None:
        """Save session to disk."""
        session_path = self.get_session_path(session.id)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text(json.dumps(session.to_dict(), indent=2))
    
    def list_sessions(self, limit: int = 10) -> list[Session]:
        """List recent sessions.
        
        Args:
            limit: Maximum number of sessions to return.
        
        Returns:
            List of sessions, sorted by date (newest first).
        """
        sessions = []
        for month_dir in sorted(self.sessions_dir.iterdir(), reverse=True):
            if not month_dir.is_dir():
                continue
            for session_file in sorted(month_dir.glob("*.json"), reverse=True):
                try:
                    data = json.loads(session_file.read_text())
                    sessions.append(Session.from_dict(data))
                    if len(sessions) >= limit:
                        return sessions
                except (json.JSONDecodeError, KeyError):
                    continue
        return sessions
