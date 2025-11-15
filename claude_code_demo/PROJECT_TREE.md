# Claude Code Demo - 项目文件树

```
claude_code_demo/
│
├── 📄 __init__.py                          # 包初始化
├── 📄 config.py                            # 配置管理 (151 行)
│   ├── LLMConfig                           # LLM 配置
│   ├── TokenConfig                         # Token 管理配置
│   ├── SubAgentConfig                      # SubAgent 配置
│   ├── TodoConfig                          # Todo 配置
│   ├── HumanLoopConfig                     # 人机协同配置
│   └── ClaudeCodeConfig                    # 主配置类
│
├── 📄 main.py                              # 主入口 (176 行)
│   └── ClaudeCodeDemo                      # 主应用类
│       ├── __init__()                      # 初始化
│       ├── run()                           # 运行 Agent
│       ├── run_interactive()               # 交互式模式
│       └── visualize()                     # 可视化图
│
├── 📄 visualize_approval.py                # 图可视化工具
├── 📄 examples.py                          # 使用示例 (226 行)
│   ├── example_1_basic_usage()             # 基础使用
│   ├── example_2_file_operations()         # 文件操作
│   ├── example_3_complex_task()            # 复杂任务
│   ├── example_4_subagent()                # SubAgent
│   ├── example_5_human_loop()              # 人机协同
│   ├── example_6_custom_config()           # 自定义配置
│   ├── example_7_streaming()               # 流式输出
│   ├── example_8_compression()             # 上下文压缩
│   └── example_9_interactive()             # 交互式模式
│
├── 📄 README.md                            # 项目文档
├── 📄 PROJECT_TREE.md                      # 项目树结构
│
├── 📁 core/                                # 核心模块
│   ├── __init__.py
│   ├── state.py                            # 状态定义 (135 行) - Pydantic BaseModel
│   │   ├── TodoItem                        # Todo 项类型
│   │   ├── CompressionRecord               # 压缩记录类型
│   │   ├── AgentState                      # Agent 状态类型（Pydantic）
│   │   └── 状态辅助函数
│   │
│   └── graph.py                            # 图构建 (233 行) - 含 approval 节点
│       ├── TOOLS_REQUIRING_APPROVAL        # 敏感工具列表
│       ├── should_continue()               # 路由函数（含 approval 判断）
│       ├── approval_node()                 # 人工确认节点
│       ├── check_compression()             # 压缩检查
│       ├── build_graph()                   # 构建图
│       └── visualize_graph()               # 可视化
│
├── 📁 tools/                               # 工具模块
│   ├── __init__.py
│   │
│   ├── base_tools.py                       # 基础工具 (173 行)
│   │   ├── read_file()                     # 读取文件
│   │   ├── write_file()                    # 写入文件 ⚠️ 需确认
│   │   ├── edit_file()                     # 编辑文件 ⚠️ 需确认
│   │   ├── list_directory()                # 列出目录
│   │   └── search_in_files()               # 搜索文件
│   │
│   ├── todo_tools.py                       # Todo 工具 (246 行)
│   │   ├── todo_read()                     # 读取任务列表
│   │   ├── todo_write()                    # 更新任务列表
│   │   └── get_todo_tools()                # 获取工具列表
│   │
│   ├── task_tool.py                        # SubAgent 工具 (159 行)
│   │   ├── TaskToolManager                 # Task 管理器
│   │   │   ├── __init__()
│   │   │   ├── _create_subagent()          # 创建 SubAgent
│   │   │   └── execute_task()              # 执行任务
│   │   └── create_task_tool()              # 创建工具
│   │
│   └── human_loop_tool.py                  # 人机协同 (54 行)
│       ├── ask_human()                     # 询问用户
│       └── get_human_loop_tools()          # 获取工具列表
│
├── 📁 nodes/                               # 节点模块
│   ├── __init__.py
│   │
│   ├── agent_node.py                       # Agent 节点 (64 行) - async
│   │   ├── agent_node()                    # 节点函数（异步）
│   │   └── create_agent_node()             # 创建节点
│   │
│   └── compression_node.py                 # 压缩节点 (66 行) - async
│       ├── compression_node()              # 节点函数（异步）
│       └── create_compression_node()       # 创建节点
│
├── 📁 utils/                               # 工具函数
│   ├── __init__.py
│   │
│   ├── token_counter.py                    # Token 计数 (177 行)
│   │   ├── get_latest_token_usage()        # 获取最新 token (倒序优化)
│   │   ├── estimate_tokens()               # 估算 token
│   │   ├── needs_compression()             # 判断是否需要压缩
│   │   ├── calculate_compression_stats()   # 计算压缩统计
│   │   └── TokenMonitor                    # Token 监控器
│   │
│   └── compression.py                      # 压缩逻辑 (230 行)
│       ├── get_messages_to_keep()          # 获取保留消息
│       ├── get_messages_to_compress()      # 分离消息
│       ├── compress_messages()             # 压缩消息 (8段式)
│       ├── should_compress_now()           # 判断是否压缩
│       └── CompressionManager              # 压缩管理器
│
├── 📁 prompts/                             # 提示词模块
│   ├── __init__.py
│   │
│   ├── system_prompts.py                   # 系统提示词 (131 行)
│   │   ├── MAIN_AGENT_SYSTEM_PROMPT        # 主 Agent 提示词
│   │   ├── TODO_MANAGEMENT_PROMPT          # Todo 管理提示词
│   │   ├── SUBAGENT_PROMPTS                # SubAgent 提示词字典
│   │   ├── get_main_system_prompt()        # 获取主提示词
│   │   └── get_subagent_system_prompt()    # 获取 SubAgent 提示词
│   │
│   └── compression_prompts.py              # 压缩提示词 (63 行)
│       ├── COMPRESSION_PROMPT              # 8段式压缩提示词
│       ├── COMPRESSION_RESULT_PREFIX       # 结果前缀
│       ├── get_compression_prompt()        # 获取提示词
│       ├── format_compression_result()     # 格式化结果
│       └── get_compression_system_prompt() # 获取系统提示词
│
└── 📁 docs/                                # 文档目录
    ├── APPROVAL_GUIDE.md                   # 人工确认功能指南
    ├── APPROVAL_IMPLEMENTATION_SUMMARY.md  # 实现总结
    ├── ARCHITECTURE.md                     # 架构设计文档
    └── DEBUG_GUIDE.md                      # 调试指南
```

