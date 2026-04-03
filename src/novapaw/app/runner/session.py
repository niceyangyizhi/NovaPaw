# -*- coding: utf-8 -*-
"""Safe JSON session with daily active-session management.

Windows filenames cannot contain: \\ / : * ? " < > |
This module wraps agentscope's SessionBase so that session_id values are
sanitized before being used as filenames. NovaPaw Phase 1 session management
uses ``session_id`` as the only identity key and keeps one active daily
session shared by all channels.
"""
import os
import re
import json
import logging
from dataclasses import dataclass
from datetime import datetime

from typing import Union, Sequence

import aiofiles
from agentscope.session import SessionBase

logger = logging.getLogger(__name__)


# Characters forbidden in Windows filenames
_UNSAFE_FILENAME_RE = re.compile(r'[\\/:*?"<>|]')
_DATE_SESSION_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def sanitize_filename(name: str) -> str:
    """Replace characters that are illegal in Windows filenames with ``--``.

    >>> sanitize_filename('discord:dm:12345')
    'discord--dm--12345'
    >>> sanitize_filename('normal-name')
    'normal-name'
    """
    return _UNSAFE_FILENAME_RE.sub("--", name)


@dataclass(frozen=True)
class SessionResolution:
    """Result of resolving the active daily session."""

    session_id: str
    previous_session_id: str | None = None
    rolled_over: bool = False
    created: bool = False


