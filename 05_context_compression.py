"""
第5章：上下文压缩 - 8段式压缩算法

实现 Claude Code 的上下文压缩机制
"""
import os
from typing import TypedDict, List, Annotated, Literal
from datetime import datetime

# LangGraph
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# LangChain
from langchain_core.tools import tool
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    AIMessage,
    BaseMessage,
    RemoveMessage,
    ToolMessage
)

# LLM
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatTongyi


# ============================================================================
# 1. 配置
# ============================================================================

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_PROJECT"] = "chapter-05-context-compression"

# 初始化LLM
# llm = ChatOpenAI(model="gpt-5", temperature=0)
llm = ChatTongyi(model="qwen-max", temperature=0)
print(f"✅ LLM初始化成功: {llm.model_name}")


# ============================================================================
# 2. Token 监控机制
# ============================================================================

def get_latest_token_usage(messages: List[BaseMessage]) -> int:
    """倒序查找最新的token使用情况

    这是一个优化的实现，避免遍历所有消息。
    从最新的消息开始查找，因为token usage信息通常在最近的AIMessage中。

    Args:
        messages: 消息列表

    Returns:
        最新的token使用总数
    """
    # 倒序扫描，找到最新的usage信息
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, 'response_metadata'):
            usage = msg.response_metadata.get('token_usage', {})

            if usage:
                # 精确计算：包含所有token类型
                total = usage.get('total_tokens', 0)
                if total > 0:
                    return total

    # 如果没有找到usage信息，返回0
    return 0


def estimate_tokens(messages: List[BaseMessage]) -> int:
    """估算token数量（当没有精确token_usage时使用）

    粗略估算：1 token ≈ 4 个字符（英文）或 1.5 个字符（中文）

    Args:
        messages: 消息列表

    Returns:
        估算的token总数
    """
    total_chars = 0

    for msg in messages:
        if hasattr(msg, 'content') and msg.content:
            total_chars += len(str(msg.content))

    # 使用保守估算（假设中英文混合）
    return int(total_chars / 3)


# ============================================================================
# 3. 压缩判断逻辑
# ============================================================================

TOKEN_THRESHOLD = 0.92  # 92% 阈值

def needs_compression(
    messages: List[BaseMessage],
    max_tokens: int = 128000,  # Claude Sonnet 3.5上下文窗口
    reserved_output: int = 4000  # 为输出预留的token
) -> bool:
    """判断是否需要压缩

    综合考虑：
    1. 当前token使用量
    2. 模型上下文窗口大小
    3. 预留的输出空间

    Args:
        messages: 消息列表
        max_tokens: 最大token数
        reserved_output: 为输出预留的token数

    Returns:
        是否需要压缩
    """
    threshold = TOKEN_THRESHOLD
    # 获取当前token使用量
    current_tokens = get_latest_token_usage(messages)

    # 如果没有精确的usage信息，使用估算
    if current_tokens == 0:
        current_tokens = estimate_tokens(messages)

    # 计算可用token（减去预留的输出空间）
    available_tokens = max_tokens - reserved_output

    # 计算使用率
    usage_ratio = current_tokens / available_tokens

    print(f"📊 Token使用情况:")
    print(f"   当前: {current_tokens:,} tokens")
    print(f"   可用: {available_tokens:,} tokens")
    print(f"   使用率: {usage_ratio:.1%}")
    print(f"   阈值: {threshold:.1%}")

    return usage_ratio > threshold


# ============================================================================
# 4. 8段式压缩提示词
# ============================================================================

COMPRESSION_PROMPT = """你的任务是创建到目前为止对话的详细摘要，密切关注用户的明确请求和你之前的行动。
此摘要应彻底捕获技术细节、代码模式和架构决策，这些对于在不丢失上下文的情况下继续开发工作至关重要。

在提供最终摘要之前，将你的分析包装在<analysis>标签中，以组织你的思考并确保你涵盖了所有必要的要点。

你的摘要应包括以下部分:

1. **主要请求和意图**: 详细捕获用户的所有明确请求和意图
   - 用户明确说了什么？
   - 任务的核心目标是什么？
   - 有哪些隐含的需求？

2. **关键技术概念**: 列出讨论的所有重要技术概念、技术和框架
   - 使用了哪些技术栈？
   - 涉及哪些核心概念？
   - 有哪些重要的架构决策？

3. **文件和代码段**: 枚举检查、修改或创建的特定文件和代码段
   - 特别注意最近的消息
   - 包含完整的代码片段（如适用）
   - 记录文件路径和关键行号

4. **错误和修复**: 列出你遇到的所有错误以及修复方法
   - 具体的错误信息
   - 解决方案和原因
   - 特别注意用户的反馈

5. **问题解决**: 记录已解决的问题和任何正在进行的故障排除工作
   - 解决了哪些难题？
   - 采用了什么方法？
   - 还有哪些未解决的问题？

6. **所有用户消息**: 列出所有非工具结果的用户消息
   - 这些对于理解用户的反馈和变化的意图至关重要
   - 按时间顺序列出
   - 注意用户态度和需求的变化

7. **待处理任务**: 概述你明确被要求处理的任何待处理任务
   - 哪些任务还没完成？
   - 优先级如何？
   - 有哪些依赖关系？

8. **当前工作**: 详细描述在此摘要请求之前正在进行的确切工作
   - 最后在做什么？
   - 进展到哪一步了？
   - 下一步计划做什么？

9. **可选的下一步**: 列出与你最近正在做的工作相关的下一步
   - 逻辑上的下一步是什么？
   - 有哪些可能的方向？

请确保摘要足够详细，使得另一个AI助手（或你自己在新会话中）能够无缝地继续这个对话和工作。
"""


