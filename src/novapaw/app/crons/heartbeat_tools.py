# -*- coding: utf-8 -*-
"""Heartbeat-specific tools (auto mode only)."""

import logging
from typing import TYPE_CHECKING, Callable, Coroutine, Any

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

if TYPE_CHECKING:
    from ..channels.manager import ChannelManager
    from ..config.config import LastDispatchConfig

logger = logging.getLogger(__name__)


def create_send_to_channel_tool(
    channel_manager: "ChannelManager",
    config: Any,  # Config object, using Any to avoid circular import
) -> Callable[..., Coroutine[Any, Any, ToolResponse]]:
    """
    Create send_to_channel tool with bound context.

    Args:
        channel_manager: Channel manager for sending messages
        config: Config object containing last_dispatch info

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