## 📊 统计信息

### 代码分布
```
总代码行数: 2,476 行

模块分布:
├── tools/        722 行 (29.2%)
├── utils/        575 行 (23.2%)
├── main/         450 行 (18.2%)
├── core/         257 行 (10.4%)
├── prompts/      194 行 (7.8%)
├── nodes/        142 行 (5.7%)
└── config/       136 行 (5.5%)
```

### 文件统计
```
Python 文件:     19 个
文档文件:        6 个 (README, PROJECT_TREE, 4个docs/)
配置文件:        1 个 (config.py)
总文件数:        26 个
```

### 功能统计
```
核心工具:        10 个
  ├── 基础工具:   5 个 (read, write, edit, list, search)
  ├── Todo 工具:  2 个 (read, write)
  ├── 人机协同:   1 个 (ask_human)
  └── SubAgent:   1 个 (task_tool)

SubAgent 类型:   3 个
  ├── general-purpose
  ├── code-analyzer
  └── document-writer

图节点:          4 个
  ├── agent (LLM 调用)
  ├── approval (人工确认) ⚠️ NEW
  ├── tools (工具执行)
  └── compression (上下文压缩)

示例数量:        9 个
```

## 🎯 功能映射

### Claude Code 功能 → 代码位置

| 功能 | 实现位置 | 文件 |
|------|---------|------|
| 基础 Agent | ✅ | `core/graph.py`, `nodes/agent_node.py` |
| Token 监控 | ✅ | `utils/token_counter.py` |
| 8段式压缩 | ✅ | `utils/compression.py`, `prompts/compression_prompts.py` |
| SubAgent | ✅ | `tools/task_tool.py` |
| Todo 管理 | ✅ | `tools/todo_tools.py` |
| 人机协同 | ✅ | `tools/human_loop_tool.py` |
| **人工确认** | ✅ | `core/graph.py::approval_node()` ⚠️ NEW |
| **Pydantic 状态** | ✅ | `core/state.py` ⚠️ NEW |
| 配置管理 | ✅ | `config.py` |

## 🔄 数据流

```
用户输入
    ↓
main.py (ClaudeCodeDemo)
    ↓
core/graph.py (build_graph)
    ↓
nodes/compression_node.py (检查压缩)
    ↓
nodes/agent_node.py (LLM 生成)
    ↓
should_continue (路由判断)
    ├─→ approval (人工确认敏感工具) ⚠️ NEW
    │   └─→ ToolNode (执行工具)
    │       ├─→ tools/base_tools.py
    │       ├─→ tools/todo_tools.py
    │       ├─→ tools/task_tool.py
    │       └─→ tools/human_loop_tool.py
    │
    ├─→ ToolNode (执行普通工具)
    │   └─→ (同上)
    │
    ├─→ nodes/compression_node.py (压缩)
    │   └─→ utils/compression.py
    │
    └─→ END (返回结果)
```

## 📚 学习路径

### 新手入门
1. 阅读 `README.md` - 了解项目
2. 运行 `quickstart.py` - 快速体验
3. 查看 `examples.py` - 学习用法
4. 阅读 `config.py` - 理解配置

### 进阶学习
1. 研究 `core/graph.py` - 理解图结构
2. 分析 `tools/` - 学习工具实现
3. 探索 `nodes/` - 理解节点逻辑
4. 深入 `utils/` - 掌握核心算法

### 高级研究
1. 阅读 `ARCHITECTURE.md` - 理解架构
2. 分析 `prompts/` - 学习提示词工程
3. 研究 `utils/compression.py` - 8段式压缩
4. 探索扩展点 - 自定义开发

## 🚀 快速索引

### 核心文件
- **入口**: `main.py` → `ClaudeCodeDemo`
- **图**: `core/graph.py` → `build_graph()`
- **状态**: `core/state.py` → `AgentState`
- **配置**: `config.py` → `ClaudeCodeConfig`

### 关键功能
- **压缩**: `utils/compression.py` → `CompressionManager`
- **Token**: `utils/token_counter.py` → `TokenMonitor`
- **SubAgent**: `tools/task_tool.py` → `TaskToolManager`
- **Todo**: `tools/todo_tools.py` → `todo_read/write`

### 提示词
- **主提示词**: `prompts/system_prompts.py`
- **压缩提示词**: `prompts/compression_prompts.py`

### 示例与文档
- **快速开始**: `quickstart.py`
- **使用示例**: `examples.py`
- **项目文档**: `README.md`
- **架构文档**: `ARCHITECTURE.md`
