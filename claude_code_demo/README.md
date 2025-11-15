# Claude Code Demo

基于 Python LangGraph 实现的 Claude Code 核心功能演示应用。

## 📋 功能特性

本项目实现了 Claude Code 的所有核心设计：

### 1. 🤖 基础 ReAct Agent
- StateGraph 图结构
- 工具调用机制
- 消息流管理

### 2. 👤 人机协同 (Human-in-the-Loop)
- `interrupt()` 中断机制
- `AskHuman` 工具（主动询问用户）
- **人工确认机制**（敏感工具自动拦截）
- 检查点持久化（MemorySaver）

### 3. 🔄 SubAgent 多智能体协作
- TaskTool 工具
- 三种专用 SubAgent：
  - `general-purpose`: 通用任务处理
  - `code-analyzer`: 代码分析专家
  - `document-writer`: 文档撰写专家
- 上下文隔离机制

### 4. ✅ Todo 任务管理
- TodoRead/TodoWrite 工具
- LLM 自主任务跟踪
- 复杂任务自动分解

### 5. 🗜️ 8 段式上下文压缩
- Token 监控（倒序查找优化）
- 92% 阈值智能触发
- 8 段式压缩提示词

### 6. 🌊 流式输出
- 异步流式处理
- 实时事件监控
- 支持中断与恢复

## 🏗️ 项目结构

```
claude_code_demo/
├── __init__.py
├── main.py                    # 主入口
├── config.py                  # 配置文件
├── visualize_approval.py      # 图可视化工具
├── core/
│   ├── __init__.py
│   ├── state.py              # 状态定义（Pydantic BaseModel）
│   └── graph.py              # 图构建（含 approval 节点）
├── tools/
│   ├── __init__.py
│   ├── base_tools.py         # 基础工具（文件操作等）
│   ├── task_tool.py          # Task SubAgent 工具
│   ├── todo_tools.py         # TodoRead/Write 工具
│   └── human_loop_tool.py    # AskHuman 工具
├── nodes/
│   ├── __init__.py
│   ├── agent_node.py         # Agent 节点
│   └── compression_node.py   # 压缩节点
├── utils/
│   ├── __init__.py
│   ├── token_counter.py      # Token 计数
│   └── compression.py        # 压缩逻辑
├── prompts/
│   ├── __init__.py
│   ├── system_prompts.py     # 系统提示词
│   └── compression_prompts.py # 压缩提示词
└── docs/
    ├── APPROVAL_GUIDE.md             # 人工确认功能指南
    ├── APPROVAL_IMPLEMENTATION_SUMMARY.md  # 实现总结
    ├── ARCHITECTURE.md               # 架构设计文档
    └── DEBUG_GUIDE.md                # 调试指南
```

## 🚀 快速开始

### 1. 安装依赖

同dive-into-claude-code依赖（../requirements.txt）

### 2. 配置 API Key

设置环境变量
```bash
# OpenAI
export OPENAI_API_KEY=sk-proj-xxxxx

# 或使用通义千问
export DASHSCOPE_API_KEY=sk-xxxxx

# LangSmith（可选）
export LANGSMITH_API_KEY=lsv2_xxxxx
export LANGSMITH_TRACING=true
```

### 3. 运行方式

#### 方式 1: 作为独立项目运行（推荐）⭐

直接 cd 到 `claude_code_demo` 目录：

```bash
cd claude_code_demo

# 运行主程序
python main.py

# 运行示例
python examples.py

# 快速启动
python quickstart.py -m "计算 1+1"
python quickstart.py --debug
python quickstart.py --example 1
```

#### 方式 2: 从父目录运行

```bash
# 在 dive-into-claude-code 目录下
python .\claude_code_demo\main.py
python .\claude_code_demo\examples.py
```

#### 方式 3: 作为 Python 模块使用

```python
from claude_code_demo.main import ClaudeCodeDemo
import asyncio

app = ClaudeCodeDemo()
asyncio.run(app.run("帮我计算 123 + 456"))
```

#### 方式 4: VS Code 调试

1. 打开 `dive-into-claude-code` 文件夹
2. 按 `F5`，选择：
   - `Debug: Claude Code Main`
   - `Debug: Examples (Interactive)`
   - `Debug: with LangSmith`

### 4. 交互式模式

```python
from claude_code_demo.main import ClaudeCodeDemo
import asyncio

app = ClaudeCodeDemo()
asyncio.run(app.run_interactive())
```

## 💡 使用示例

### 示例 1: 简单计算
```python
await app.run("帮我计算 123 + 456")
```

### 示例 2: 文件操作
```python
await app.run("请在当前目录创建一个 hello.txt 文件，内容是 'Hello, World!'")
```

### 示例 3: 复杂任务（自动使用 TodoList）
```python
await app.run("""
帮我完成以下任务：
1. 分析当前目录下所有 Python 文件
2. 找出可能的代码质量问题
3. 生成一份分析报告
""")
```

### 示例 4: SubAgent 协作
```python
# Agent 会自动判断是否使用 SubAgent
await app.run("帮我分析 main.py 的代码质量")
```

## ⚙️ 配置说明

### 自定义配置

