# 不使用包装器实现人工确认功能 - 实现总结

## 实现方案

采用**方案1：条件边路由**，通过在图中插入独立的 `approval` 节点实现敏感工具调用前的人工确认。

## 核心修改

### 1. 修改文件: `core/graph.py`

#### 新增内容:

1. **TOOLS_REQUIRING_APPROVAL** (第24-29行)
   - 敏感工具列表配置
   - 当前包含: `write_file`, `edit_file`

2. **should_continue()** 函数增强 (第32-61行)
   - 返回类型: `Literal["tools", "approval", "compression", END]`
   - 新增逻辑: 检测敏感工具，路由到 `approval` 节点

3. **approval_node()** 新函数 (第64-130行)
   - 功能: 人工确认节点
   - 核心机制: 使用 `interrupt()` 暂停执行
   - 用户响应处理:
     - Yes → 返回空字典 `{}`，继续执行
     - No → 返回 `ToolMessage` 取消消息

4. **build_graph()** 更新 (第178-201行)
   - 添加 `approval` 节点
   - 配置路由边: `approval → tools`
   - 更新条件边: 支持 4 个出口 (tools/approval/compression/END)

## 架构优势

### 与其他方案对比

| 指标 | 条件边路由 | 包装器方案 | interrupt_before |
|-----|----------|-----------|-----------------|
| 代码侵入性 | ⭐⭐⭐⭐⭐ 低 | ⭐⭐⭐ 中 | ⭐⭐⭐⭐ 低 |
| 责任分离 | ⭐⭐⭐⭐⭐ 清晰 | ⭐⭐⭐ 混合 | ⭐⭐⭐⭐ 清晰 |
| 工具区分 | ⭐⭐⭐⭐⭐ 支持 | ⭐⭐⭐⭐⭐ 支持 | ⭐ 不支持 |
| 自定义消息 | ⭐⭐⭐⭐⭐ 支持 | ⭐⭐⭐⭐⭐ 支持 | ⭐ 不支持 |
| 可扩展性 | ⭐⭐⭐⭐⭐ 高 | ⭐⭐⭐ 中 | ⭐⭐ 低 |
| 配置复杂度 | ⭐⭐⭐ 中 | ⭐⭐⭐⭐ 中 | ⭐⭐⭐⭐⭐ 低 |

## 流程图

```
┌─────┐
│START│
└──┬──┘
   │
   v
┌────────────┐
│compression │ (检查是否需要压缩)
└──────┬─────┘
       │
       v
   ┌───────┐
   │ agent │ (调用 LLM 生成工具调用)
   └───┬───┘
       │
       v
 ┌─────────────────┐
 │should_continue()│ (条件路由)
 └────────┬────────┘
          │
    ┌─────┼─────┬──────────┬─────┐
    │     │     │          │     │
    v     v     v          v     v
  tools  approval  compression  END
         │
         │ (触发 interrupt)
         │
   ┌─────┴─────┐
   │用户确认?  │
   └─────┬─────┘
         │
    ┌────┴────┐
    │         │
   Yes       No
    │         │
    v         v
  tools    agent
           (返回取消消息)
```

## 关键技术点

### 1. interrupt() 机制

```python
user_response = interrupt({
    "type": "tool_approval_required",
    "message": "⚠️ 以下敏感操作需要您的批准...",
    "tool_calls": [...]
})
```

**工作原理**:
1. `interrupt()` 暂停图执行，保存当前状态到 checkpoint
2. 返回中断信息给客户端
3. 等待客户端使用 `Command(resume=...)` 恢复执行
4. `user_response` 接收恢复时传入的值

### 2. ToolMessage 取消机制

```python
ToolMessage(
    content="操作已被用户取消",
    tool_call_id=tc.get("id")
)
```

**关键点**:
- `tool_call_id` 必须匹配 AIMessage 中的工具调用 ID
- LLM 会将此消息理解为工具执行结果
- Agent 可以据此向用户报告操作被取消

### 3. 条件边类型安全

```python
def should_continue(state: AgentState) -> Literal["tools", "approval", "compression", END]:
    # ...
```

**优势**:
- 编译时类型检查
- IDE 自动补全
- 防止拼写错误导致路由失败

## 测试验证

### 单元测试结果

```
✓ 识别敏感工具: 通过
✓ 放行普通工具: 通过
✓ approval_node 输出: 通过
✓ 敏感工具列表: 通过
✓ 混合工具调用: 通过

总计: 5/5 测试通过
```

测试文件: `test_approval_unit.py`

## 使用示例

### 基础用法

```python
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from main import ClaudeCodeDemo

app_instance = ClaudeCodeDemo()
app = app_instance.app

inputs = {"messages": [HumanMessage(content="创建 test.txt 文件")]}
config = {"configurable": {"thread_id": "session-1"}}

# 第一步：触发中断
result = await app.ainvoke(inputs, config)

# 第二步：用户确认
result = await app.ainvoke(Command(resume="yes"), config)
```

### 拒绝操作

```python
# 第二步：用户拒绝
result = await app.ainvoke(Command(resume="no"), config)

# 结果：收到 ToolMessage("操作已被用户取消")
```

## 扩展方向

### 1. 多级审批

```python
def should_continue(state):
    if needs_critical_approval:
        return "critical_approval"
    elif needs_approval:
        return "approval"
    return "tools"
```

### 2. 基于权限的确认

```python
TOOLS_REQUIRING_APPROVAL = {
    "write_file": "user",
    "delete_file": "admin",
}
```

### 3. 批量选择审批

允许用户选择性批准部分工具调用。

## 文档清单

1. **APPROVAL_GUIDE.md** - 完整使用指南
2. **test_approval_unit.py** - 单元测试
3. **test_approval.py** - 集成测试（需要 LLM）
4. **visualize_approval.py** - 图可视化工具

## 与原始 tool_node.py 的对比

### 原始包装器方案 (已禁用)

```python
# nodes/tool_node.py
def create_tool_node(tools: list):
    standard_tool_node = ToolNode(tools)

    def tool_node_with_approval(state: AgentState):
        # 在工具节点内部处理确认
        if needs_approval:
            user_response = interrupt(...)
        result = standard_tool_node.invoke(...)
        return result

    return tool_node_with_approval
```

**问题**:
- 责任混合（工具执行 + 确认逻辑）
- 难以可视化流程
- 扩展性差（多级审批困难）

### 新方案 (条件边路由)

```python
# core/graph.py
workflow.add_node("approval", approval_node)  # 独立节点
workflow.add_conditional_edges(
    "agent",
    should_continue,
    ["tools", "approval", ...]
)
workflow.add_edge("approval", "tools")
```

**优势**:
- 单一职责（approval 节点仅负责确认）
- 流程可视化（Mermaid 图清晰展示）
- 易于扩展（插入新节点）

## 总结

成功实现了**不使用包装器**的人工确认功能，核心要点:

1. ✅ **独立节点**: `approval` 节点单一职责
2. ✅ **条件路由**: `should_continue()` 智能识别敏感工具
3. ✅ **类型安全**: 使用 `Literal` 类型注解
4. ✅ **用户体验**: 仅敏感操作触发确认
5. ✅ **可扩展性**: 支持多级审批、权限控制
6. ✅ **测试完备**: 5/5 单元测试通过

相比包装器方案，本方案更符合 **LangGraph 最佳实践**，推荐在生产环境使用。
