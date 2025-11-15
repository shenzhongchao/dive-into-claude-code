"""
压缩逻辑模块
实现 Claude Code 的 8 段式压缩策略
"""
from datetime import datetime
from typing import Sequence
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage

from prompts.compression_prompts import (
    get_compression_prompt,
    format_compression_result,
    get_compression_system_prompt
)
from utils.token_counter import get_latest_token_usage, estimate_tokens


def get_messages_to_keep(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """
    获取需要保留的消息（最近的几条）

    Claude Code 的保留策略：
    - 保留最近的 3-5 条消息
    - 保留系统消息
    - 保留重要的用户消息

    Args:
        messages: 消息列表

    Returns:
        需要保留的消息列表
    """
    if len(messages) <= 5:
        return list(messages)

    keep_messages = []

    # 保留系统消息
    for msg in messages:
        if isinstance(msg, SystemMessage):
            keep_messages.append(msg)

    # 保留最近的 3 条消息
    recent_messages = list(messages[-3:])
    for msg in recent_messages:
        if msg not in keep_messages:
            keep_messages.append(msg)

    return keep_messages


def get_messages_to_compress(
    messages: Sequence[BaseMessage]
) -> tuple[list[BaseMessage], list[BaseMessage]]:
    """
    分离需要压缩的消息和需要保留的消息

    Args:
        messages: 消息列表

    Returns:
        (需要压缩的消息, 需要保留的消息)
    """
    keep_messages = get_messages_to_keep(messages)
    keep_ids = {id(msg) for msg in keep_messages}

    compress_messages = [
        msg for msg in messages
        if id(msg) not in keep_ids and not isinstance(msg, SystemMessage)
    ]

    return compress_messages, keep_messages


async def compress_messages(
    llm,
    messages: Sequence[BaseMessage]
) -> tuple[str, dict]:
    """
    使用 LLM 压缩消息

    实现 Claude Code 的 8 段式压缩：
    1. Primary Request and Intent
    2. Key Technical Concepts
    3. Files and Code Sections
    4. Errors and Fixes
    5. Problem Solving
    6. All User Messages
    7. Pending Tasks
    8. Current Work
    9. Optional Next Step

    Args:
        llm: 语言模型
        messages: 要压缩的消息列表

    Returns:
        (压缩后的摘要, 统计信息)
    """
    # 构建压缩提示词
    compression_prompt = get_compression_prompt()

    # 构建用于压缩的消息上下文
    context_messages = [
        SystemMessage(content=get_compression_system_prompt())
    ]

    # 添加历史消息
    context_messages.extend(messages)

    # 添加压缩请求
    context_messages.append(
        HumanMessage(content=compression_prompt)
    )

    # 调用 LLM 进行压缩
    try:
        response = await llm.ainvoke(context_messages)
        summary = response.content

        # 格式化压缩结果
        formatted_summary = format_compression_result(summary)

        # 计算统计信息
        original_tokens = estimate_tokens(messages)
        compressed_tokens = estimate_tokens([AIMessage(content=formatted_summary)])

        stats = {
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "saved_tokens": original_tokens - compressed_tokens,
            "compression_ratio": (
                (original_tokens - compressed_tokens) / original_tokens * 100
                if original_tokens > 0 else 0
            ),
            "timestamp": datetime.now().isoformat()
        }

        return formatted_summary, stats

    except Exception as e:
        # 压缩失败，返回简单摘要
        fallback_summary = "# Conversation Summary\n\nPrevious conversation compressed due to context length."
        return fallback_summary, {
            "original_tokens": estimate_tokens(messages),
            "compressed_tokens": len(fallback_summary) // 3,
            "error": str(e)
        }


def should_compress_now(
    messages: Sequence[BaseMessage],
    max_tokens: int,
    threshold: float = 0.92
) -> bool:
    """
    判断是否应该立即压缩

    Args:
        messages: 消息列表
        max_tokens: 最大 token 数
        threshold: 压缩阈值

    Returns:
        是否应该压缩
    """
    current_tokens = get_latest_token_usage(messages)
    trigger_tokens = int(max_tokens * threshold)

    return current_tokens >= trigger_tokens


class CompressionManager:
    """压缩管理器"""

    def __init__(self, llm, max_tokens: int = 100000, threshold: float = 0.92):
        """
        初始化压缩管理器

        Args:
            llm: 语言模型
            max_tokens: 最大 token 数
            threshold: 压缩阈值
        """
        self.llm = llm
        self.max_tokens = max_tokens
        self.threshold = threshold
        self.compression_history = []

    async def compress_if_needed(
        self,
        messages: Sequence[BaseMessage]
    ) -> tuple[bool, list[BaseMessage], dict]:
        """
        如果需要则压缩消息

        Args:
            messages: 消息列表

        Returns:
            (是否进行了压缩, 新的消息列表, 统计信息)
        """
        # 检查是否需要压缩
        if not should_compress_now(messages, self.max_tokens, self.threshold):
            return False, list(messages), {}

        print("🔄 Context compression triggered (usage > 92%)")

        # 分离消息
        compress_msgs, keep_msgs = get_messages_to_compress(messages)

        if not compress_msgs:
            return False, list(messages), {}

        # 执行压缩
        summary, stats = await compress_messages(self.llm, compress_msgs)

        # 构建新的消息列表
        new_messages = []

        # 保留系统消息
        for msg in messages:
            if isinstance(msg, SystemMessage):
                new_messages.append(msg)

        # 添加压缩摘要
        new_messages.append(AIMessage(content=summary))

        # 添加保留的消息
        for msg in keep_msgs:
            if msg not in new_messages:
                new_messages.append(msg)

        # 记录压缩历史
        self.compression_history.append({
            **stats,
            "removed_messages_count": len(compress_msgs)
        })

        print(f"✅ Compression completed: {stats.get('compression_ratio', 0):.1f}% saved")

        return True, new_messages, stats
