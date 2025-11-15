"""
人机协同工具
实现 Claude Code 的人工审查机制
"""
from langchain_core.tools import tool
from langgraph.types import interrupt


ASK_HUMAN_DESCRIPTION = """当需要向用户确认需求、询问补充信息、向用户提问或请求权限时，务必调用此工具。

使用场景：
1. 需要用户确认操作（如删除文件、修改重要代码）
2. 需要用户提供额外信息（如配置参数、设计决策）
3. 遇到歧义，需要用户澄清需求
4. 需要用户做出选择（如多个解决方案）
5. 执行敏感操作前需要获得明确许可

此工具会暂停执行，等待用户响应。用户响应后，您将收到用户的回复并继续执行。
"""


@tool(description=ASK_HUMAN_DESCRIPTION)
def ask_human(question: str) -> str:
    """
    向用户询问问题

    Args:
        question: 要询问的问题

    Returns:
        用户的回答
    """
    # 使用 interrupt 暂停执行，等待用户输入
    user_response = interrupt(
        {
            "type": "human_input_required",
            "question": question,
            "instructions": "Please provide your response to continue."
        }
    )

    # 如果用户提供了响应，返回响应内容
    if isinstance(user_response, dict):
        return user_response.get("response", "No response provided")
    elif isinstance(user_response, str):
        return user_response
    else:
        return str(user_response)


def get_human_loop_tools() -> list:
    """获取人机协同工具列表"""
    return [ask_human]
