# Claude Code Demo - 架构设计文档

## 📐 整体架构

本项目基于 Python LangGraph 实现了 Claude Code 的所有核心功能，采用模块化设计，易于理解、调试和扩展。

```
┌─────────────────────────────────────────────────────┐
│                   User Interface                     │
│              (CLI / Interactive Mode)                │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                  Main Application                    │
│                  (main.py)                          │
│  - ClaudeCodeDemo class                             │
│  - Async event loop                                 │
│  - Streaming processor                              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                 Graph Builder                        │
│                 (core/graph.py)                      │
│  - StateGraph construction                          │
│  - Node & edge definition                           │
│  - Conditional routing                              │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
┌─────────────────┐          ┌─────────────────┐
│     Nodes       │          │     Tools       │
│  (nodes/)       │          │   (tools/)      │
│                 │          │                 │
│ • agent_node    │          │ • base_tools    │
│ • tool_node     │          │ • todo_tools    │
│ • compression   │          │ • task_tool     │
│                 │          │ • human_loop    │
└─────────────────┘          └─────────────────┘
        │                             │
        └──────────────┬──────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│                    Utilities                         │
│                    (utils/)                          │
│  • token_counter - Token 监控                        │
│  • compression - 8段式压缩                           │
│  • streaming - 流式输出处理                          │
└─────────────────────────────────────────────────────┘
```

## 🔄 核心流程

### 1. 消息处理流程

```
User Input
    ↓
[compression] ← 检查 token 使用量
    ↓
[agent] ← LLM 生成响应
    ↓
[should_continue] ← 条件路由
    ├─→ [approval] → 敏感工具人工确认 → [tools] → [compression] → [agent]
    ├─→ [tools] → 执行普通工具 → [compression] → [agent]
    ├─→ [compression] → 压缩上下文 → [agent]
    └─→ [END] → 返回结果
```

### 2. Token 监控与压缩

```python
# 倒序查找最新 token 使用量
for msg in reversed(messages):
    if has_usage_info(msg):
        current_tokens = extract_tokens(msg)
        break

# 判断是否需要压缩（92% 阈值）
if current_tokens >= max_tokens * 0.92:
    trigger_compression()
```

### 3. SubAgent 执行流程

```
Main Agent
    ↓
识别复杂任务
    ↓
调用 TaskTool
    ↓
创建 SubAgent (隔离上下文)
    ├─→ general-purpose (所有工具)
    ├─→ code-analyzer (Read, Grep, Glob)
    └─→ document-writer (Read, Write, Edit)
    ↓
SubAgent 执行
    ↓
返回结果到 Main Agent
    ↓
Main Agent 总结
```

## 🧩 模块详解

### 1. 配置模块 (config.py)

```python
ClaudeCodeConfig
├── LLMConfig          # LLM 配置
│   ├── provider       # openai / tongyi
│   ├── model          # 模型名称
│   └── temperature    # 温度参数
├── TokenConfig        # Token 管理
│   ├── max_context_tokens
│   ├── compression_threshold (0.92)
│   └── reserved_output_tokens
├── SubAgentConfig[]   # SubAgent 配置
├── TodoConfig         # Todo 管理
├── HumanLoopConfig    # 人机协同
└── CheckpointConfig   # 检查点配置
```

### 2. 状态模块 (core/state.py)

```python
AgentState (TypedDict)
├── messages                # 对话消息列表
├── todo_list              # 任务列表
├── compression_history    # 压缩历史
├── current_tokens         # 当前 token 数
├── needs_compression      # 是否需要压缩
├── human_review_pending   # 是否等待人工审查
└── pending_tool_call      # 待处理的工具调用
```

### 3. 工具系统

#### 基础工具 (base_tools.py)
- `read_file`: 读取文件
- `write_file`: 写入文件
- `edit_file`: 编辑文件
- `list_directory`: 列出目录
- `search_in_files`: 搜索文件内容

#### Todo 工具 (todo_tools.py)
- `todo_read`: 读取任务列表
- `todo_write`: 更新任务列表
- 使用 `InjectedState` 访问状态

#### Task 工具 (task_tool.py)
- `task_tool`: 启动 SubAgent
- `TaskToolManager`: 管理多个 SubAgent
- 上下文隔离机制

#### 人机协同 (human_loop_tool.py)
- `ask_human`: 询问用户
- 使用 `interrupt()` 暂停执行

### 4. 节点系统

#### Agent 节点 (agent_node.py)
```python
async def agent_node(state, llm, tools):
    # 1. 构建系统提示词
    system_prompt = get_main_system_prompt(todo_count)

    # 2. 绑定工具
    llm_with_tools = llm.bind_tools(tools)

    # 3. 调用 LLM
    response = await llm_with_tools.ainvoke(messages)

    return {"messages": [response]}
```

#### Approval 节点 (graph.py::approval_node) ⚠️ NEW
```python
def approval_node(state: AgentState) -> dict:
    """敏感工具人工确认节点"""
    # 1. 提取敏感工具调用
    tool_calls = [tc for tc in last_message.tool_calls
                  if tc["name"] in TOOLS_REQUIRING_APPROVAL]

    # 2. 使用 interrupt() 暂停执行，等待用户响应
    user_response = interrupt({
        "type": "tool_approval",
        "tool_calls": tool_calls
    })

    # 3. 处理用户响应
    if user_response in ["yes", "y", "确认", "是"]:
        return {}  # 继续执行工具
    else:
        # 返回取消消息
        return {"messages": [ToolMessage("操作已被用户取消", ...)]}
```

