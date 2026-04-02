# Heartbeat Tests

单元测试覆盖 heartbeat 模块的核心功能。

## 测试文件

### `test_heartbeat_tools.py`

测试 `send_to_channel` 工具的创建和执行逻辑。

**覆盖场景**：
- ✅ 发送成功
- ✅ 无 last_dispatch（不发送）
- ✅ 无 channel（不发送）
- ✅ 无 user_id/session_id（不发送）
- ✅ 发送异常处理
- ✅ 各种内容类型（空/长/多行）
- ✅ 工具签名验证

**运行测试**：
```bash
cd ~/NovaPaw
python -m pytest tests/unit/app/test_heartbeat_tools.py -v
```

### `test_heartbeat.py`

测试 heartbeat 模块的工具函数和配置。

**覆盖场景**：
- ✅ `parse_heartbeat_every` - 间隔解析
- ✅ `_in_active_hours` - 活跃时段判断
- ✅ `build_heartbeat_auto_system_prompt()` - system prompt 验证

**运行测试**：
```bash
cd ~/NovaPaw
python -m pytest tests/unit/app/test_heartbeat.py -v
```

## 运行所有 heartbeat 测试

```bash
cd ~/NovaPaw
python -m pytest tests/unit/app/test_heartbeat*.py -v
```

## 测试覆盖率

```bash
cd ~/NovaPaw
python -m pytest tests/unit/app/test_heartbeat*.py --cov=novapaw.app.crons --cov-report=term-missing
```

## Mock 对象说明

### `MockChannelManager`
模拟 channel manager，记录发送的消息但不实际发送。

### `MockChannelManagerWithError`
模拟发送时总是抛出异常的 channel manager。

### `MockConfig`
模拟 config 对象，可配置 last_dispatch 属性。

### `MockConfigNoLastDispatch`
模拟没有 last_dispatch 的 config 对象。

### `MockConfigPartial`
模拟 partia l last_dispatch 的 config 对象（缺失 channel 或 user_id/session_id）。

## 测试设计原则

1. **隔离性** - 每个测试独立，不依赖其他测试的状态
2. **可重复性** - 使用 mock 对象，不依赖外部环境
3. **覆盖边界** - 测试成功、失败、边界条件
4. **断言明确** - 每个测试有清晰的验证逻辑