# ============================================================================
# 5. 状态定义
# ============================================================================

class CompressionRecord(TypedDict):
    """压缩记录"""
    timestamp: str
    messages_removed: int
    messages_kept: int
    tokens_before: int
    tokens_after: int
    summary_content: str


class AgentState(TypedDict):
    """扩展的Agent状态

    包含：
    - messages: 对话历史
    - compression_history: 压缩历史
    """
    messages: Annotated[List[BaseMessage], add_messages]
    compression_history: List[CompressionRecord]  # 不需要 reducer，直接替换


# ============================================================================
# 6. 压缩节点实现
# ============================================================================

def compression_node(state: AgentState) -> dict:
    """上下文压缩节点

    工作流程：
    1. 检查是否需要压缩
    2. 如果不需要，直接返回空字典
    3. 如果需要，调用LLM生成摘要
    4. 删除旧消息，保留最近消息和摘要
    5. 记录压缩历史到compression_history

    Args:
        state: 当前状态

    Returns:
        更新后的状态（messages字段和compression_history字段）
    """
    messages = state.get("messages", [])

    print("\n" + "="*60)
    print("🗜️  压缩节点执行")
    print("="*60)

    # 1. 检查是否需要压缩
    if not needs_compression(messages):
        print("✅ Token使用率在安全范围内，无需压缩")
        return {}

    print("⚠️  Token使用率超过阈值，开始压缩...")

    # 记录压缩前的token数量
    tokens_before = get_latest_token_usage(messages)
    if tokens_before == 0:
        tokens_before = estimate_tokens(messages)

    # 2. 调用LLM生成压缩摘要
    try:
        print("📝 生成8段式压缩摘要...")

        # 构建压缩请求
        compression_messages = [
            SystemMessage(content=COMPRESSION_PROMPT),
            *messages  # 包含完整对话历史
        ]

        # 调用LLM
        summary_response = llm.invoke(compression_messages)
        summary_content = summary_response.content

        print(f"✅ 摘要生成完成，长度: {len(summary_content)} 字符")

        # 3. 决定保留多少最近消息
        # 策略：保留最近3条消息
        keep_recent = 3

        if len(messages) <= keep_recent:
            print("⚠️  消息数量较少，不进行压缩")
            return {}

        # 4. 构建新的消息列表
        # 删除旧消息，保留最近的消息
        messages_to_remove = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        # 如果拆分点下一条是ToolMessage, 将该条message也删除
        if recent_messages and isinstance(recent_messages[0], ToolMessage):
            messages_to_remove.append(recent_messages[0])
            recent_messages = recent_messages[1:]

        # 创建摘要消息
        summary_message = AIMessage(
            content=f"""📋 **对话摘要** (压缩于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

{summary_content}

---
*以上是之前 {len(messages_to_remove)} 条消息的摘要，以下是最近的对话*
"""
        )

        print(f"🗑️  删除旧消息: {len(messages_to_remove)} 条")
        print(f"📌 保留最近消息: {len(recent_messages)} 条")
        print(f"📄 添加摘要: 1 条")

        # 5. 返回更新
        # 使用RemoveMessage删除旧消息
        remove_messages = [RemoveMessage(id=msg.id) for msg in messages_to_remove if hasattr(msg, 'id')]

        # 计算压缩后的token数量
        new_messages_for_count = recent_messages + [summary_message]
        tokens_after = estimate_tokens(new_messages_for_count)

        # 6. 创建压缩记录
        compression_record: CompressionRecord = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "messages_removed": len(messages_to_remove),
            "messages_kept": len(recent_messages),
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "summary_content": summary_content[:200] + "..." if len(summary_content) > 200 else summary_content
        }

        # 7. 获取现有的压缩历史并添加新记录
        compression_history = state.get("compression_history", [])

        print(f"📊 压缩统计:")
        print(f"   压缩前: {tokens_before:,} tokens")
        print(f"   压缩后: {tokens_after:,} tokens")
        print(f"   节省: {tokens_before - tokens_after:,} tokens ({(tokens_before - tokens_after) / tokens_before * 100:.1f}%)")

        # 返回更新的完整列表
        return {
            "messages": remove_messages + [summary_message],
            "compression_history": compression_history + [compression_record]
        }

    except Exception as e:
        print(f"❌ 压缩失败: {e}")
        print("继续执行，不进行压缩")
        return {}


