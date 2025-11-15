# 人工确认功能使用指南

## 概述

本项目实现了**方案1：条件边路由**的人工确认机制，在不使用工具节点包装器的情况下，通过在图中插入独立的 `approval` 节点来实现敏感工具调用前的人工确认。

## 架构设计

### 流程图

```
START → compression → agent → should_continue
                                ├─ [有敏感工具?]
                                │   ├─ Yes → approval → [用户确认?]
                                │   │                    ├─ Yes → tools
                                │   │                    └─ No → agent (取消消息)
                                │   └─ No → tools
                                ├─ [需要压缩?] → compression
                                └─ [无工具调用] → END
```

### 核心组件

1. **TOOLS_REQUIRING_APPROVAL**: 敏感工具列表
2. **should_continue()**: 条件路由函数，识别敏感工具
3. **approval_node()**: 人工确认节点，触发 interrupt
4. **图边配置**: `approval → tools` 确保确认后才执行

## 配置敏感工具

在 `core/graph.py` 中修改敏感工具列表:

```python
TOOLS_REQUIRING_APPROVAL = [
    "write_file",      # 写入文件
    "edit_file",       # 编辑文件
    # 可以添加其他敏感工具:
    # "delete_file",
    # "execute_code",
    # "git_commit",
]
```

## 使用示例

### 基础使用

```python
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from main import ClaudeCodeDemo

# 创建应用
app_instance = ClaudeCodeDemo()
app = app_instance.app

# 准备输入
inputs = {
    "messages": [
        HumanMessage(content="请创建一个名为 test.txt 的文件")
    ]
}

config = {"configurable": {"thread_id": "user-session-1"}}

# 第一步执行（会在 approval 节点中断）
result = await app.ainvoke(inputs, config)

# 检查是否需要确认
state = app.get_state(config)
if state.next:  # 如果有下一个节点，说明已中断
    print("等待用户确认...")

    # 获取中断信息
    for task in state.tasks:
        if task.interrupts:
            interrupt_data = task.interrupts[0]['value']
            print(interrupt_data['message'])

    # 用户批准
    result = await app.ainvoke(Command(resume="yes"), config)
    print("工具已执行")
```

### 拒绝确认

```python
# ... 前面步骤相同 ...

# 用户拒绝
result = await app.ainvoke(Command(resume="no"), config)

# 检查结果
state = app.get_state(config)
messages = state.values['messages']
last_msg = messages[-1]  # ToolMessage: "操作已被用户取消"
```

### 自动化批准（测试场景）

```python
# 在测试中可以自动批准所有操作
async def auto_approve_runner(app, inputs, config):
    """自动批准工具调用的运行器"""
    result = await app.ainvoke(inputs, config)

    state = app.get_state(config)
    while state.next:  # 有中断
        # 自动批准
        result = await app.ainvoke(Command(resume="yes"), config)
        state = app.get_state(config)

    return result
```

## 核心代码解析

### 1. should_continue() 函数

```python
def should_continue(state: AgentState) -> Literal["tools", "approval", "compression", END]:
    messages = state.messages
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # 检查是否有敏感工具
        needs_approval = any(
            tc["name"] in TOOLS_REQUIRING_APPROVAL
            for tc in last_message.tool_calls
        )
        if needs_approval:
            return "approval"  # 需要确认
        return "tools"  # 直接执行

    if state.needs_compression:
        return "compression"

    return END
```

**关键点**:
- 返回类型使用 `Literal` 确保类型安全
- 检查所有工具调用，只要有一个敏感工具就需要确认
- 支持混合工具调用（敏感+非敏感）

### 2. approval_node() 函数

```python
def approval_node(state: AgentState) -> dict:
    messages = state.messages
    last_message = messages[-1]
    tool_calls = last_message.tool_calls

    # 构建确认信息
    tool_descriptions = [
        f"  - {tc['name']}({args_str})"
        for tc in tool_calls
        if tc["name"] in TOOLS_REQUIRING_APPROVAL
    ]

    confirmation_message = (
        f"⚠️ 以下敏感操作需要您的批准:\n\n"
        + "\n".join(tool_descriptions) + "\n\n"
        + "是否继续? (yes/no)"
    )

    # 触发中断
    user_response = interrupt({
        "type": "tool_approval_required",
        "message": confirmation_message,
        "tool_calls": [...]
    })

    # 检查响应
    if str(user_response).lower() not in ["yes", "y", "确认", "是"]:
        # 返回取消消息
        return {
            "messages": [
                ToolMessage(
                    content="操作已被用户取消",
                    tool_call_id=tc.get("id")
                )
                for tc in tool_calls
                if tc["name"] in TOOLS_REQUIRING_APPROVAL
            ]
        }

    # 用户同意，返回空更新
    return {}
```

