"""
图构建模块
整合所有组件构建完整的 Agent 图
"""
from typing import Literal
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from langchain_core.messages import ToolMessage

from core.state import AgentState
from config import ClaudeCodeConfig
from tools.base_tools import get_base_tools
from tools.todo_tools import get_todo_tools
from tools.human_loop_tool import get_human_loop_tools
from tools.task_tool import create_task_tool
from nodes.agent_node import create_agent_node
from nodes.compression_node import create_compression_node
from utils.compression import CompressionManager


# 需要人工确认的工具列表
TOOLS_REQUIRING_APPROVAL = [
    "write_file",
    "edit_file",
    # 可以根据需要添加其他敏感工具
]


def should_continue(state: AgentState) -> Literal["tools", "approval", "compression", END]:
    """
    决定下一步：调用工具、人工确认、压缩还是结束

    Args:
        state: 当前状态（Pydantic 实例）

    Returns:
        下一个节点名称
    """
    # 使用属性访问而不是字典访问
    messages = state.messages
    last_message = messages[-1]

    # 检查是否有工具调用
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # 检查是否需要审批
        needs_approval = any(
            tc["name"] in TOOLS_REQUIRING_APPROVAL
            for tc in last_message.tool_calls
        )
        if needs_approval:
            return "approval"
        return "tools"

    # 检查是否需要压缩
    if state.needs_compression:
        return "compression"

    return END


def approval_node(state: AgentState) -> dict:
    """
    人工确认节点：在执行敏感工具前请求用户确认

    Args:
        state: 当前状态（Pydantic 实例）

    Returns:
        状态更新字典
    """
    messages = state.messages
    last_message = messages[-1]

    # 检查是否有工具调用
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    tool_calls = last_message.tool_calls

    # 构建确认信息
    tool_descriptions = []
    for tc in tool_calls:
        if tc["name"] in TOOLS_REQUIRING_APPROVAL:
            args_str = ", ".join(
                f"{k}={repr(v)[:50]}" for k, v in tc["args"].items()
            )
            tool_descriptions.append(f"  - {tc['name']}({args_str})")

    if not tool_descriptions:
        return {}

    confirmation_message = (
        f"⚠️ 以下敏感操作需要您的批准:\n\n"
        + "\n".join(tool_descriptions) + "\n\n"
        + "是否继续? (yes/no)"
    )

    # 触发 interrupt，等待用户确认
    user_response = interrupt(
        {
            "type": "tool_approval_required",
            "message": confirmation_message,
            "tool_calls": [
                {"name": tc["name"], "args": tc["args"]}
                for tc in tool_calls
                if tc["name"] in TOOLS_REQUIRING_APPROVAL
            ]
        }
    )

    # 检查用户响应
    if user_response:
        response_text = str(user_response).lower().strip()
        if response_text not in ["yes", "y", "确认", "是"]:
            # 用户拒绝，返回拒绝消息
            rejection_messages = [
                ToolMessage(
                    content="操作已被用户取消",
                    tool_call_id=tc.get("id") or tc.get("tool_call_id", "unknown")
                )
                for tc in tool_calls
                if tc["name"] in TOOLS_REQUIRING_APPROVAL
            ]
            return {"messages": rejection_messages}

    # 用户同意或默认同意，不修改状态，继续执行
    return {}


def build_graph(config: ClaudeCodeConfig, llm) -> StateGraph:
    """
    构建 Claude Code Agent 图

    Args:
        config: 配置
        llm: 语言模型

    Returns:
        编译后的图
    """
    # 1. 准备工具
    base_tools = get_base_tools()
    todo_tools = get_todo_tools()
    human_loop_tools = get_human_loop_tools()

    # 创建 Task 工具（SubAgent）
    task_tool = create_task_tool(
        llm,
        base_tools,
        config.subagent
    )

    # 所有工具
    all_tools = base_tools + todo_tools + human_loop_tools + [task_tool]

    # 2. 创建节点
    agent_node = create_agent_node(llm, all_tools)

    # 直接使用 ToolNode，不使用包装器
    # 注意：人工确认功能暂时禁用，可以通过其他方式实现
    tool_node = ToolNode(all_tools)
    # tool_node = create_tool_node(all_tools)

    # 创建压缩管理器和节点
    compression_manager = CompressionManager(
        llm,
        max_tokens=config.token.max_context_tokens,
        threshold=config.token.compression_threshold
    )
    compression_node = create_compression_node(compression_manager)

    # 3. 构建图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("approval", approval_node)  # 新增人工确认节点
    workflow.add_node("compression", compression_node)

    # 添加边
    # START -> compression -> agent
    # compression 节点会检查是否需要压缩，如果需要就压缩，否则返回空更新
    workflow.add_edge(START, "compression")
    workflow.add_edge("compression", "agent")

    # agent -> should_continue (tools/approval/compression/END)
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        ["tools", "approval", "compression", END]
    )

    # approval -> tools (用户确认后执行工具)
    workflow.add_edge("approval", "tools")

    # tools -> compression check -> agent
    workflow.add_edge("tools", "compression")

    # 4. 创建检查点
    if config.checkpoint.provider == "memory":
        checkpointer = MemorySaver()
    else:
        # TODO: 支持 Redis/PostgreSQL
        checkpointer = MemorySaver()

    # 5. 编译图
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=[]  # 可以在这里配置需要中断的节点
    )

    return app


def visualize_graph(app) -> bytes:
    """
    可视化图结构

    Args:
        app: 编译后的图

    Returns:
        图的 PNG 字节数据
    """
    try:
        return app.get_graph().draw_mermaid_png()
    except Exception as e:
        print(f"Failed to visualize graph: {e}")
        return None