# ============================================================================
# 7. 测试工具定义
# ============================================================================

@tool
def search_docs(query: str) -> str:
    """搜索文档（模拟）

    Args:
        query: 搜索关键词
    """
    return f"找到关于'{query}'的文档：\n1. 文档A - 这是一篇关于{query}的详细介绍...\n2. 文档B - {query}的最佳实践..."


@tool
def analyze_code(code: str) -> str:
    """分析代码（模拟）

    Args:
        code: 要分析的代码
    """
    return f"代码分析结果：\n- 代码行数: {len(code.split())}\n- 复杂度: 中等\n- 建议: 可以进一步优化..."


tools = [search_docs, analyze_code]
llm_with_tools = llm.bind_tools(tools)


# ============================================================================
# 8. Agent 节点定义
# ============================================================================

def agent_node(state: AgentState):
    """Agent节点：调用LLM"""
    messages = state["messages"]

    # 添加系统提示
    system_msg = SystemMessage(
        content="你是一个智能助手，可以搜索文档和分析代码。请帮助用户解决问题。"
    )

    response = llm_with_tools.invoke([system_msg] + list(messages))
    return {"messages": [response]}


def tool_node(state: AgentState):
    """工具节点：执行工具"""
    tools_by_name = {t.name: t for t in tools}
    last_message = state["messages"][-1]

    results = []
    for tool_call in last_message.tool_calls:
        tool_func = tools_by_name[tool_call["name"]]
        result = tool_func.invoke(tool_call["args"])
        results.append(ToolMessage(
            content=str(result),
            tool_call_id=tool_call["id"]
        ))

    return {"messages": results}


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """判断是否继续"""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


# ============================================================================
# 9. 构建图
# ============================================================================

def build_graph():
    """构建带压缩功能的Agent图"""
    builder = StateGraph(AgentState)

    # 添加节点
    builder.add_node("compression", compression_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)

    # 添加边
    builder.add_edge(START, "compression")
    builder.add_edge("compression", "agent")

    # agent的条件边
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )

    # tools执行后回到compression检查
    builder.add_edge("tools", "compression")

    # 编译
    graph = builder.compile()

    print("✅ 图构建完成")
    return graph


# ============================================================================
# 10. 测试函数
# ============================================================================

def test_short_conversation():
    """测试1：短对话（不触发压缩）"""
    print("="*60)
    print("测试1：短对话 - 不应触发压缩")
    print("="*60)

    graph = build_graph()

    result = graph.invoke({
        "messages": [HumanMessage(content="搜索关于LangGraph的文档")],
        "compression_history": []
    })

    print("\n最终回答:")
    print(result["messages"][-1].content)
    print(f"\n消息总数: {len(result['messages'])}")
    print(f"压缩次数: {len(result.get('compression_history', []))}")


def test_long_conversation():
    """测试2：长对话（触发压缩）"""
    global TOKEN_THRESHOLD
    TOKEN_THRESHOLD = 0.01  # 降低阈值以触发压缩

    print("\n" + "="*60)
    print("测试2：长对话模拟 - 应触发压缩")
    print("="*60)

    graph = build_graph()

    questions = [
        "搜索LangGraph的基础概念",
        "分析以下代码：def hello(): pass",
        "搜索StateGraph的用法",
        "搜索ToolNode的实现",
        "搜索MessagesState的定义",
        "搜索条件边的使用",
        "搜索interrupt机制",
        "搜索checkpointer的配置"
    ]

    state = {"messages": [], "compression_history": []}

    for i, question in enumerate(questions, 1):
        print(f"\n{'='*60}")
        print(f"第 {i} 轮对话: {question}")
        print(f"{'='*60}")

        # 添加用户消息
        state["messages"] = list(state["messages"]) + [HumanMessage(content=question)]

        # 执行
        result = graph.invoke(state)
        state = result

        print(f"\n当前消息数: {len(state['messages'])}")
        print(f"压缩次数: {len(state.get('compression_history', []))}")

    print("\n" + "="*60)
    print("长对话测试完成")
    print("="*60)
    print(f"最终消息数: {len(state['messages'])}")
    print(f"总压缩次数: {len(state.get('compression_history', []))}")

    # 显示压缩历史摘要
    if state.get('compression_history'):
        print("\n压缩历史摘要:")
        for i, record in enumerate(state['compression_history'], 1):
            print(f"\n第 {i} 次压缩:")
            print(f"  时间: {record['timestamp']}")
            print(f"  删除消息: {record['messages_removed']} 条")
            print(f"  保留消息: {record['messages_kept']} 条")
            saved = record['tokens_before'] - record['tokens_after']
            ratio = (saved / record['tokens_before'] * 100) if record['tokens_before'] > 0 else 0
            print(f"  节省: {saved:,} tokens ({ratio:.1f}%)")


# ============================================================================
# 11. 主函数
# ============================================================================

def main():
    """主函数"""
    # 测试1：短对话
    # test_short_conversation()

    # 测试2：长对话
    test_long_conversation()


if __name__ == "__main__":
    main()