**关键点**:
- `interrupt()` 会暂停图执行，等待 `Command(resume=...)` 恢复
- 用户拒绝时返回 `ToolMessage`，LLM 会收到取消通知
- 用户同意时返回空字典 `{}`，图继续执行到 `tools` 节点

### 3. 图配置

```python
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)  # 直接使用 ToolNode
workflow.add_node("approval", approval_node)
workflow.add_node("compression", compression_node)

# 条件路由
workflow.add_conditional_edges(
    "agent",
    should_continue,
    ["tools", "approval", "compression", END]
)

# approval 确认后执行工具
workflow.add_edge("approval", "tools")
```

## 优势分析

### 与包装器方案对比

| 特性 | 条件边路由（本方案） | 包装器方案 |
|-----|------------------|-----------|
| 代码侵入性 | 低（独立节点） | 中（包装 ToolNode） |
| 责任分离 | 清晰（单一职责） | 混合（工具+确认） |
| 可扩展性 | 高（易添加多级审批） | 中 |
| 调试难度 | 低（流程可视化） | 中 |
| 性能开销 | 无（条件路由） | 无 |

### 与 interrupt_before 对比

| 特性 | 条件边路由 | interrupt_before |
|-----|----------|-----------------|
| 区分工具类型 | 支持 | 不支持（全部中断） |
| 配置复杂度 | 中 | 低 |
| 用户体验 | 好（仅敏感操作） | 差（所有工具） |
| 自定义确认信息 | 支持 | 不支持 |

## 扩展方案

### 1. 多级审批

```python
def should_continue(state: AgentState) -> Literal[...]:
    # ...
    if needs_critical_approval:
        return "critical_approval"  # 需要管理员审批
    elif needs_approval:
        return "approval"  # 需要用户审批
    return "tools"

# 添加节点
workflow.add_node("critical_approval", critical_approval_node)
workflow.add_edge("critical_approval", "approval")
```

### 2. 基于权限的确认

```python
TOOLS_REQUIRING_APPROVAL = {
    "write_file": "user",      # 需要用户确认
    "edit_file": "user",
    "delete_file": "admin",    # 需要管理员确认
    "execute_code": "admin",
}

def should_continue(state: AgentState):
    user_role = state.user_role
    needs_approval = any(
        TOOLS_REQUIRING_APPROVAL.get(tc["name"]) == user_role
        for tc in tool_calls
    )
    # ...
```

### 3. 批量审批

```python
def approval_node(state: AgentState) -> dict:
    # 允许用户选择性批准部分工具
    user_response = interrupt({
        "type": "batch_approval",
        "tools": [
            {"id": tc["id"], "name": tc["name"], "args": tc["args"]}
            for tc in tool_calls
        ]
    })

    # user_response = ["call_1", "call_3"]  # 仅批准这两个
    approved_ids = set(user_response)

    # 过滤工具调用
    # ...
```

## 测试

运行单元测试:

```bash
cd claude_code_demo
python test_approval_unit.py
```

运行集成测试（需要 LLM API）:

```bash
python test_approval.py
```

## 常见问题

### Q1: 如何添加新的敏感工具?

修改 `core/graph.py`:

```python
TOOLS_REQUIRING_APPROVAL = [
    "write_file",
    "edit_file",
    "your_new_tool",  # 添加这里
]
```

### Q2: 如何自定义确认消息?

修改 `approval_node()` 函数中的 `confirmation_message`:

```python
confirmation_message = (
    f"🔐 安全确认\n\n"
    f"即将执行 {len(tool_descriptions)} 个敏感操作:\n"
    + "\n".join(tool_descriptions) + "\n\n"
    + "请输入 'yes' 继续，或 'no' 取消"
)
```

### Q3: 如何禁用人工确认（开发模式）?

方法1：清空敏感工具列表:

```python
TOOLS_REQUIRING_APPROVAL = []
```

方法2：修改 `should_continue`:

```python
def should_continue(state: AgentState):
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # if needs_approval:  # 注释掉这行
        #     return "approval"
        return "tools"  # 直接执行
    # ...
```

### Q4: interrupt 在测试中失败?

`interrupt()` 只能在图执行中使用，单元测试会抛出 `RuntimeError`。这是预期行为，说明节点正确工作。使用 `try-except` 捕获异常进行测试。

## 总结

本方案通过**条件边路由**实现了清晰、可扩展的人工确认机制，核心优势:

1. **架构清晰**: 独立节点，单一职责
2. **易于维护**: 配置集中在 `TOOLS_REQUIRING_APPROVAL`
3. **可扩展性**: 支持多级审批、权限控制
4. **用户体验**: 仅敏感操作触发确认

相比包装器方案，本方案更符合 LangGraph 的最佳实践，推荐在生产环境使用。
