"""
Todo 任务管理工具
实现 Claude Code 的任务跟踪功能
"""
import json
import uuid
from datetime import datetime
from typing import List
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated

from core.state import TodoItem, AgentState


# Todo 工具的详细提示词
TODO_READ_DESCRIPTION = """读取当前会话的任务列表。

主动且频繁地使用此工具，以确保您了解当前任务列表的状态。
您应该尽可能多地使用此工具，特别是在：
- 开始工作前
- 完成任务后
- 不确定下一步做什么时

此工具不需要任何参数。
"""


def format_todo_list(todo_list: List[dict]) -> str:
    """将 todo_list 格式化为美观的、人类可读的字符串"""
    if not todo_list:
        return "[OK] Task list is empty."

    # 按状态分组
    by_status = {
        "in_progress": [],
        "pending": [],
        "completed": [],
        "failed": []
    }

    for task in todo_list:
        status = task.get("status", "pending")
        if status not in by_status:
            status = "pending"
        by_status[status].append(task)

    # 定义状态标题
    status_headers = {
        "in_progress": "[*] In-Progress:",
        "pending": "[ ] Pending:",
        "completed": "[x] Completed:",
        "failed": "[!] Failed:"
    }

    result_lines = ["\n" + "=" * 30 + " Task List " + "=" * 30]
    has_content = False

    for status, header in status_headers.items():
        tasks = by_status[status]

        if tasks:
            has_content = True
            result_lines.append(f"\n{header}")
            for task in tasks:
                result_lines.append(f"  [{task['id']}] {task['name']}")
                result_lines.append(f"      Desc: {task['desc']}")

    result_lines.append("\n" + "=" * 62)

    if not has_content:
        return "[OK] Task list is empty."

    return "\n".join(result_lines)


def _validate_todo_list(todo_list: List[dict]) -> List[dict]:
    """验证和处理任务列表"""
    current_time = datetime.now().isoformat()

    validated = []
    for task in todo_list:
        # 确保必需字段存在
        task_id = task.get("id") or str(uuid.uuid4())[:8]
        name = task.get("name", "未命名任务")
        desc = task.get("desc", "")
        status = task.get("status", "pending")

        # 验证状态
        if status not in ["pending", "in_progress", "completed", "failed"]:
            status = "pending"

        # 设置时间戳
        start_time = task.get("start_time")
        end_time = task.get("end_time")

        if status == "in_progress" and not start_time:
            start_time = current_time

        if status in ["completed", "failed"] and not end_time:
            end_time = current_time

        validated_task = {
            "id": task_id,
            "name": name,
            "desc": desc,
            "status": status,
            "start_time": start_time,
            "end_time": end_time,
            "error": task.get("error")
        }

        validated.append(validated_task)

    return validated

TODO_WRITE_DESCRIPTION = """更新当前会话的任务列表。主动使用此工具来跟踪进度和管理任务执行。

## 任务对象结构

每个任务必须包含以下字段：
- **name** (必填): 任务名称，简短描述任务内容
- **desc** (可选): 任务详细描述，默认为空字符串
- **status** (可选): 任务状态，默认为 "pending"
- **id** (可选): 任务ID，如果不提供会自动生成

### 示例：

创建新任务：
```json
{
  "todo_list": [
    {"name": "分析Python文件", "desc": "使用search_in_files工具扫描所有Python文件", "status": "pending"},
    {"name": "生成问题报告", "desc": "整理发现的代码质量问题并生成报告", "status": "pending"}
  ]
}
```

更新任务状态：
```json
{
  "todo_list": [
    {"id": "abc123", "name": "分析Python文件", "desc": "使用search_in_files工具扫描所有Python文件", "status": "completed"},
    {"id": "def456", "name": "生成问题报告", "desc": "整理发现的代码质量问题并生成报告", "status": "in_progress"}
  ]
}
```

## 何时使用此工具

在以下场景中主动使用此工具：

1. **开始任务时** - 将任务标记为 in_progress（可单个或批量，但每批最多5个）
2. **完成任务后** - 将任务标记为 completed（可单个或批量完成）
3. **任务失败时** - 将任务标记为 failed 并包含错误详情
4. **需要更新任务进度或添加详情时**

## 任务状态和管理

1. **任务状态**：使用这些状态来跟踪进度：
   - pending: 任务尚未开始
   - in_progress: 当前正在执行（同一时间最多5个任务）
   - completed: 任务成功完成
   - failed: 任务遇到错误

2. **任务管理规则**：
   - 实时更新任务状态
   - 支持批量执行：可以将多个相似简单任务同时标记为 in_progress 或 completed
   - 批量限制：同一时间最多5个任务处于 in_progress 状态
   - 顺序执行：必须按任务列表顺序处理，不能跳跃
   - 任务失败时，将其标记为 failed 并包含错误详情

3. **任务完成要求**：
   - 只有在完全完成任务时才标记为 completed
   - 如果遇到错误，将任务标记为 failed 并包含错误详情
   - 在以下情况下绝不要将任务标记为 completed：
     - 实现不完整
     - 遇到未解决的错误
     - 找不到必要的文件或依赖项

如有疑问，请使用此工具。主动进行任务管理可以展现专业性并确保您完成所有要求。
"""


