# 📝 Rollover Prompt (Daily/Weekly Summary Generation)

## 🎯 任务
生成今日/周记忆摘要，严格遵循 YAML+MD 格式。输出将直接进入漏斗管线。

## ⚠️ 强制规范 (P0)
1. **实体隔离**：绝对禁止使用孤立代词（他/她/它/对方/这人）。必须使用完整姓名或项目代号。
   - ❌ `她回复了冷淡内容` -> ✅ `[程姗姗] -> [回复"衢州"] -> [极度冷淡]`
2. **强类型约束**：YAML 键名不可更改，枚举值不可越界。
   - `status`: `routine` | `milestone` | `critical`
   - `tags`: `development`, `relationship`, `wealth`, `learning`, `lifestyle`, `health`, `review`, `tools`, `preference`
3. **结构化句式**：使用 `[主体] -> [行为/状态] -> [结果/决策]` 格式记录关键事件。

## 📄 输出模板
```markdown
---
- id: {{uuid}}
  date: {{today}}
  entity: "{{FULL_NAME}}"
  source: daily_summary
  authority: 0.6
  tags: [{{tag1}}, {{tag2}}]
  status: {{routine|milestone|critical}}
  content: "{{结构化摘要，≤50字}}"
---

# 📝 原始笔记 / 上下文缓冲区
> 此处记录待验证观察、原始对话片段、情绪标记或临时假设。
> 保持精简，下次 Heartbeat 将触发压缩。
- 观察: ...
- 证据: ...
```

## 💡 提示
- `routine` 仅留档，不上报高层漏斗。
- `critical` 将触发全量上下文注入，谨慎使用。
- 若发生状态变更，在 `content` 末尾追加 `⚠️ State Change: 旧 -> 新`。
