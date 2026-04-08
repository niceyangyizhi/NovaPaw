#!/usr/bin/env python3
"""
Migration Script: TASK-004 (JSON) -> TASK-007 (Unified YAML+MD)
Converts legacy `long_term.json` to `long_term.md` with authority tracking.
"""
import json
import uuid
from datetime import date
from pathlib import Path
import yaml

LEGACY_JSON = Path("/Users/yanghao/.novapaw/memory/long_term.json")
NEW_MD = Path("/Users/yanghao/.novapaw/memory/long_term.md")

def migrate():
    if not LEGACY_JSON.exists():
        print("✅ No legacy JSON found. Migration skipped.")
        return

    with open(LEGACY_JSON, "r", encoding="utf-8") as f:
        try:
            legacy_data = json.load(f)
        except json.JSONDecodeError:
            print("❌ Legacy JSON is corrupted. Aborting.")
            return

    # Handle v1.0 structure {"version": "1.0", "entries": [...]}
    raw_list = legacy_data.get("entries", []) if isinstance(legacy_data, dict) else legacy_data

    # Convert to new format
    entries = []
    for idx, item in enumerate(raw_list):
        entries.append({
            "id": item.get("id", f"mem_{idx:03d}"),
            "date": date.today().isoformat(),
            "entity": item.get("entity", "未知实体"),
            "source": "auto_extract",
            "authority": 0.6,
            "tags": item.get("tags", ["preference"]),
            "status": "milestone",
            "archived": False,
            "content": item.get("content", "")
        })

    yaml_header = yaml.dump(entries, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    output = f"""---
{yaml_header}---

# 📝 缓冲区 / 原始上下文
> 迁移自 legacy long_term.json。等待下次 Heartbeat 压缩。
- 历史条目已统一标记为 auto_extract (权威度 0.6)
- 请核实并手动修正 entity 与 authority 字段。
"""

    NEW_MD.parent.mkdir(parents=True, exist_ok=True)
    NEW_MD.write_text(output, encoding="utf-8")
    print(f"✅ Migration complete: {LEGACY_JSON} -> {NEW_MD}")
    print(f"📦 Total entries migrated: {len(entries)}")
    print("⚠️ Next Step: Run Heartbeat Compaction to verify entities & authorities.")

if __name__ == "__main__":
    migrate()
