# -*- coding: utf-8 -*-
"""
Heartbeat: run agent with HEARTBEAT.md as query at interval.
Uses config functions (get_heartbeat_config, get_heartbeat_query_path,
load_config) for paths and settings.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, time
from typing import Any, Dict

from ...config import (
    get_heartbeat_config,
    get_heartbeat_query_path,
    load_config,
)
from ...constant import (
    HEARTBEAT_DEFAULT_TARGET,
    HEARTBEAT_TARGET_LAST,
    HEARTBEAT_TARGET_AUTO,
)
from .heartbeat_tools import create_send_to_channel_tool

logger = logging.getLogger(__name__)

# Pattern for "30m", "1h", "2h30m", "90s"
_EVERY_PATTERN = re.compile(
    r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?$",
    re.IGNORECASE,
)


def parse_heartbeat_every(every: str) -> int:
    """Parse interval string (e.g. '30m', '1h') to total seconds."""
    every = (every or "").strip()
    if not every:
        return 30 * 60  # default 30 min
    m = _EVERY_PATTERN.match(every)
    if not m:
        logger.warning("heartbeat every=%r invalid, using 30m", every)
        return 30 * 60
    hours = int(m.group("hours") or 0)
    minutes = int(m.group("minutes") or 0)
    seconds = int(m.group("seconds") or 0)
    total = hours * 3600 + minutes * 60 + seconds
    if total <= 0:
        return 30 * 60
    return total


def _in_active_hours(active_hours: Any) -> bool:
    """Return True if current local time is within [start, end]."""
    if (
        not active_hours
        or not hasattr(active_hours, "start")
        or not hasattr(active_hours, "end")
    ):
        return True
    try:
        start_parts = active_hours.start.strip().split(":")
        end_parts = active_hours.end.strip().split(":")
        start_t = time(
            int(start_parts[0]),
            int(start_parts[1]) if len(start_parts) > 1 else 0,
        )
        end_t = time(
            int(end_parts[0]),
            int(end_parts[1]) if len(end_parts) > 1 else 0,
        )
    except (ValueError, IndexError, AttributeError):
        return True
    now = datetime.now().time()
    if start_t <= end_t:
        return start_t <= now <= end_t
    return now >= start_t or now <= end_t


def build_heartbeat_auto_system_prompt(language: str = "zh") -> str:
    """Build heartbeat auto-mode system prompt based on configured language."""
    if language == "zh":
        return """你是心跳助手，定期检查用户状态并主动提供帮助。

你有 send_to_channel 工具可以发送消息给用户。

请在以下情况调用 send_to_channel：
✅ 有行动项、待办、任务需要提醒用户
✅ 有重要提醒或建议值得用户注意
✅ 有用户等待的信息或新发现
✅ 有具体的下一步建议

不要在以下情况调用：
❌ 纯确认性回复（如"好的"、"收到了"、"无更新"）
❌ 没有实质内容的回复
❌ 重复之前的内容

如果不确定是否有价值，宁可不发送。"""

    return """You are a heartbeat assistant that periodically checks the user's
state and proactively offers help.

You have a send_to_channel tool that can send messages to the user.

Use send_to_channel when:
- There are concrete action items, tasks, or reminders for the user
- There are important reminders or suggestions worth notifying
- There is new information the user is waiting for
- There is a specific next-step recommendation

Do not use send_to_channel when:
- The response is only a confirmation (for example: "ok", "received", "no update")
- The response has no substantive content
- The response only repeats previous content

