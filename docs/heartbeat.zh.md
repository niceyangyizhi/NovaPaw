# 心跳

「心跳」在 NovaPaw 里指的是：**按固定间隔，用你写好的一段「问题」去问 NovaPaw，并可选择把 NovaPaw 的回复发到你上次对话的频道**。适合做「定期自检、每日摘要、定时提醒」——不用你主动发消息，NovaPaw 到点就干活。

如果你还没看过 [项目介绍](./intro)，建议先看一眼那里对「心跳」和「频道」的说明。

---

## 心跳是怎么工作的？

1. 你有一个文件 **HEARTBEAT.md**（默认在工作目录 `~/.novapaw/` 下），里面写的是**每次心跳要问 NovaPaw 的内容**（一段或几段话都行，NovaPaw 会当成一条用户消息）。
2. 系统按你配置的**间隔**（例如每 30 分钟）执行一次：读取 HEARTBEAT.md → 用这段内容去问 NovaPaw → NovaPaw 回复。
3. **发不发到频道** 由配置里的 **target** 决定：
   - **main**：只跑 NovaPaw，不把回复发到任何频道（适合只做「自检」、结果自己看日志或别处）。
   - **last**：把 NovaPaw 的回复发到你**上次和 NovaPaw 对话的那个频道/会话**（例如上次你在钉钉和它聊，这次心跳的回复就发到钉钉）。
   - **auto**：NovaPaw 自行判断是否有价值发送。它会根据回复内容决定是否调用 `send_to_channel` 工具，只有在有行动项、重要提醒或实质性内容时才会发送消息给你。

还可以设置 **active hours**（活跃时段）：只在每天的某段时间内跑心跳（例如 08:00–22:00），其余时间不跑。

---

## 第一步：写 HEARTBEAT.md

文件路径默认是 `~/.novapaw/HEARTBEAT.md`。内容就是「每次要问 NovaPaw 什么」，纯文本或 Markdown 都行，NovaPaw 会整体当作一条用户消息。

示例（你可以按自己需求改）：

```markdown
# Heartbeat checklist

- 扫描收件箱紧急邮件
- 查看未来 2h 的日历
- 检查待办是否卡住
- 若安静超过 8h，轻量 check-in
```

初始化时如果执行过 `novapaw init`（没加 `--defaults`），会提示你是否编辑 HEARTBEAT.md；选是会用系统默认编辑器打开。你也可以之后随时用任何编辑器改这个文件，保存即可，下次心跳会用到新内容。

---

## 第二步：在 config.json 里配置心跳

心跳的**间隔、发到哪、活跃时段**都在 `config.json` 里，路径一般是 `~/.novapaw/config.json`。

在 `agents.defaults.heartbeat` 下可以配置：

| 字段        | 含义                       | 示例                                         |
| ----------- | -------------------------- | -------------------------------------------- |
| every       | 间隔多久跑一次             | `"30m"`、`"1h"`、`"2h30m"`、`"90s"`          |
| target      | 回复发到哪                 | `"main"` 不发送；`"last"` 发到上次对话的频道；`"auto"` 自动判断是否发送 |
| activeHours | 可选，只在每天这段时间内跑 | `{ "start": "08:00", "end": "22:00" }`       |

示例（只跑 NovaPaw、不发到频道，每 30 分钟）：

```json
"agents": {
  "defaults": {
    "heartbeat": {
      "every": "30m",
      "target": "main"
    }
  }
}
```

示例（发到上次对话的频道，每 1 小时，且只在 08:00–22:00 跑）：

```json
"agents": {
  "defaults": {
    "heartbeat": {
      "every": "1h",
      "target": "last",
      "activeHours": { "start": "08:00", "end": "22:00" }
    }
  }
}
```

改完保存 config.json；若服务在跑，会按新配置生效（部分实现可能需重启，以实际为准）。

---

## target="auto" 模式（推荐）

`target="auto"` 让 NovaPaw 自行判断心跳回复是否有价值发送给你，避免「无更新」类消息打扰。

### 工作原理

当 `target="auto"` 时，NovaPaw 会：

1. **注册 `send_to_channel` 工具** —— 这是一个专门用于发送心跳消息的工具
2. **添加系统提示** —— 指导 LLM 在什么情况下应该调用此工具
3. **LLM 自主决策** —— LLM 根据回复内容决定是否调用工具发送消息

### Tool 参数

```json
{
  "name": "send_to_channel",
  "description": "将心跳回复发送给用户",
  "parameters": {
    "type": "object",
    "properties": {
      "content": {
        "type": "string",
        "description": "要发送的内容"
      }
    },
    "required": ["content"]
  }
}
```

### 判断标准

**LLM 被指导在以下情况调用工具（发送）**：
- ✅ 有行动项、待办、任务需要提醒用户
- ✅ 有重要提醒或建议值得用户注意
- ✅ 有用户等待的信息或新发现
- ✅ 有具体的下一步建议

**LLM 被指导在以下情况不调用工具（不发送）**：
- ❌ 纯确认性回复（如"好的"、"收到了"、"无更新"）
- ❌ 没有实质内容的回复
- ❌ 重复之前的内容

### 配置示例

```json
"agents": {
  "defaults": {
    "heartbeat": {
      "every": "6h",
      "target": "auto",
      "activeHours": { "start": "10:00", "end": "23:00" }
    }
  }
}
```

### 优势

| 优势 | 说明 |
|------|------|
| **真正智能** | LLM 理解完整上下文，不是关键词匹配 |
| **零额外调用** | 心跳本来就要调用 LLM，只是多一个 tool 选项 |
| **部分可观测** | 可以从 tool 调用与 heartbeat 日志看出是否尝试发送、是否发送成功 |
| **架构优雅** | 复用现有 tool calling 机制，无需特殊逻辑 |

### 日志示例

```
# LLM 决定发送并发送成功
INFO send_to_channel called: channel=dingtalk, user_id=user123..., content_len=42
INFO send_to_channel: message sent successfully
INFO heartbeat completed (target=auto, dispatched=True)

# LLM 决定不发送
INFO heartbeat completed (target=auto, no dispatch attempted)
```

---

## 和「定时任务」的区别

|          | 心跳                       | 定时任务 (cron)              |
| -------- | -------------------------- | ---------------------------- |
| **数量** | 只有一份（HEARTBEAT.md）   | 可以建很多个                 |
| **间隔** | 一个全局间隔               | 每个独立设定时间             |
| **投递** | 可选发到「上次频道」或不发 | 每个独立指定频道和用户       |
| **适用** | 固定的一套自检/摘要        | 多条不同时间、不同内容的任务 |

> 需要「每天 9 点发早安」「每 2 小时问待办并发到钉钉」这类多条任务？用 [CLI](./cli) 的 `novapaw cron create` 做定时任务，不用心跳。

---

## 相关页面

- [项目介绍](./intro) — 这个项目可以做什么
- [频道配置](./channels) — 先接好频道，target=last 才有「上次频道」可发
- [CLI](./cli) — init 时配置心跳、cron 定时任务
- [配置与工作目录](./config) — config.json 与工作目录
