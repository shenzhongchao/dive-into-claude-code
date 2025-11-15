"""
Token 计数工具
实现 Claude Code 的 Token 监控机制
"""
from typing import Sequence
from langchain_core.messages import BaseMessage, AIMessage


def get_latest_token_usage(messages: Sequence[BaseMessage]) -> int:
    """
    获取最新的 Token 使用量（倒序查找优化）

    这是 Claude Code 的核心优化：从最新消息开始查找，
    因为 usage 信息通常在最近的 AI 消息中

    Args:
        messages: 消息列表

    Returns:
        总 Token 数
    """
    # 倒序扫描，找到最新的 usage 信息
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]

        # 检查是否是 AI 消息且包含 usage 信息
        if isinstance(msg, AIMessage):
            # 检查 response_metadata 中的 usage
            if hasattr(msg, 'response_metadata') and msg.response_metadata:
                usage = msg.response_metadata.get('usage')
                if usage:
                    # 计算总 token（包括缓存）
                    total = (
                        usage.get('total_tokens', 0) +
                        usage.get('cache_creation_tokens', 0) +
                        usage.get('cache_read_tokens', 0)
                    )
                    return total

            # 检查 usage_metadata
            if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                total = (
                    msg.usage_metadata.get('total_tokens', 0) +
                    msg.usage_metadata.get('cache_creation_tokens', 0) +
                    msg.usage_metadata.get('cache_read_tokens', 0)
                )
                return total

    # 如果没有找到 usage 信息，使用估算
    return estimate_tokens(messages)


def estimate_tokens(messages: Sequence[BaseMessage]) -> int:
    """
    估算消息的 Token 数

    简单估算：英文约 4 字符 = 1 token，中文约 1.5 字符 = 1 token

    Args:
        messages: 消息列表

    Returns:
        估算的 Token 数
    """
    total_chars = 0

    for msg in messages:
        if isinstance(msg.content, str):
            total_chars += len(msg.content)
        elif isinstance(msg.content, list):
            for item in msg.content:
                if isinstance(item, dict) and 'text' in item:
                    total_chars += len(item['text'])

    # 保守估算：平均 3 字符 = 1 token
    return total_chars // 3


def needs_compression(
    current_tokens: int,
    max_tokens: int,
    threshold: float = 0.92,
    reserved_output: int = 4096
) -> bool:
    """
    判断是否需要压缩

    Claude Code 的 92% 阈值策略：
    - 当使用率超过 92% 时触发压缩
    - 预留输出 token（默认 4096）

    Args:
        current_tokens: 当前 Token 数
        max_tokens: 最大 Token 数
        threshold: 压缩阈值（默认 0.92）
        reserved_output: 预留输出 Token（默认 4096）

    Returns:
        是否需要压缩
    """
    # 可用 token = 最大 token - 预留输出 token
    available_tokens = max_tokens - reserved_output

    # 计算使用率
    usage_ratio = current_tokens / available_tokens

    return usage_ratio >= threshold


def calculate_compression_stats(
    original_tokens: int,
    compressed_tokens: int
) -> dict:
    """
    计算压缩统计信息

    Args:
        original_tokens: 原始 Token 数
        compressed_tokens: 压缩后 Token 数

    Returns:
        压缩统计信息
    """
    saved_tokens = original_tokens - compressed_tokens
    compression_ratio = (
        (saved_tokens / original_tokens * 100)
        if original_tokens > 0
        else 0
    )

    return {
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "saved_tokens": saved_tokens,
        "compression_ratio": f"{compression_ratio:.1f}%"
    }


class TokenMonitor:
    """Token 监控器"""

    def __init__(self, max_tokens: int = 100000, threshold: float = 0.92):
        """
        初始化 Token 监控器

        Args:
            max_tokens: 最大 Token 数
            threshold: 压缩阈值
        """
        self.max_tokens = max_tokens
        self.threshold = threshold
        self.reserved_output = 4096

    def get_current_usage(self, messages: Sequence[BaseMessage]) -> dict:
        """获取当前使用情况"""
        current = get_latest_token_usage(messages)
        available = self.max_tokens - self.reserved_output
        percentage = (current / available) * 100

        return {
            "used": current,
            "available": available,
            "total": self.max_tokens,
            "percentage": f"{percentage:.1f}%",
            "needs_compression": needs_compression(
                current,
                self.max_tokens,
                self.threshold,
                self.reserved_output
            )
        }

    def should_compress(self, messages: Sequence[BaseMessage]) -> bool:
        """判断是否应该压缩"""
        current = get_latest_token_usage(messages)
        return needs_compression(
            current,
            self.max_tokens,
            self.threshold,
            self.reserved_output
        )
