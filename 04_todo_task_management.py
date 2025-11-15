"""
第4章：TodoList任务管理 - 终极优雅版 (InjectedState + ToolNode)

这是 LangGraph 推荐的、用于管理自定义 State 的最终实现方式。
它完全依赖预构建的 ToolNode 来自动处理状态的读取和写入。

关键技术点：
1. todo_read 使用 InjectedState 读取 state["todo_list"]
2. todo_write 使用 InjectedState 写入 state["todo_list"]
3. 直接使用 ToolNode，无需任何包装器 (Wrapper)
4. ToolNode 自动检测到 state 的修改，并将其作为节点输出

运行方式：
    python 04_todo_elegant_solution.py
"""
import os
import sys
import uuid
from datetime import datetime
from typing import Annotated, List, Optional
from enum import Enum

# LangGraph
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import InjectedState, ToolNode 
from langgraph.types import Command
from typing_extensions import TypedDict # 类型定义qwen3-max会出错
from pydantic import BaseModel, Field # 改用更鲁棒的方式

# LangChain
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, ToolMessage

# LLM (选择一个)
# from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatTongyi


# ============================================================================
# 1. 数据结构定义
# ============================================================================

class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TodoItem(BaseModel):
    # LLM 如果忘记提供 ID，default_factory 会自动创建一个
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    # 必填字段
    name: str 
    # 字段默认值
    desc: str = ""
    status: TaskStatus = TaskStatus.PENDING # 自动默认为 "pending"
    # 可选字段
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    error: Optional[str] = None


class AgentState(BaseModel):
    """
    Pydantic 版本的 Agent 状态。
    """
    # 关键优势 3: 在 Pydantic 中使用 LangGraph 的 Reducer
    # 语法是 "Annotated[TYPE, REDUCER] = Field(default_factory=...)"
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)
    
    # 我们的自定义状态
    todo_list: List[TodoItem] = Field(default_factory=list)


# ============================================================================
# 1.5. 辅助函数
# ============================================================================

def format_todo_list(todo_list: List[TodoItem]) -> str:
    """
    将 todo_list 格式化为美观的、人类可读的字符串。
    
    - 仅显示 id, name, desc, status
    - 按 status 分组
    """
    if not todo_list:
        return "✅ 任务列表为空。"

    # 1. 按状态分组
    by_status = {
        "in_progress": [],
        "pending": [],
        "completed": [],
        "failed": []
    }
    
    for task in todo_list:
        status = task.status
        if status not in by_status: # 捕获无效的状态
            status = "pending"
        by_status[status].append(task)

    # 2. 定义状态标题和表情
    status_headers = {
        "in_progress": "🔄 进行中 (In-Progress):",
        "pending": "⏳ 待处理 (Pending):",
        "completed": "✅ 已完成 (Completed):",
        "failed": "❌ 失败 (Failed):"
    }
    
    result_lines = ["\n" + "=" * 30 + " 任务列表 " + "=" * 30]
    has_content = False

    # 3. 按期望的顺序构建输出
    for status, header in status_headers.items():
        tasks = by_status[status]
        
        if tasks:
            has_content = True
            result_lines.append(f"\n{header}")
            for task in tasks:
                # 仅包含 id, name, desc
                task_id = task.id
                task_name = task.name
                task_desc = task.desc
                
                result_lines.append(f"  [{task_id}] {task_name}")
                result_lines.append(f"      描述: {task_desc}")
            
    result_lines.append("\n" + "=" * 62)

    if not has_content:
        return "✅ 任务列表为空。"
        
    return "\n".join(result_lines)

def _validate_todo_list(todo_list: List[TodoItem]) -> List[TodoItem]:
    """
    验证和处理 Pydantic 任务列表。
    
    Pydantic 已经完成了：
    1. 类型检查 (例如, name 必须是 str)
    2. 默认值 (id, status, desc)
    
    我们只需要处理 *业务逻辑*，比如根据状态设置时间戳。
    """
    current_time = datetime.now().isoformat()
    
    # Pydantic 模型是可变的 (mutable)，我们可以直接修改它们
    for task in todo_list:
        
        # 业务逻辑：设置开始/结束时间戳
        if task.status == TaskStatus.IN_PROGRESS and not task.start_time:
            task.start_time = current_time
            
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] and not task.end_time:
            task.end_time = current_time

    # 返回已修改的 Pydantic 对象列表
    return todo_list
