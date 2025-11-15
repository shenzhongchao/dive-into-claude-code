# Claude Code Demo - 调试指南

## 🚀 快速开始

### 1. VS Code 调试配置

已为你配置了 6 种调试模式，按 `F5` 或点击侧边栏的"运行和调试"图标即可使用：

| 配置名称 | 用途 | 适用场景 |
|---------|------|---------|
| **Debug: Claude Code Main** | 调试主程序 | 调试 main.py 交互式模式 |
| **Debug: Examples (Interactive)** | 调试示例程序 | 调试 examples.py，选择运行哪个示例 |
| **Debug: with LangSmith** | 启用 LangSmith 追踪 | 需要可视化 Agent 执行流程时 |
| **Python: Current File** | 调试当前文件 | 调试任意打开的 Python 文件 |
| **Debug: Specific Example** | 调试特定示例 | 需要传入参数运行特定示例 |


## 🎯 调试技巧

### 设置断点的关键位置

#### 1. **Agent 节点** (`claude_code_demo/nodes/agent_node.py`)
```python
async def agent_node(state: AgentState) -> dict:
    # 在这里设置断点，查看 Agent 收到的状态
    messages = state.messages
    response = await llm_with_tools.ainvoke(messages)  # ← 设置断点
    return {"messages": [response]}
```

#### 2. **Approval 节点** (`claude_code_demo/core/graph.py::approval_node`) ⚠️ NEW
```python
def approval_node(state: AgentState) -> dict:
    # 在这里设置断点，查看敏感工具调用
    tool_calls = [tc for tc in last_message.tool_calls
                  if tc["name"] in TOOLS_REQUIRING_APPROVAL]  # ← 设置断点

    # 在 interrupt 处设置断点，检查用户响应
    user_response = interrupt(approval_data)  # ← 设置断点

    # 在响应判断处设置断点
    if user_response in APPROVAL_RESPONSES:  # ← 设置断点
        return {}
```

#### 3. **路由函数** (`claude_code_demo/core/graph.py::should_continue`)
```python
def should_continue(state: AgentState) -> Literal["tools", "approval", ...]:
    # 在路由判断处设置断点
    if has_tool_calls(last_message):
        # 检查是否有敏感工具
        needs_approval = any(
            tc["name"] in TOOLS_REQUIRING_APPROVAL  # ← 设置断点
            for tc in last_message.tool_calls
        )
        if needs_approval:
            return "approval"  # ← 设置断点
```

#### 3. **压缩节点** (`claude_code_demo/nodes/compression_node.py`)
```python
def compression_node(state: AgentState) -> dict:
    # 在这里设置断点，查看压缩触发条件
    if current_tokens > threshold_tokens:  # ← 设置断点
        compressed_messages = compress(...)
```

#### 4. **主运行循环** (`claude_code_demo/main.py`)
```python
async def run(self, message: str, ...):
    # 在这里设置断点，查看整体流程
    async for event in self.app.astream(...):  # ← 设置断点
        # 检查事件内容
        if self.config.debug:
            print(f"Event: {event}")  # ← 设置断点
```

### 使用条件断点

**右键断点 → "编辑断点" → 添加条件**

示例：只在特定工具被调用时中断
```python
# 条件：tc["name"] == "write_file"
```

示例：只在 token 数量超过阈值时中断
```python
# 条件：current_tokens > 10000
```

### 监视表达式（Watch）

在"变量"面板点击"+"添加监视表达式：

```python
# 监视当前消息数量
len(state["messages"])

# 监视 todo 列表状态
[t["status"] for t in state.get("todo_list", [])]

# 监视 token 使用量
state.get("current_tokens", 0)

# 监视最后一条消息类型
type(state["messages"][-1]).__name__

# 监视工具调用
[tc["name"] for tc in last_message.tool_calls] if hasattr(last_message, "tool_calls") else []
```

## 🔍 调试常见问题

### 问题 1：State 字段缺失

**症状**：`KeyError` 或 Pydantic 验证错误

**调试步骤**：
1. 在 `create_initial_state()` 处设置断点
2. 检查返回的状态是否包含所有必需字段
3. 在状态更新处设置断点，查看哪个字段被遗漏

```python
# 在这里设置断点
input_data = create_initial_state()  # ← 检查所有字段
input_data["messages"] = [HumanMessage(content=message)]
```

### 问题 2：工具不触发确认 ⚠️ UPDATED

**调试步骤**：
1. 在 `core/graph.py` 的 `should_continue()` 处设置断点
2. 检查工具名称是否在 `TOOLS_REQUIRING_APPROVAL` 列表中
3. 查看返回值是否为 `"approval"`

```python
# 在 core/graph.py 设置断点检查
needs_approval = any(
    tc["name"] in TOOLS_REQUIRING_APPROVAL  # ← 断点在这里
    for tc in tool_calls
)

# 检查 TOOLS_REQUIRING_APPROVAL 配置
TOOLS_REQUIRING_APPROVAL = ["write_file", "edit_file"]  # ← 检查配置
```

