# -*- coding: utf-8 -*-
"""Heartbeat-specific tools (auto mode only)."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Coroutine, Any

from agentscope.tool import ToolResponse
from agentscope.message import Msg, TextBlock

if TYPE_CHECKING:
    from ..channels.manager import ChannelManager
    from ..config.config import LastDispatchConfig
    from ..runner.session import SafeJSONSession

logger = logging.getLogger(__name__)


async def save_heartbeat_messages(
    session: "SafeJSONSession",
    session_id: str,
    query_text: str,
    response_text: str,
) -> None:
    """Save heartbeat interaction to daily session if message was sent.

    Args:
        session: SafeJSONSession instance for state management
        session_id: Today's session ID (YYYY-MM-DD)
        query_text: The HEARTBEAT.md query text
        response_text: The content sent to user
    """
    if not session_id:
        logger.warning("save_heartbeat_messages: session_id is empty, skip saving")
        return

    try:
        # Create message objects
        user_msg = Msg(
            name="user",
            role="user",
            content=[TextBlock(type="text", text=query_text)],
        )
        assistant_msg = Msg(
            name="heartbeat",
            role="assistant",
            content=[TextBlock(type="text", text=response_text)],
        )

        # Save user query
        await session.update_session_state(
            session_id=session_id,
            key="heartbeat_messages.user",
            value=user_msg.to_dict(),
            create_if_not_exist=True,
        )

        # Save assistant response
        await session.update_session_state(
            session_id=session_id,
            key="heartbeat_messages.assistant",
            value=assistant_msg.to_dict(),
            create_if_not_exist=True,
        )

        logger.info(
            "Heartbeat messages saved to session %s (query_len=%d, response_len=%d)",
            session_id,
            len(query_text),
            len(response_text),
        )
    except Exception:
        logger.exception(
            "Failed to save heartbeat messages to session %s",
            session_id,
        )


def create_send_to_channel_tool(
    channel_manager: "ChannelManager",
    config: Any,  # Config object, using Any to avoid circular import
    session: "SafeJSONSession | None" = None,
    today_session_id: str | None = None,
    query_text: str | None = None,
) -> Callable[..., Coroutine[Any, Any, ToolResponse]]:
    """
    Create send_to_channel tool with bound context.

    Args:
        channel_manager: Channel manager for sending messages
        config: Config object containing last_dispatch info
        session: Optional SafeJSONSession for saving heartbeat messages
        today_session_id: Today's session ID (YYYY-MM-DD format)
        query_text: The HEARTBEAT.md query text (for saving to session)

    Returns:
        Async function that can be registered as a tool
    """

    state = {"called": False, "sent": False}

    async def send_to_channel(content: str) -> ToolResponse:
        """
        将心跳回复发送给用户。

        使用场景：
        - 有行动项、待办、任务需要提醒用户
        - 有重要信息或用户等待的内容
        - 有建议或提醒值得用户注意

        不要使用的场景：
        - 纯确认性回复（如"好的"、"收到了"）
        - 无实质内容的"无更新"
        - 重复之前的内容

        Args:
            content (`str`): 要发送的内容

        Returns:
            `ToolResponse`: 发送结果
        """
        state["called"] = True

        # Get last_dispatch with safe attribute access
        ld = getattr(config, 'last_dispatch', None)

        # Validate last_dispatch
        if not ld:
            logger.warning("send_to_channel: last_dispatch is None")
            return ToolResponse(
                content=[TextBlock(type="text", text="错误：没有上次对话记录")]
            )

        # Type-safe attribute access for LastDispatchConfig
        channel = getattr(ld, 'channel', None)
        user_id = getattr(ld, 'user_id', None)
        session_id = getattr(ld, 'session_id', None)

        if not channel:
            logger.warning("send_to_channel: channel is None")
            return ToolResponse(
                content=[TextBlock(type="text", text="错误：没有可用的频道")]
            )

        if not (user_id or session_id):
            logger.warning("send_to_channel: both user_id and session_id are None")
            return ToolResponse(
                content=[TextBlock(type="text", text="错误：没有可用的用户或会话")]
            )

        # Log the tool call
        logger.info(
            "send_to_channel called: channel=%s, user_id=%s, content_len=%d",
            channel,
            user_id[:8] + "..." if user_id and len(user_id) > 8 else user_id,
            len(content),
        )

        try:
            await channel_manager.send_text(
                channel=channel,
                user_id=user_id,
                session_id=session_id,
                text=content,
                meta={},
            )
            state["sent"] = True
            logger.info("send_to_channel: message sent successfully")

            # Save heartbeat messages to daily session (if session provided)
            if session and today_session_id and query_text:
                await save_heartbeat_messages(
                    session=session,
                    session_id=today_session_id,
                    query_text=query_text,
                    response_text=content,
                )

            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"消息已发送到 {channel}",
                    )
                ]
            )
        except Exception as e:
            logger.exception("send_to_channel: failed to send message")
            return ToolResponse(
                content=[TextBlock(type="text", text=f"发送失败：{e}")]
            )

    send_to_channel._heartbeat_state = state
    return send_to_channel