@tool(description=TODO_READ_DESCRIPTION)
def todo_read(state: Annotated[AgentState, InjectedState]) -> str:
    """
    读取当前的 Todo 列表

    Args:
        state: Agent 状态（自动注入，Pydantic 实例）

    Returns:
        格式化的任务列表
    """
    # 使用属性访问，并将 Pydantic 模型转换为字典
    todo_list = [task.model_dump() for task in state.todo_list]

    if not todo_list:
        return "当前没有任务。如果您收到了新的复杂任务，请使用 TodoWrite 创建任务列表。"

    # 格式化输出
    output = ["当前任务列表:\n"]

    # 按状态分组
    by_status = {
        "in_progress": [],
        "pending": [],
        "completed": [],
        "failed": []
    }

    for task in todo_list:
        status = task.get("status", "pending")
        by_status[status].append(task)

    # 输出进行中的任务
    if by_status["in_progress"]:
        output.append("## 进行中 (In Progress):")
        for task in by_status["in_progress"]:
            output.append(f"  [{task['id']}] {task['name']}")
            output.append(f"      描述: {task['desc']}")
            if task.get('start_time'):
                output.append(f"      开始时间: {task['start_time']}")
        output.append("")

    # 输出待处理的任务
    if by_status["pending"]:
        output.append("## 待处理 (Pending):")
        for task in by_status["pending"]:
            output.append(f"  [{task['id']}] {task['name']}")
            output.append(f"      描述: {task['desc']}")
        output.append("")

    # 输出已完成的任务
    if by_status["completed"]:
        output.append("## 已完成 (Completed):")
        for task in by_status["completed"]:
            output.append(f"  ✓ [{task['id']}] {task['name']}")
        output.append("")

    # 输出失败的任务
    if by_status["failed"]:
        output.append("## 失败 (Failed):")
        for task in by_status["failed"]:
            output.append(f"  ✗ [{task['id']}] {task['name']}")
            if task.get('error'):
                output.append(f"      错误: {task['error']}")
        output.append("")

    output.append(f"\n总计: {len(todo_list)} 个任务")
    output.append("请继续使用任务列表更新和读取功能来跟踪您的进度。")

    return "\n".join(output)


@tool(description=TODO_WRITE_DESCRIPTION)
def todo_write(
    todo_list: List[dict],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
):
    """
    更新 Todo 列表

    Args:
        todo_list: 新的任务列表（字典列表）
        state: Agent 状态（自动注入，Pydantic 实例）
        tool_call_id: 工具调用 ID（自动注入）

    Returns:
        Command 对象，包含状态更新
    """
    # 获取更新前的任务列表（用于调试），转换为字典
    old_todo_list = [task.model_dump() for task in state.todo_list]
    formatted_old = format_todo_list(old_todo_list)
    print(f"Before update:")
    print(formatted_old)

    # 调试：打印 LLM 传递的原始数据
    print(f"\n[DEBUG] LLM 传递的 todo_list 原始数据:")
    for i, task in enumerate(todo_list, 1):
        print(f"  Task {i}: {task}")

    # 验证任务数据
    validated_tasks = _validate_todo_list(todo_list)
    formatted_new = format_todo_list(validated_tasks)
    print(f"\nAfter update:")
    print(formatted_new)

    # 检查并发任务限制
    in_progress_count = sum(1 for t in validated_tasks if t["status"] == "in_progress")
    if in_progress_count > 5:
        return Command(
            update={
                "messages": [ToolMessage(
                    f"Error: Concurrent tasks ({in_progress_count}) exceed limit (5).",
                    tool_call_id=tool_call_id
                )]
            }
        )

    # 生成摘要（简化版，避免影响 todo_read 的调用）
    summary = "Task list updated, use todo_read to view task status"

    # 返回 Command 更新状态
    return Command(
        update={
            "todo_list": validated_tasks,
            "messages": [ToolMessage(summary, tool_call_id=tool_call_id)]
        }
    )


def get_todo_tools() -> list:
    """获取 Todo 工具列表"""
    return [todo_read, todo_write]