```python
from claude_code_demo.config import ClaudeCodeConfig, LLMConfig, TokenConfig

config = ClaudeCodeConfig(
    llm=LLMConfig(
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.7
    ),
    token=TokenConfig(
        max_context_tokens=100000,
        compression_threshold=0.92
    ),
    debug=True
)

app = ClaudeCodeDemo(config)
```

### 环境变量配置

```bash
# LLM 配置
export LLM_PROVIDER=openai
export LLM_MODEL=gpt-4o-mini

# 调试选项
export DEBUG=true
export LANGSMITH_TRACING=true
```

## 🔧 核心组件说明

### 1. 状态管理 (AgentState)

```python
class AgentState(BaseModel):  # 使用 Pydantic BaseModel
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)
    todo_list: List[TodoItem] = Field(default_factory=list)
    compression_history: List[CompressionRecord] = Field(default_factory=list)
    current_tokens: int = 0
    needs_compression: bool = False
    human_review_pending: bool = False
    pending_tool_call: Optional[dict] = None
```

### 2. 图结构

```
START
  ↓
compression (检查压缩)
  ↓
agent (LLM 生成)
  ↓
should_continue
  ├─→ approval (敏感工具确认) → tools (执行工具) → compression → agent
  ├─→ tools (普通工具) → compression → agent
  ├─→ compression (压缩) → agent
  └─→ END
```

### 3. 核心工具

| 工具名称 | 功能 | 类型 |
|---------|------|------|
| `read_file` | 读取文件 | 基础工具 |
| `write_file` | 写入文件 | 基础工具 |
| `edit_file` | 编辑文件 | 基础工具 |
| `list_directory` | 列出目录 | 基础工具 |
| `search_in_files` | 搜索文件 | 基础工具 |
| `todo_read` | 读取任务列表 | Todo 工具 |
| `todo_write` | 更新任务列表 | Todo 工具 |
| `ask_human` | 询问用户 | 人机协同 |
| `task_tool` | 启动 SubAgent | SubAgent |

## 🎯 设计亮点

### 1. 模块化设计
- 清晰的职责分离
- 易于扩展和维护
- 可复用的组件

### 2. Claude Code 核心机制
- ✅ 倒序 Token 监控（性能优化）
- ✅ 92% 压缩阈值（最佳平衡点）
- ✅ 8 段式压缩策略
- ✅ SubAgent 上下文隔离
- ✅ LLM 驱动的任务管理
- ✅ **敏感工具人工确认**（条件边路由）
- ✅ Pydantic 状态模型（类型安全）

### 3. LangGraph 特性运用
- StateGraph 状态管理
- 条件边路由（含 approval 节点）
- 检查点持久化
- 流式事件处理
- `interrupt()` 人机协同

## 📊 性能特性

- **Token 优化**: 倒序查找 + 智能压缩
- **并发支持**: SubAgent 独立执行
- **流式输出**: 实时响应用户
- **状态持久化**: 支持长对话

## 🐛 调试技巧

### 1. 启用详细日志

```python
config = ClaudeCodeConfig(debug=True)
app = ClaudeCodeDemo(config)
```

### 2. 可视化图结构

```python
app.visualize("graph.png")
```

### 3. 使用 LangSmith

```bash
export LANGSMITH_API_KEY="your-key"
export LANGSMITH_TRACING=true
```

## 🔄 扩展指南

### 添加新工具

1. 在 `tools/` 目录创建工具文件
2. 使用 `@tool` 装饰器定义工具
3. 在 `core/graph.py` 中注册工具

### 添加新节点

1. 在 `nodes/` 目录创建节点文件
2. 实现节点函数（接收 state，返回更新）
3. 在图构建中添加节点和边

### 自定义 SubAgent

```python
from claude_code_demo.config import SubAgentConfig

custom_agent = SubAgentConfig(
    type="custom-agent",
    system_prompt="Your custom prompt",
    allowed_tools=["read_file", "write_file"]
)

config.subagent.append(custom_agent)
```

## 📚 参考资料

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [Claude Code 逆向分析](https://github.com/Yuyz0112/claude-code-reverse)
- [架构设计文档](docs/ARCHITECTURE.md)
- [调试指南](docs/DEBUG_GUIDE.md)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## ❓ 常见问题

**Q: 如何切换 LLM？**
A: 修改配置中的 `provider` 和 `model` 参数。

**Q: Token 超限怎么办？**
A: 系统会自动触发压缩（92% 阈值）。

**Q: 如何禁用某些功能？**
A: 在配置中调整相应参数，或修改图构建逻辑。

**Q: 支持哪些检查点存储？**
A: 目前支持 MemorySaver（内存），计划支持 Redis 和 PostgreSQL。

## 🎉 总结

这是一个完整的 Claude Code 核心功能实现，展示了：

1. ✅ **完整的功能覆盖**: 所有核心机制都已实现
2. ✅ **模块化设计**: 代码结构清晰，易于理解和扩展
3. ✅ **生产级质量**: 包含错误处理、配置管理、日志输出
4. ✅ **最佳实践**: 结合了 Claude Code 和 LangGraph 的设计精髓

Happy Coding! 🚀