class SafeJSONSession(SessionBase):
    """SessionBase subclass with filename sanitization and async file I/O.

    Overrides all file-reading/writing methods to use :mod:`aiofiles` so
    that disk I/O does not block the event loop.
    """

    def __init__(
        self,
        save_dir: str = "./",
    ) -> None:
        """Initialize the JSON session class.

        Args:
            save_dir (`str`, defaults to `"./"):
                The directory to save the session state.
        """
        self.save_dir = save_dir

    @property
    def _active_session_path(self) -> str:
        return os.path.join(self.save_dir, "active_session.json")

    @staticmethod
    def _daily_session_id(now: datetime | None = None) -> str:
        return (now or datetime.now()).date().isoformat()

    @staticmethod
    def _session_month_dir(session_id: str) -> str:
        if _DATE_SESSION_ID_RE.match(session_id):
            return session_id[:7]
        return ""

    def _get_save_path(self, session_id: str, user_id: str) -> str:
        """Return a filesystem-safe save path.

        Overrides the parent implementation to ensure the generated
        filename is valid on Windows, macOS and Linux.
        """
        month_dir = self._session_month_dir(session_id)
        base_dir = (
            os.path.join(self.save_dir, month_dir)
            if month_dir
            else self.save_dir
        )
        os.makedirs(base_dir, exist_ok=True)
        safe_sid = sanitize_filename(session_id)
        file_path = f"{safe_sid}.json"
        return os.path.join(base_dir, file_path)

    async def _load_active_session_meta(self) -> dict:
        """Load active session metadata with error handling.

        Returns empty dict if file doesn't exist or is corrupted.
        """
        active_path = self._active_session_path
        if not os.path.exists(active_path):
            return {}
        try:
            async with aiofiles.open(
                active_path,
                "r",
                encoding="utf-8",
                errors="surrogatepass",
            ) as f:
                content = await f.read()
                return json.loads(content) if content else {}
        except json.JSONDecodeError:
            logger.warning(
                "Corrupted active_session.json at %s, starting fresh",
                active_path,
            )
            return {}
        except Exception:
            logger.exception(
                "Failed to load active_session.json at %s",
                active_path,
            )
            return {}

    async def _save_active_session_meta(self, data: dict) -> None:
        os.makedirs(self.save_dir, exist_ok=True)
        async with aiofiles.open(
            self._active_session_path,
            "w",
            encoding="utf-8",
            errors="surrogatepass",
        ) as f:
            await f.write(json.dumps(data, ensure_ascii=False))

    async def resolve_active_session(
        self,
        requested_session_id: str = "",
        now: datetime | None = None,
    ) -> SessionResolution:
        """Resolve the single active daily session.

        All channels share the same active session. The active session id is
        simply ``YYYY-MM-DD``. On the first request of a new day, the previous
        active session is marked as rolled over and a new one becomes active.
        """
        current_time = now or datetime.now()
        target_session_id = self._daily_session_id(current_time)
        active_meta = await self._load_active_session_meta()
        current_session_id = active_meta.get("session_id")

        if current_session_id == target_session_id:
            return SessionResolution(session_id=target_session_id)

        rolled_over = bool(
            current_session_id and current_session_id != target_session_id
        )
        created = current_session_id != target_session_id
        previous_session_id = (
            current_session_id if rolled_over else None
        )

        await self._save_active_session_meta(
            {
                "session_id": target_session_id,
                "date": target_session_id,
                "requested_session_id": requested_session_id,
                "previous_session_id": previous_session_id,
                "updated_at": current_time.isoformat(),
            },
        )

        logger.info(
            "Resolved active session: requested=%s active=%s previous=%s "
            "(rolled_over=%s, created=%s)",
            requested_session_id,
            target_session_id,
            previous_session_id,
            rolled_over,
            created,
        )
        return SessionResolution(
            session_id=target_session_id,
            previous_session_id=previous_session_id,
            rolled_over=rolled_over,
            created=created,
        )

    async def save_session_state(
        self,
        session_id: str,
        user_id: str = "",
        **state_modules_mapping,
    ) -> None:
        """Save state modules to a JSON file using async I/O."""
        state_dicts = {
            name: state_module.state_dict()
            for name, state_module in state_modules_mapping.items()
        }
        session_save_path = self._get_save_path(session_id, user_id=user_id)
        with open(
            session_save_path,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(state_dicts, ensure_ascii=False))

        logger.info(
            "Saved session state to %s successfully.",
            session_save_path,
        )

    async def load_session_state(
        self,
        session_id: str,
        user_id: str = "",
        allow_not_exist: bool = True,
        **state_modules_mapping,
    ) -> None:
        """Load state modules from a JSON file using async I/O."""
        session_save_path = self._get_save_path(session_id, user_id=user_id)
        if os.path.exists(session_save_path):
            async with aiofiles.open(
                session_save_path,
                "r",
                encoding="utf-8",
                errors="surrogatepass",
            ) as f:
                content = await f.read()
                states = json.loads(content)

            for name, state_module in state_modules_mapping.items():
                if name in states:
                    state_module.load_state_dict(states[name])
            logger.info(
                "Load session state from %s successfully.",
                session_save_path,
            )

        elif allow_not_exist:
            logger.info(
                "Session file %s does not exist. Skip loading session state.",
                session_save_path,
            )

        else:
            raise ValueError(
                f"Failed to load session state for file {session_save_path} "
                "because it does not exist.",
            )

    async def update_session_state(
        self,
        session_id: str,
        key: Union[str, Sequence[str]],
        value,
        user_id: str = "",
        create_if_not_exist: bool = True,
    ) -> None:
        session_save_path = self._get_save_path(session_id, user_id=user_id)

        if os.path.exists(session_save_path):
            async with aiofiles.open(
                session_save_path,
                "r",
                encoding="utf-8",
                errors="surrogatepass",
            ) as f:
                content = await f.read()
                states = json.loads(content)

        else:
            if not create_if_not_exist:
                raise ValueError(
                    f"Session file {session_save_path} does not exist.",
                )
            states = {}

        path = key.split(".") if isinstance(key, str) else list(key)
        if not path:
            raise ValueError("key path is empty")

        cur = states
        for k in path[:-1]:
            if k not in cur or not isinstance(cur[k], dict):
                cur[k] = {}
            cur = cur[k]

        cur[path[-1]] = value

        async with aiofiles.open(
            session_save_path,
            "w",
            encoding="utf-8",
            errors="surrogatepass",
        ) as f:
            await f.write(json.dumps(states, ensure_ascii=False))

        logger.info(
            "Updated session state key '%s' in %s successfully.",
            key,
            session_save_path,
        )

    async def get_session_state_dict(
        self,
        session_id: str,
        user_id: str = "",
        allow_not_exist: bool = True,
    ) -> dict:
        """Return the session state dict from the JSON file.

        Args:
            session_id (`str`):
                The session id.
            user_id (`str`, default to `""`):
                The user ID for the storage.
            allow_not_exist (`bool`, defaults to `True`):
                Whether to allow the session to not exist. If `False`, raises
                an error if the session does not exist.

        Returns:
            `dict`:
                The session state dict loaded from the JSON file. Returns an
                empty dict if the file does not exist and
                `allow_not_exist=True`.
        """
        session_save_path = self._get_save_path(session_id, user_id=user_id)
        if os.path.exists(session_save_path):
            async with aiofiles.open(
                session_save_path,
                "r",
                encoding="utf-8",
                errors="surrogatepass",
            ) as file:
                content = await file.read()
                states = json.loads(content)

            logger.info(
                "Get session state dict from %s successfully.",
                session_save_path,
            )
            return states

        if allow_not_exist:
            logger.info(
                "Session file %s does not exist. Return empty state dict.",
                session_save_path,
            )
            return {}

        raise ValueError(
            f"Failed to get session state for file {session_save_path} "
            "because it does not exist.",
        )