# ============================================================================
# 2. 工具定义（使用 InjectedState）
# ============================================================================

@tool
def todo_read(state: Annotated[AgentState, InjectedState]) -> str:
    """读取当前会话的任务列表

    主动且频繁地使用此工具，以确保你了解当前任务列表的状态。
    你应该尽可能多地使用此工具，特别是在：
    - 开始工作之前
    - 完成任务后
    - 不确定下一步做什么时

    Args:
        state: Agent 状态（通过 InjectedState 自动注入）

    Returns:
        格式化的任务列表
    """
    todo_list = state.todo_list

    if not todo_list:
        return "任务列表为空。如果用户给了复杂任务，请使用 todo_write 创建任务列表。"

    # 格式化输出 (内容不变)
    result = ["当前任务列表:\n"]
    by_status = {"in_progress": [], "pending": [], "completed": [], "failed": []}
    for task in todo_list:
        status = task.status
        by_status[status].append(task)
    
    if by_status["in_progress"]:
        result.append("🔄 进行中:")
        for task in by_status["in_progress"]:
            result.append(f"  [{task.id}] {task.name}")
        result.append("")
    if by_status["pending"]:
        result.append("⏳ 待处理:")
        for task in by_status["pending"]:
            result.append(f"  [{task.id}] {task.name}")
        result.append("")
    if by_status["completed"]:
        result.append("✅ 已完成:")
        for task in by_status["completed"]:
            result.append(f"  [{task.id}] {task.name}")
        result.append("")
    if by_status["failed"]:
        result.append("❌ 失败:")
        for task in by_status["failed"]:
            result.append(f"  [{task.id}] {task.name}")
        result.append("")
    result.append(f"\n总计: {len(todo_list)} 个任务")

    return "\n".join(result)


@tool
def todo_write(
    todo_list: List[TodoItem],
    state: Annotated[AgentState, InjectedState], # 为了演示，可以删掉
    tool_call_id: Annotated[str, InjectedToolCallId]
):
    """更新当前会话的任务列表

    主动使用此工具来跟踪进度和管理任务执行。

    ## 何时使用此工具
    在以下场景中主动使用此工具：
    1. 收到复杂的多步骤任务时 - 立即分解为子任务
    2. 开始执行任务时 - 将任务标记为 in_progress
    3. 完成任务后 - 将任务标记为 completed
    4. 遇到错误时 - 将任务标记为 failed 并记录错误

    ## 任务状态管理
    1. **任务状态**: 使用这些状态来跟踪进度：
       - pending: 任务尚未开始
       - in_progress: 当前正在执行（同一时间最多3个）
       - completed: 任务成功完成
       - failed: 任务遇到错误

    2. **任务管理规则**:
       - 实时更新任务状态
       - 同一时间最多3个任务处于 in_progress
       - 必须按顺序处理任务
       - 任务失败时，标记为 failed 并包含错误详情

    3. **任务完成要求**:
       - 只有在完全完成时才标记为 completed
       - 如果遇到错误，标记为 failed
       - 绝不要在以下情况标记为 completed：
         * 实现不完整
         * 遇到未解决的错误
         * 找不到必要的文件或依赖

    Args:
        todo_list: 更新后的完整任务列表
        state: Agent 状态，包含更新前的todo_list
        tool_call_id: 本次工具调用对应的id（通过InjectedToolCallId注入）
        
    """
    
    # ✅ 1. 验证逻辑放回工具内部
    validated_tasks = []
    current_time = datetime.now().isoformat()
    old_todo_list = state.todo_list
    
    formated_old = format_todo_list(old_todo_list)
    print(f"更新前todo_list：\n{formated_old}")
        
    validated_tasks = _validate_todo_list(todo_list)
    formated_new = format_todo_list(validated_tasks)
    print(f"更新后todo_list：\n{formated_new}")

    # 2. 检查并发任务限制
    in_progress_count = sum(1 for t in validated_tasks if t.status == "in_progress")
    if in_progress_count > 3:
        return Command(
            update={
                "messages": [ToolMessage(f"错误: 同时进行的任务数 ({in_progress_count}) 超过限制 (3)。", tool_call_id=tool_call_id)]
            }
        )

    # 3. 生成统计信息
    # status_count = {
    #     "pending": sum(1 for t in validated_tasks if t.status == "pending"),
    #     "in_progress": in_progress_count,
    #     "completed": sum(1 for t in validated_tasks if t.status == "completed"),
    #     "failed": sum(1 for t in validated_tasks if t.status == "failed")
    # }

