"""
NovaPaw Memory Loader (V2.0)
Funnel injection pipeline: loads Day/Week/Month/LongTerm layers,
applies status filtering, respects token budget, and assembles System Prompt context.
"""
import json
import os
import tiktoken
from typing import List, Dict, Tuple
from pathlib import Path
from .memory_schema import MemoryEntry, MemoryStatus
from .memory_store import MemoryStore


# Token budget limits (10k tokens)
DEFAULT_TOKEN_BUDGET = 10000

class TokenCounter:
    """Lazy-loaded token counter to ensure tiktoken is available."""
    _encoder = None

    @classmethod
    def get_encoder(cls):
        if cls._encoder is None:
            try:
                cls._encoder = tiktoken.encoding_for_model("gpt-4o") # o200k_base compatible
            except Exception:
                try:
                    cls._encoder = tiktoken.get_encoding("cl100k_base")
                except Exception:
                    print("⚠️ tiktoken init failed, falling back to rough estimation.")
                    cls._encoder = "fallback"
        return cls._encoder

    @classmethod
    def count(cls, text: str) -> int:
        enc = cls.get_encoder()
        if enc == "fallback":
            # Conservative fallback: 1.5 tokens per Chinese char, 0.25 per English word
            # Rough estimate: len(text) * 0.75
            return int(len(text) * 0.8)
        return len(enc.encode(text))


class MemoryLoader:
    def __init__(self, base_memory_dir: str, token_budget: int = DEFAULT_TOKEN_BUDGET):
        self.base_dir = Path(base_memory_dir)
        self.token_budget = token_budget

    def inject_context(self) -> str:
        """
        Main pipeline: Load funnel layers -> Priority Assembly -> Budget Control.
        优先级：LongTerm > Monthly > Weekly > Daily
        """
        context_parts = []
        
        # 1. Define Priority Layers (High to Low)
        # Note: We load LongTerm FIRST so it's safe from truncation.
        layers = [
            ("long_term", 1),
            ("monthly", 3),
            ("weekly", 2),
            ("daily", 3)
        ]

        budget_exceeded = False

        for layer_name, limit in layers:
            if budget_exceeded:
                break

            files = self._get_layer_files(layer_name, limit)
            # Reverse files for daily/weekly to get most recent first? 
            # _get_layer_files already returns sorted files. 
            # For daily, we usually want the 3 most recent days.
            
            # However, since we are filling into context_parts, the order matters.
            # If we iterate layers: LongTerm -> Month -> Week -> Day.
            # Within a layer (e.g. Daily), should we add Day 1 then Day 2? Yes.
            
            for f_path in files:
                block = self._load_block(layer_name, f_path)
                if not block:
                    continue
                
                # Check budget before adding this block? 
                # Or add and then truncate? 
                # Better strategy: Add, check, truncate the LAST item if budget exceeded.
                
                current_total_text = "\n\n".join(context_parts + [block])
                if TokenCounter.count(current_total_text) > self.token_budget:
                    print(f"⚠️ Memory budget limit reached at layer: {layer_name}")
                    
                    # Attempt to truncate this specific block to fit remaining space
                    current_total = TokenCounter.count("\n\n".join(context_parts))
                    remaining_budget = self.token_budget - current_total
                    
                    # Approximation: encode the block
                    block_tokens = TokenCounter.count(block)
                    
                    if block_tokens > remaining_budget:
                        # Truncate block to fit (using token indices is hard without decoding, 
                        # so we fallback to char ratio estimation for the cut point)
                        ratio = remaining_budget / max(block_tokens, 1)
                        cut_len = int(len(block) * ratio * 0.95) # 0.95 safety margin
                        block = block[:cut_len] + f"\n\n[... Memory truncated: {layer_name} ...]"
                        context_parts.append(block)
                        budget_exceeded = True
                        break
                    else:
                        context_parts.append(block)
                else:
                    context_parts.append(block)

        full_text = "\n\n".join(context_parts)
        return full_text if full_text else "无可用记忆上下文。"

    def _get_layer_files(self, layer_name: str, limit: int) -> List[Path]:
        """Sort and slice layer files by recency."""
        if layer_name == "long_term":
            candidates = [
                self.base_dir / "MEMORY.md",
                self.base_dir / "long_term.md",
                self.base_dir / "memory" / "MEMORY.md",
                self.base_dir / "memory" / "long_term.md",
            ]
            return [path for path in candidates if path.exists()][:1]

        layer_dirs = [
            self.base_dir / layer_name,
            self.base_dir / "memory" / layer_name,
        ]
        files: list[Path] = []
        for layer_dir in layer_dirs:
            if not layer_dir.exists():
                continue
            files.extend(path for path in layer_dir.rglob("*.md") if path.is_file())
            files.extend(path for path in layer_dir.rglob("*.json") if path.is_file())
        unique_files = sorted({path for path in files}, key=lambda x: x.name, reverse=True)
        return unique_files[:limit]

    def _load_block(self, layer_name: str, f_path: Path) -> str:
        """Load one memory layer block from either YAML+MD or legacy JSON."""
        if f_path.suffix == ".json":
            return self._load_json_block(layer_name, f_path)

        store = MemoryStore(str(f_path))
        data = store.load()
        active_entries = [e for e in data.entries if not e.archived]
        if not active_entries and not data.buffer_text.strip():
            return ""
        return self._format_block(layer_name, active_entries, data.buffer_text)

    def _load_json_block(self, layer_name: str, f_path: Path) -> str:
        """Load legacy JSON daily-memory artifacts into funnel context."""
        try:
            payload = json.loads(f_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️ Failed to parse JSON memory file {f_path.name}: {e}")
            return ""

        summary = (payload.get("summary") or "").strip()
        content = (payload.get("content") or "").strip()
        date = payload.get("date") or payload.get("session_id") or f_path.stem

        if not summary and not content:
            return ""

        lines = [f"## [{layer_name.upper()}] 记忆摘要", f"- **{date}** {summary or content}"]
        if content and content != summary:
            lines.append(f"\n### 📝 {layer_name} 原始观察\n{content}")
        return "\n".join(lines)

    def _format_block(self, layer_name: str, entries: List[MemoryEntry], buffer: str) -> str:
        """Format entries into a clean Markdown block for LLM injection."""
        if not entries:
            return f"## [{layer_name.upper()}] 缓冲区\n{buffer}"

        lines = [f"## [{layer_name.upper()}] 结构化记忆"]
        for e in entries:
            tags = ", ".join([t.value if hasattr(t, 'value') else str(t) for t in e.tags])
            lines.append(
                f"- **【{e.entity} | {e.date} | {e.source} (权威:{e.authority})】** "
                f"`[{tags}]` {e.content}"
            )
        
        if buffer.strip():
            lines.append(f"\n### 📝 {layer_name} 原始观察\n{buffer}")
            
        return "\n".join(lines)