#### 工具节点 (直接使用 LangGraph ToolNode)
- 使用 LangGraph 的 `ToolNode` 直接执行工具
- 不再需要自定义 wrapper（已删除 `nodes/tool_node.py`）
- 由 `should_continue()` 条件路由决定是否先经过 approval

#### 压缩节点 (compression_node.py)
```python
async def compression_node(state, compression_manager):
    # 1. 检查是否需要压缩
    compressed, new_messages, stats =
        await compression_manager.compress_if_needed(messages)

    # 2. 更新状态
    if compressed:
        return {
            "messages": new_messages,
            "compression_history": [..., new_record]
        }
```

### 5. 工具函数

#### Token 计数 (token_counter.py)
```python
def get_latest_token_usage(messages):
    """倒序查找优化"""
    for i in range(len(messages) - 1, -1, -1):
        if has_usage(messages[i]):
            return extract_tokens(messages[i])
    return estimate_tokens(messages)
```

#### 压缩逻辑 (compression.py)
```python
async def compress_messages(llm, messages):
    """8段式压缩"""
    # 1. 构建压缩提示词（8个部分）
    # 2. 调用 LLM 生成摘要
    # 3. 格式化结果
    # 4. 返回压缩后的消息
```

#### 流式输出 (streaming.py)
- `StreamProcessor`: 处理流式事件
- `format_stream_output`: 格式化输出
- `print_stream`: 打印流式输出

## 🎯 核心设计特点

### 1. Claude Code 机制

| 功能 | CC 实现 | 本项目实现 |
|------|---------|-----------|
| Token 监控 | 倒序查找 | ✅ `get_latest_token_usage()` |
| 压缩阈值 | 92% | ✅ `compression_threshold=0.92` |
| 压缩策略 | 8段式 | ✅ 完整提示词 |
| SubAgent | Task 工具 | ✅ `TaskToolManager` |
| Todo 管理 | Read/Write | ✅ LLM 驱动 |
| 人机协同 | 中断机制 | ✅ `interrupt()` + `ask_human` |
| **敏感工具确认** | 条件路由 | ✅ `approval_node()` + 条件边 ⚠️ NEW |
| 流式输出 | Steering | ✅ `astream()` + 事件处理 |

### 2. LangGraph 特性

| 特性 | 使用场景 |
|------|---------|
| `StateGraph` | 定义 Agent 状态机 |
| `Conditional Edges` | 动态路由（工具/压缩/结束） |
| `ToolNode` | 工具执行 |
| `MemorySaver` | 检查点持久化 |
| `interrupt()` | 人机协同 |
| `InjectedState` | 工具访问状态 |
| `astream()` | 流式输出 |

### 3. 模块化设计

```
关注点分离:
├── config.py        → 配置管理
├── core/            → 核心逻辑
│   ├── state.py     → 状态定义
│   └── graph.py     → 图构建
├── tools/           → 工具实现
├── nodes/           → 节点逻辑
├── utils/           → 工具函数
└── prompts/         → 提示词管理
```

## 🔧 扩展点

### 1. 添加新工具

```python
# 1. 在 tools/ 创建文件
@tool
def my_custom_tool(arg: str) -> str:
    """工具描述"""
    # 实现逻辑
    return result

# 2. 在 graph.py 注册
all_tools = [..., my_custom_tool]
```

### 2. 添加新节点

```python
# 1. 在 nodes/ 创建文件
async def custom_node(state: AgentState) -> dict:
    # 节点逻辑
    return {"messages": [...]}

# 2. 在 graph.py 添加
workflow.add_node("custom", custom_node)
workflow.add_edge("agent", "custom")
```

### 3. 自定义 SubAgent

```python
custom_agent = SubAgentConfig(
    type="custom",
    system_prompt="...",
    allowed_tools=[...]
)
config.subagent.append(custom_agent)
```

## 📊 性能优化

### 1. Token 优化
- ✅ 倒序查找（O(k) vs O(n)）
- ✅ 智能压缩（92% 阈值）
- ✅ 预留输出 token

### 2. 并发优化
- ✅ SubAgent 独立执行
- ✅ 异步流式处理
- ✅ 并发工具调用（ToolNode）

### 3. 上下文优化
- ✅ 8段式压缩（保留关键信息）
- ✅ 上下文隔离（SubAgent）
- ✅ 消息保留策略

## 🐛 调试指南

### 1. 启用调试模式
```python
config = ClaudeCodeConfig(debug=True)
```

### 2. 查看图结构
```python
app.visualize("graph.png")
```

### 3. 监控 Token
```python
from utils.token_counter import TokenMonitor
monitor = TokenMonitor()
usage = monitor.get_current_usage(messages)
```

### 4. LangSmith 追踪
```bash
export LANGSMITH_TRACING=true
```

## 📝 总结

本项目成功实现了 Claude Code 的所有核心功能：

1. ✅ **完整功能**: ReAct Agent, SubAgent, Todo, 压缩, 流式, 人机协同
2. ✅ **模块化**: 清晰的职责分离，易于理解和扩展
3. ✅ **生产级**: 错误处理、配置管理、日志输出
4. ✅ **最佳实践**: 结合 CC 和 LG 的设计精髓

这是一个可以直接用于学习和参考的完整实现！