#     summary = f"""任务列表已更新！

# 📊 状态统计:
# - ⏳ 待执行: {status_count['pending']}
# - 🔄 进行中: {status_count['in_progress']}
# - ✅ 已完成: {status_count['completed']}
# - ❌ 失败: {status_count['failed']}

# 总计: {len(validated_tasks)} 个任务

# 继续执行下一个任务或向用户报告进度。使用 TodoRead 查看当前状态。"""

    summary = "任务列表已更新，使用todo_read查看任务状态" # 用上面summary会导致todo_read调用不稳定, 但可以省略todo_read的调用。
    return Command(
        update={
            "todo_list": validated_tasks,
            "messages": [ToolMessage(summary, tool_call_id=tool_call_id)]
        }
    )


# ============================================================================
# 3. 辅助工具（用于演示）
# ============================================================================

@tool
def create_file(filename: str, content: str) -> str:
    """创建文件（模拟）"""
    return f"✅ 已创建文件 {filename}，内容长度: {len(content)} 字符"


@tool
def run_tests() -> str:
    """运行测试（模拟）"""
    return "✅ 测试运行完成：10个测试全部通过"


# ============================================================================
# 4. 系统提示词
# ============================================================================

SYSTEM_PROMPT = """你是一个高效的AI助手，具有强大的任务管理能力。

## 任务管理规则

### 何时创建任务列表
当用户请求满足以下条件时，你必须使用 todo_write 创建任务列表：
1. 任务需要3个或更多步骤
2. 任务复杂且需要仔细规划
3. 用户明确要求使用任务列表
4. 用户提供了多个待办事项

### 任务执行流程
1. 收到复杂任务 → 使用 todo_write 创建任务列表
2. 开始执行任务 → 使用 todo_read 查看任务，然后用 todo_write 标记为 in_progress
3. 完成任务 → 使用 todo_write 标记为 completed
4. 遇到错误 → 使用 todo_write 标记为 failed，包含错误信息

### 任务状态转换
pending → in_progress → completed/failed

### 重要原则
- 频繁使用 todo_read 检查当前状态
- 实时更新任务状态
- 同时最多3个 in_progress 任务
- 按顺序执行任务
- 向用户清晰报告进度

## 示例

用户: "创建一个Python项目，包含主文件、测试文件，并运行测试"

你的行动:
1. 使用 todo_write 创建任务列表:
   - 创建主文件 main.py
   - 创建测试文件 test_main.py
   - 运行测试
2. 执行第一个任务前，用 todo_write 标记为 in_progress
3. 完成后，用 todo_write 标记为 completed
4. 继续下一个任务...
"""


# ============================================================================
# 5. 节点定义
# ============================================================================

def agent_node(state: AgentState, llm_with_tools):
    """Agent 节点：调用 LLM 生成响应
    (此函数内容不变)
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state.messages
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """条件边：判断是否继续执行工具
    (此函数内容不变)
    """
    last_message = state.messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


# ============================================================================
# 6. 构建图
# ============================================================================

def build_graph():
    """构建 StateGraph"""

    # 初始化 LLM
    # llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm = ChatTongyi(model="qwen3-max", temperature=0)

    # 准备工具
    tools = [todo_read, todo_write, create_file, run_tests]
    llm_with_tools = llm.bind_tools(tools)

    # 
    # ✅ 关键：直接使用预构建的 ToolNode
    # 它会自动处理 todo_read (读取) 和 todo_write (写入) 的 InjectedState
    # 
    tool_node = ToolNode(tools)

    # 创建 StateGraph
    builder = StateGraph(AgentState)

    # 添加节点
    builder.add_node("agent", lambda state: agent_node(state, llm_with_tools))
    builder.add_node("tools", tool_node) # ✅ 直接使用 tool_node

    # 添加边 (不变)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, {
        "tools": "tools",
        END: END
    })
    builder.add_edge("tools", "agent")

    # 编译
    return builder.compile()


# ============================================================================
# 7. 测试代码
# ============================================================================

def print_separator(title: str = ""):
    """打印分隔线"""
    print("\n" + "=" * 80)
    if title:
        print(f" {title}")
        print("=" * 80)
    print()


def test_complex_task(graph):
    """测试复杂任务的自动分解和跟踪
    (此函数内容不变)
    """
    print_separator("测试1: 复杂任务自动分解和跟踪")

    result = graph.invoke({
        "messages": [HumanMessage(
            content="""请帮我完成以下任务：