### 问题 2.1：Approval 未正常工作 ⚠️ NEW

**症状**：敏感工具直接执行，没有弹出确认

**调试步骤**：
1. 检查 `TOOLS_REQUIRING_APPROVAL` 列表是否包含该工具
2. 在 `approval_node()` 入口设置断点，确认是否进入该节点
3. 检查图结构是否正确连接 `approval → tools`

```python
# 在 approval_node 入口设置断点
def approval_node(state: AgentState) -> dict:
    print(f"[DEBUG] Entering approval_node")  # ← 添加调试输出
    last_message = state.messages[-1]
```

### 问题 3：压缩未触发

**调试步骤**：
1. 在 `compression_node.py` 设置断点
2. 监视 `current_tokens` 和 `threshold_tokens`
3. 检查 `needs_compression` 标志

```python
# 在压缩判断处设置断点
if current_tokens > threshold_tokens:  # ← 断点
    print(f"Compression triggered: {current_tokens}/{threshold_tokens}")
```

### 问题 4：Interrupt 未正确处理

**调试步骤**：
1. 在 `main.py` 的 interrupt 检测逻辑处设置断点
2. 检查 `state.next` 和 `state.tasks`
3. 查看 interrupt 数据结构

```python
# 在这里设置断点
if hasattr(state, 'tasks') and state.tasks:  # ← 断点
    for task in state.tasks:
        if hasattr(task, 'interrupts'):  # ← 断点
            print(task.interrupts[0].value)
```

## 📊 使用 LangSmith 进行调试

### 启用 LangSmith

1. **在 .env 中配置**：
```bash
LANGSMITH_API_KEY=lsv2_xxxxx
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=claude-code-debug
```

2. **使用调试配置**：选择 "Debug: with LangSmith"

3. **查看追踪**：访问 https://smith.langchain.com

### LangSmith 查看内容

- **完整的工具调用链** - 每个工具的输入输出
- **LLM 调用详情** - Token 使用、响应时间
- **错误堆栈** - 详细的错误信息
- **状态演变** - State 在每个节点的变化

## 🛠️ 实用调试代码片段

### 1. 打印状态快照

在需要查看状态的地方插入：
```python
import json
print(json.dumps({
    "messages_count": len(state["messages"]),
    "todo_count": len(state.get("todo_list", [])),
    "current_tokens": state.get("current_tokens", 0),
    "needs_compression": state.get("needs_compression", False)
}, indent=2))
```

### 2. 查看消息历史

```python
for i, msg in enumerate(state["messages"]):
    msg_type = type(msg).__name__
    content = getattr(msg, 'content', '')[:50]
    print(f"{i}: [{msg_type}] {content}...")
```

### 3. 监控工具调用

```python
if hasattr(last_message, "tool_calls"):
    for tc in last_message.tool_calls:
        print(f"Tool: {tc['name']}, Args: {tc['args']}")
```

### 4. 追踪 Token 使用

```python
from claude_code_demo.utils.token_counter import count_messages_tokens
tokens = count_messages_tokens(state["messages"])
print(f"Current tokens: {tokens}, Limit: {config.token.max_context_tokens}")
```

## ⚡ 性能调试

### 启用详细日志

在 `config.py` 中设置：
```python
config = ClaudeCodeConfig(
    debug=True,  # 启用调试输出
    token=TokenConfig(
        max_context_tokens=100000,
        compression_threshold=0.92
    )
)
```

### 测量执行时间

```python
import time

start = time.time()
result = await app.run(message)
elapsed = time.time() - start
print(f"Execution time: {elapsed:.2f}s")
```

## 📝 调试检查清单

开始调试前，确保：

- [ ] `.env` 文件已正确配置
- [ ] 虚拟环境已激活
- [ ] 所有依赖已安装 (`pip install -r requirements.txt`)
- [ ] VS Code Python 解释器指向正确的虚拟环境
- [ ] 如果使用 LangSmith，API key 已配置

## 🎓 进阶技巧

### 使用 IPython 进行交互式调试

在代码中插入：
```python
import IPython; IPython.embed()
```

执行到这里会启动交互式 shell，可以：
- 检查变量：`print(state)`
- 调用函数：`result = some_function(args)`
- 修改状态：`state["messages"] = []`

### 使用 pdb 调试器

```python
import pdb; pdb.set_trace()
```

常用命令：
- `n` - 下一行
- `s` - 步入函数
- `c` - 继续执行
- `p variable` - 打印变量
- `l` - 显示当前代码

## 🆘 寻求帮助

如果遇到问题：
1. 检查本指南的常见问题部分
2. 启用 `debug=True` 查看详细输出
3. 使用 LangSmith 追踪完整执行流程
4. 在关键位置设置断点，逐步执行

Happy Debugging! 🐛🔨