If you are not sure the message is valuable enough, prefer not to send it."""


async def run_heartbeat_once(
    *,
    runner: Any,
    channel_manager: Any,
) -> None:
    """
    Run one heartbeat: read HEARTBEAT.md via config path, run agent,
    optionally dispatch to last channel (target=last or target=auto).

    - target="last": Always send response to last_dispatch channel
    - target="auto": Inject send_to_channel tool into this one-shot agent run
    - target="main": Run agent only, no dispatch

    When target="auto" and message is sent, the interaction will be saved
    to today's daily session (YYYY-MM-DD).
    """
    config = load_config()
    hb = get_heartbeat_config()
    if not _in_active_hours(hb.active_hours):
        logger.debug("heartbeat skipped: outside active hours")
        return

    path = get_heartbeat_query_path()
    if not path.is_file():
        logger.debug("heartbeat skipped: no file at %s", path)
        return

    query_text = path.read_text(encoding="utf-8").strip()
    if not query_text:
        logger.debug("heartbeat skipped: empty query file")
        return

    target = (hb.target or "").strip().lower()
    is_auto = target == HEARTBEAT_TARGET_AUTO

    # Check last_dispatch availability for auto mode
    has_last_dispatch = (
        getattr(config, 'last_dispatch', None) is not None and
        getattr(config.last_dispatch, 'channel', None) is not None and
        (getattr(config.last_dispatch, 'user_id', None) or
         getattr(config.last_dispatch, 'session_id', None))
    )

    # Auto mode fallback: if no last_dispatch, degrade to main mode
    if is_auto and not has_last_dispatch:
        logger.info(
            "heartbeat: target=auto but no last_dispatch available, "
            "degrading to target=main"
        )
        target = HEARTBEAT_DEFAULT_TARGET  # Degrade to main mode
        is_auto = False

    # Get today's session ID for saving heartbeat messages (auto mode only)
    today_session_id = datetime.now().strftime("%Y-%m-%d") if is_auto else None

    # Build request (session_id remains "main" to avoid polluting daily session state)
    req: Dict[str, Any] = {
        "input": [
            {
                "role": "user",
                "content": [{"type": "text", "text": query_text}],
            },
        ],
        "session_id": "main",
        "user_id": "main",
    }

    send_tool = None

    # target="auto": attach one-shot tool and system prompt via request extras
    if is_auto:
        # Get session from runner for saving heartbeat messages
        session = getattr(runner, 'session', None)

        send_tool = create_send_to_channel_tool(
            channel_manager=channel_manager,
            config=config,
            session=session,
            today_session_id=today_session_id,
            query_text=query_text,
        )
        req["extra_tool_functions"] = [send_tool]
        req["extra_system_prompt"] = build_heartbeat_auto_system_prompt(
            getattr(config.agents, "language", "zh")
        )
        logger.debug(
            "heartbeat: attached send_to_channel with session saving (target=auto)"
        )

    # target="last": Will dispatch all events to last channel
    # target="auto": Tool call will handle dispatch and session saving
    # target="main": No dispatch

    async def _run() -> None:
        if target == HEARTBEAT_TARGET_LAST and config.last_dispatch:
            ld = config.last_dispatch
            if ld.channel and (ld.user_id or ld.session_id):
                # Dispatch all events to last channel
                async for event in runner.stream_query(req):
                    await channel_manager.send_event(
                        channel=ld.channel,
                        user_id=ld.user_id,
                        session_id=ld.session_id,
                        event=event,
                        meta={},
                    )
                logger.info("heartbeat dispatched to last channel (target=last)")
            else:
                # No last_dispatch available, run without dispatch
                async for _ in runner.stream_query(req):
                    pass
                logger.debug("heartbeat completed (target=last, no last_dispatch)")
        else:
            # For target="auto" or target="main": Just run agent
            # For "auto", LLM may call send_to_channel tool which handles dispatch
            async for _ in runner.stream_query(req):
                pass

            if is_auto:
                send_state = getattr(send_tool, "_heartbeat_state", {})
                if send_state.get("called"):
                    logger.info(
                        "heartbeat completed (target=auto, dispatched=%s)",
                        send_state.get("sent", False),
                    )
                else:
                    logger.info(
                        "heartbeat completed (target=auto, no dispatch attempted)"
                    )
            else:
                logger.debug("heartbeat completed (target=main, no dispatch)")

    try:
        await asyncio.wait_for(_run(), timeout=120)
    except asyncio.TimeoutError:
        logger.warning("heartbeat run timed out")
    except Exception:
        logger.exception("heartbeat run failed")
        raise