1. 创建一个Python主文件 main.py，内容是一个简单的Hello World程序
2. 创建一个测试文件 test_main.py
3. 运行测试确保一切正常

将上面两个python文件放到 ./demo/ 目录中。
请使用任务列表跟踪进度。"""
        )],
        "todo_list": [] # 确保从空列表开始
    }, {"recursion_limit": 100})

    # 打印最终任务列表
    print_separator("最终任务列表")
    for i, task in enumerate(result["todo_list"], 1):
        status_emoji = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "failed": "❌"
        }
        emoji = status_emoji.get(task.status, "")
        print(f"{i}. {emoji} [{task.status}] {task.name}")
        print(f"   描述: {task.desc}")
        if task.start_time:
            print(f"   开始: {task.start_time}")
        if task.end_time:
            print(f"   结束: {task.end_time}")
        print()

    # 打印最终回答
    print_separator("最终回答")
    final_message = result["messages"][-1]
    print(final_message.content)

    return result


def test_simple_task(graph):
    """测试简单任务（不使用 TodoList）
    (此函数内容不变)
    """
    print_separator("测试2: 简单任务（不使用TodoList）")

    result = graph.invoke({
        "messages": [HumanMessage(content="创建一个名为 hello.txt 的文件")],
        "todo_list": []
    })

    print("最终回答:")
    print(result["messages"][-1].content)
    print(f"\n任务列表是否为空: {len(result['todo_list']) == 0}")

    return result


def main():

    # 构建图
    print("正在构建 LangGraph...")
    graph = build_graph()
    print("✅ 图构建完成！\n")

    # 运行测试
    test_complex_task(graph)
    test_simple_task(graph)

    print_separator("所有测试完成")
    print("""
关键设计要点（最终版）：

1. 📦 InjectedState 的作用
   - 工具可以通过 Annotated[AgentState, InjectedState] 访问完整的 state。
   - `todo_read` 用它来 *读取* state["todo_list"]。
   - `todo_write` 用它来 *写入* state["todo_list"]。

2. ✅ ToolNode 的威力 (正确实现)
   - `ToolNode` 是 LangGraph 的 prebuilt 工具节点。
   - 它自动处理 InjectedState 的注入逻辑（读和写）。
   - 当 `todo_write` 修改了 `state["todo_list"]` 时，`ToolNode` 会检测到这个修改。
   - `ToolNode` 会自动将这个修改和 `ToolMessage` 打包在一起返回。
   - `ToolNode` 的返回值是 `{"messages": [...], "todo_list": [...]}`。

3. 🔄 为什么不需要包装 ToolNode？
   - 因为 `ToolNode` 本身就设计用来处理这个确切的用例。
   - 任何包装器（如我们之前版本）都可能错误地覆盖 `ToolNode` 的正确输出，导致 bug。

4. 📊 完整的数据流（最终版）
   ① LLM 调用 todo_write(todo_list=...)
   ② Graph 调用 `ToolNode`
   ③ `ToolNode` 自动注入 `state` 到 `todo_write`
   ④ `todo_write` 修改 `state["todo_list"]`（临时修改）
   ⑤ `todo_write` 返回 `summary` 字符串
   ⑥ `ToolNode` 检测到 `state` 被修改，并捕获 `summary`
   ⑦ `ToolNode` 返回 `{"messages": [ToolMessage(content=summary)], "todo_list": validated_list}`
   ⑧ LangGraph 用这个返回值正式更新 State

5. 💡 最佳实践
   - ✅ 相信并直接使用 `ToolNode`。
   - ✅ 使用 `InjectedState` 在工具内部 *声明式地* (declaratively) 修改状态。
   - ✅ 避免编写不必要的包装器节点来手动管理状态。
    """)


if __name__ == "__main__":
    # 设置环境变量（可选）
    # os.environ["OPENAI_API_KEY"] = "your-key"
    # os.environ["DASHSCOPE_API_KEY"] = "your-key"
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = "chapter-04-todo-task"

    main()