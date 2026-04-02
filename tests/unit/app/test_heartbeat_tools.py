# -*- coding: utf-8 -*-
"""Unit tests for heartbeat_tools module."""
from __future__ import annotations

import pytest
from types import SimpleNamespace
from agentscope.tool import ToolResponse

from novapaw.app.crons.heartbeat_tools import create_send_to_channel_tool


class MockChannelManager:
    """Mock channel manager for testing."""

    def __init__(self):
        self.sent_messages = []

    async def send_text(
        self,
        channel: str,
        user_id: str,
        session_id: str,
        text: str,
        meta: dict,
    ) -> None:
        """Record sent message for verification."""
        self.sent_messages.append({
            "channel": channel,
            "user_id": user_id,
            "session_id": session_id,
            "text": text,
            "meta": meta,
        })


class MockChannelManagerWithError:
    """Mock channel manager that raises exception."""

    async def send_text(
        self,
        channel: str,
        user_id: str,
        session_id: str,
        text: str,
        meta: dict,
    ) -> None:
        """Always raise exception."""
        raise RuntimeError("Connection failed")


class MockConfig:
    """Mock config with last_dispatch."""

    def __init__(
        self,
        channel: str = "dingtalk",
        user_id: str = "user123",
        session_id: str = "session456",
    ):
        self.last_dispatch = SimpleNamespace(
            channel=channel,
            user_id=user_id,
            session_id=session_id,
        )


class MockConfigNoLastDispatch:
    """Mock config without last_dispatch."""

    def __init__(self):
        self.last_dispatch = None


class MockConfigPartial:
    """Mock config with partial last_dispatch."""

    def __init__(self, missing: str = "channel"):
        if missing == "channel":
            self.last_dispatch = SimpleNamespace(
                channel=None,
                user_id="user123",
                session_id="session456",
            )
        elif missing == "user_and_session":
            self.last_dispatch = SimpleNamespace(
                channel="dingtalk",
                user_id=None,
                session_id=None,
            )
        else:
            self.last_dispatch = None


# =============================================================================
# Test: Successful message sending
# =============================================================================


async def test_send_to_channel_success() -> None:
    """Test successful message sending."""
    channel_manager = MockChannelManager()
    config = MockConfig()

    send_tool = create_send_to_channel_tool(channel_manager, config)
    response = await send_tool("测试消息内容")

    # Verify response
    assert isinstance(response, ToolResponse)
    assert len(response.content) == 1
    assert response.content[0].type == "text"
    assert "消息已发送" in response.content[0].text
    assert "dingtalk" in response.content[0].text

    # Verify message was sent
    assert len(channel_manager.sent_messages) == 1
    msg = channel_manager.sent_messages[0]
    assert msg["channel"] == "dingtalk"
    assert msg["user_id"] == "user123"
    assert msg["session_id"] == "session456"
    assert msg["text"] == "测试消息内容"
    assert msg["meta"] == {}


async def test_send_to_channel_with_long_user_id() -> None:
    """Test message sending with long user_id (logging truncation)."""
    channel_manager = MockChannelManager()
    config = MockConfig(user_id="very_long_user_id_12345678901234567890")

    send_tool = create_send_to_channel_tool(channel_manager, config)
    response = await send_tool("短消息")

    assert isinstance(response, ToolResponse)
    assert len(channel_manager.sent_messages) == 1


# =============================================================================
# Test: No last_dispatch (should not send)
# =============================================================================


async def test_send_to_channel_no_last_dispatch() -> None:
    """Test when last_dispatch is None."""
    channel_manager = MockChannelManager()
    config = MockConfigNoLastDispatch()

    send_tool = create_send_to_channel_tool(channel_manager, config)
    response = await send_tool("测试消息")

    # Verify error response
    assert isinstance(response, ToolResponse)
    assert len(response.content) == 1
    assert response.content[0].type == "text"
    assert "错误" in response.content[0].text
    assert "没有上次对话记录" in response.content[0].text

    # Verify no message was sent
    assert len(channel_manager.sent_messages) == 0


# =============================================================================
# Test: Partial last_dispatch (should not send)
# =============================================================================


async def test_send_to_channel_no_channel() -> None:
    """Test when channel is None."""
    channel_manager = MockChannelManager()
    config = MockConfigPartial(missing="channel")

    send_tool = create_send_to_channel_tool(channel_manager, config)
    response = await send_tool("测试消息")

    assert isinstance(response, ToolResponse)
    assert "错误" in response.content[0].text
    assert "没有可用的频道" in response.content[0].text
    assert len(channel_manager.sent_messages) == 0


async def test_send_to_channel_no_user_or_session() -> None:
    """Test when both user_id and session_id are None."""
    channel_manager = MockChannelManager()
    config = MockConfigPartial(missing="user_and_session")

    send_tool = create_send_to_channel_tool(channel_manager, config)
    response = await send_tool("测试消息")

    assert isinstance(response, ToolResponse)
    assert "错误" in response.content[0].text
    assert "没有可用的用户或会话" in response.content[0].text
    assert len(channel_manager.sent_messages) == 0


# =============================================================================
# Test: Exception handling
# =============================================================================


async def test_send_to_channel_exception() -> None:
    """Test exception during message sending."""
    channel_manager = MockChannelManagerWithError()
    config = MockConfig()

    send_tool = create_send_to_channel_tool(channel_manager, config)
    response = await send_tool("测试消息")

    # Verify error response contains exception info
    assert isinstance(response, ToolResponse)
    assert len(response.content) == 1
    assert response.content[0].type == "text"
    assert "发送失败" in response.content[0].text
    assert "Connection failed" in response.content[0].text


# =============================================================================
# Test: Content variations
# =============================================================================


async def test_send_to_channel_empty_content() -> None:
    """Test with empty content."""
    channel_manager = MockChannelManager()
    config = MockConfig()

    send_tool = create_send_to_channel_tool(channel_manager, config)
    response = await send_tool("")

    assert isinstance(response, ToolResponse)
    assert len(channel_manager.sent_messages) == 1
    assert channel_manager.sent_messages[0]["text"] == ""


async def test_send_to_channel_long_content() -> None:
    """Test with long content."""
    channel_manager = MockChannelManager()
    config = MockConfig()
    long_content = "A" * 1000

    send_tool = create_send_to_channel_tool(channel_manager, config)
    response = await send_tool(long_content)

    assert isinstance(response, ToolResponse)
    assert len(channel_manager.sent_messages) == 1
    assert channel_manager.sent_messages[0]["text"] == long_content


async def test_send_to_channel_multiline_content() -> None:
    """Test with multiline content."""
    channel_manager = MockChannelManager()
    config = MockConfig()
    content = """第一行
第二行
第三行"""

    send_tool = create_send_to_channel_tool(channel_manager, config)
    response = await send_tool(content)

    assert isinstance(response, ToolResponse)
    assert len(channel_manager.sent_messages) == 1
    assert channel_manager.sent_messages[0]["text"] == content


# =============================================================================
# Test: Tool function signature
# =============================================================================


async def test_send_to_channel_only_accepts_content() -> None:
    """Test that tool only accepts content parameter (no priority)."""
    channel_manager = MockChannelManager()
    config = MockConfig()

    send_tool = create_send_to_channel_tool(channel_manager, config)

    # Should work with just content
    response = await send_tool(content="测试")
    assert isinstance(response, ToolResponse)

    # Verify no priority parameter is expected
    import inspect
    sig = inspect.signature(send_tool)
    params = list(sig.parameters.keys())
    assert params == ["content"]
