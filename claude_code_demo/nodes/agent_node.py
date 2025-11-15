"""
Agent 节点
实现主 Agent 的调用逻辑
"""
from langchain_core.messages import SystemMessage
from core.state import AgentState
from prompts.system_prompts import get_main_system_prompt


async def agent_node(state: AgentState, llm, tools: list) -> dict:
    """
    Agent 节点：调用 LLM 生成响应

    Args:
        state: 当前状态（Pydantic 实例）
        llm: 语言模型
        tools: 工具列表

    Returns:
        更新的状态
    """
    # 使用属性访问而不是字典访问
    messages = state.messages
    todo_count = len(state.todo_list)

    # 构建系统提示词
    system_prompt = get_main_system_prompt(todo_count)

    # 准备消息列表
    input_messages = list(messages)  # 转换为列表以便修改

    # 如果没有系统消息，添加系统消息
    has_system_msg = any(
        isinstance(msg, SystemMessage) for msg in input_messages
    )

    if not has_system_msg:
        input_messages.insert(0, SystemMessage(content=system_prompt))

    # 绑定工具到 LLM
    llm_with_tools = llm.bind_tools(tools)

    # 调用 LLM（简化版本：直接使用 ainvoke）
    response = await llm_with_tools.ainvoke(input_messages)

    return {"messages": [response]}


def create_agent_node(llm, tools: list):
    """
    创建 Agent 节点函数

    Args:
        llm: 语言模型
        tools: 工具列表

    Returns:
        Agent 节点函数
    """
    async def node(state: AgentState) -> dict:
        return await agent_node(state, llm, tools)

    return node
