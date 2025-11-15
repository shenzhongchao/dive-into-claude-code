"""
压缩节点
实现上下文压缩逻辑
"""
from datetime import datetime
from core.state import AgentState, CompressionRecord
from utils.compression import CompressionManager


async def compression_node(
    state: AgentState,
    compression_manager: CompressionManager
) -> dict:
    """
    压缩节点：检查并执行上下文压缩

    Args:
        state: 当前状态（Pydantic 实例）
        compression_manager: 压缩管理器

    Returns:
        更新的状态
    """
    # 使用属性访问而不是字典访问
    messages = state.messages

    # 检查是否需要压缩
    compressed, new_messages, stats = await compression_manager.compress_if_needed(
        messages
    )

    if not compressed:
        # 不需要压缩，返回空更新
        return {}

    # 创建压缩记录（使用 Pydantic 模型）
    compression_record = CompressionRecord(
        timestamp=datetime.now().isoformat(),
        original_tokens=stats.get("original_tokens", 0),
        compressed_tokens=stats.get("compressed_tokens", 0),
        compression_ratio=stats.get("compression_ratio", 0),
        removed_messages_count=stats.get("removed_messages_count", 0)
    )

    return {
        "messages": new_messages,
        "compression_history": list(state.compression_history) + [compression_record],
        "needs_compression": False
    }


def create_compression_node(compression_manager: CompressionManager):
    """
    创建压缩节点函数

    Args:
        compression_manager: 压缩管理器

    Returns:
        压缩节点函数
    """
    async def node(state: AgentState) -> dict:
        return await compression_node(state, compression_manager)

    return node
