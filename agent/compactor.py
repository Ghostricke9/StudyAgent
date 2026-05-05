"""
上下文压缩组件 - 三层上下文窗口管理

Agent 工作越久，messages 数组越臃肿，Token 压力持续增长。
三层压缩按"无感→重压缩→自救"递进：

  Layer 1: micro_compact()   — 每轮自动运行，裁剪旧的 tool 结果，对 LLM 无感
  Layer 2: auto_compact()    — 超过 Token 阈值自动触发，LLM 摘要后替换全部历史
  Layer 3: manual_compact()  — LLM 主动请求压缩，生成摘要后替换全部历史
"""
import json
import logging
import os
import time

from config import KEEP_RECENT_TOOLS, COMPACT_TOKEN_THRESHOLD, TRANSCRIPT_DIR

logger = logging.getLogger(__name__)


def estimate_tokens(messages: list[dict]) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        total = 0
        for msg in messages:
            total += 4
            for key, value in msg.items():
                if isinstance(value, str):
                    total += len(enc.encode(value))
                elif isinstance(value, list):
                    total += len(enc.encode(json.dumps(value, ensure_ascii=False)))
        return total
    except ImportError:
        total = 0
        for msg in messages:
            total += 4
            for value in msg.values():
                if isinstance(value, str):
                    total += len(value) // 3
                elif isinstance(value, list):
                    total += len(json.dumps(value, ensure_ascii=False)) // 3
        return total


def micro_compact(messages: list[dict]) -> list[dict]:
    tool_indices = [
        i for i, msg in enumerate(messages)
        if msg["role"] == "tool"
    ]

    if len(tool_indices) <= KEEP_RECENT_TOOLS:
        return messages

    for idx in tool_indices[:-KEEP_RECENT_TOOLS]:
        content = messages[idx].get("content", "")
        if len(content) > 150:
            tool_name = ""
            snippet = content[:100].replace("\n", " ").strip()
            messages[idx]["content"] = f"[已压缩 原工具结果过长] {snippet}..."

    logger.debug(
        f"micro_compact: {len(tool_indices)} 条 tool 消息，"
        f"裁剪前 {len(tool_indices) - KEEP_RECENT_TOOLS} 条，"
        f"保留最近 {min(len(tool_indices), KEEP_RECENT_TOOLS)} 条"
    )
    return messages


def auto_compact(messages: list[dict], llm) -> list[dict]:
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    transcript_path = os.path.join(TRANSCRIPT_DIR, f"transcript_{int(time.time())}.jsonl")
    with open(transcript_path, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg, ensure_ascii=False, default=str) + "\n")
    logger.info(f"对话存档已保存: {transcript_path}")

    payload = json.dumps(messages, ensure_ascii=False, default=str)
    summary_prompt = (
        "请将以下对话历史压缩为一份连续摘要。保留：\n"
        "1. 用户最初的需求和目标\n"
        "2. 已完成的关键步骤和结果\n"
        "3. 当前进行中的任务和进度\n"
        "4. 被压缩的工具结果中仍需保留的核心信息\n"
        "忽略被标记为 [已压缩] 的中间过程细节。\n\n"
        f"对话历史:\n{payload[:80000]}"
    )

    try:
        response = llm.chat(
            messages=[{"role": "user", "content": summary_prompt}],
            tools=None,
        )
        choice = response.choices[0]
        summary = choice.message.content or "(摘要生成失败)"
    except Exception as e:
        logger.exception("auto_compact: LLM 摘要生成失败")
        summary = f"(上下文压缩失败: {e})"

    logger.info(
        f"auto_compact: {len(messages)} 条消息 → 1 条摘要 "
        f"({len(payload)} → {len(summary)} 字符)"
    )

    return [
        {
            "role": "system",
            "content": f"[对话已压缩]\n\n以下是对此前对话的摘要，请基于此继续工作：\n\n{summary}",
        }
    ]


def manual_compact(messages: list[dict], llm) -> list[dict]:
    return auto_compact(messages, llm)
