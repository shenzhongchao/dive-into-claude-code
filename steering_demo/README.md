# Streaming + Steering Demo

**流式输出 + 中断控制（Steering）**演示应用，展示 Claude Code 的核心交互特性。

## 🎯 功能特性

### 1. **流式输出（Streaming）**
- ✅ 实时逐字显示 AI 回复（类似 ChatGPT）
- ✅ 使用 SSE (Server-Sent Events) 技术
- ✅ 低延迟、高性能

### 2. **中断控制（Steering）**
- ✅ **随时中断** AI 的执行
- ✅ **立即响应** 用户的新输入
- ✅ **保持上下文** - 使用 Checkpointer 保存对话状态
- ✅ 实现类似 Claude Code 的交互体验

### 3. **会话管理**
- ✅ 自动生成会话 ID
- ✅ 保存完整对话历史
- ✅ 支持从检查点恢复

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────┐
│                   架构设计                           │
│                                                      │
│  前端 (frontend.html)                                │
│  ├─ HTML + CSS (响应式设计)                          │
│  ├─ JavaScript (原生 Fetch API)                      │
│  └─ SSE 流式接收                                     │
│                                                      │
│  后端 (backend.py)                                   │
│  ├─ FastAPI (异步 Web 框架)                          │
│  ├─ LangGraph (Agent 框架)                           │
│  ├─ LangChain (LLM 集成)                             │
│  └─ MemorySaver (检查点存储)                         │
│                                                      │
│  通信协议                                             │
│  └─ SSE (Server-Sent Events)                        │
│     ├─ event: session_id → 会话 ID                   │
│     ├─ event: token → 流式 token                     │
│     ├─ event: aborted → 中断通知                     │
│     └─ event: done → 完成通知                        │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## 📦 安装依赖

### 前置要求

- Python 3.9+
- 现代浏览器（支持 SSE）

### 安装 Python 依赖

```bash
pip install fastapi uvicorn langgraph langchain langchain-openai langchain-community
# 或使用通义千问
pip install dashscope
```

### 配置环境变量

创建 `.env` 文件：

```bash
# 选择一个 LLM 配置

# 选项 1: OpenAI
OPENAI_API_KEY=sk-proj-xxxxx

# 选项 2: 通义千问
DASHSCOPE_API_KEY=sk-xxxxx

# 可选：LangSmith 追踪
LANGSMITH_API_KEY=lsv2_xxxxx
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=steering-demo
```

## 🚀 运行应用

### 1. 启动后端

```bash
cd steering_demo
python backend.py
```

你会看到：

```
============================================================
🚀 Streaming + Steering Demo 后端启动
============================================================
LLM: ChatOpenAI
工具数量: 3
API 端点:
  - POST /api/chat        - 流式聊天
  - POST /api/abort       - 中断执行
  - GET  /api/history/:id - 获取历史
============================================================

监听地址: http://localhost:8000
前端页面: 请在浏览器中打开 frontend.html
```

### 2. 打开前端

在浏览器中打开 `frontend.html`：

```bash
# 方法 1: 双击文件
# 方法 2: 使用浏览器打开
# 方法 3: 使用 live server（推荐）
```


## 🎮 使用演示

### 基本使用

1. **发送消息**：在输入框输入消息，按 Enter 或点击"发送"
2. **查看流式输出**：AI 的回复会逐字显示
3. **中断执行**：在 AI 回复过程中，点击 "🛑 停止" 按钮
4. **继续对话**：中断后可以立即发送新消息，对话上下文会保持

### 测试场景

#### 场景 1: 体验流式输出

```
用户: 用一段话介绍 LangGraph

观察: AI 的回复会像 ChatGPT 一样逐字显示
```

#### 场景 2: 测试中断功能（核心特性）

```
步骤 1: 发送消息: "先搜索 Python，然后计算 100 * 200"
步骤 2: 等待 AI 开始回复
步骤 3: 点击 "🛑 停止" 按钮
步骤 4: 立即发送新消息: "不用搜索了，直接告诉我北京天气"

观察:
  - ✅ AI 立即停止当前任务
  - ✅ 立即处理新请求
  - ✅ 对话历史完整保存
```

#### 场景 3: 测试工具调用

```
用户: 计算 15 * 23

观察:
  - 后端控制台显示 "🧮 计算: 15 * 23"
  - 前端实时显示计算过程
  - 工具执行有 1 秒延迟（模拟真实场景）
```

#### 场景 4: 测试上下文保持

```
步骤 1: 发送 "我的名字是张三"
步骤 2: 发送 "我叫什么名字？"

观察: AI 能记住之前的对话（Checkpointer 机制）
```

## 📝 API 端点说明

### POST /api/chat
流式聊天端点

**请求体：**
```json
{
  "message": "你的消息",
  "session_id": "可选，会话ID"
}
```

**响应：** SSE 流
```
event: session_id
data: xxx-xxx-xxx

event: token
data: 你好

event: token
data: ！

event: done
data: 完成
```

### POST /api/abort
中断当前执行

**请求体：**
```json
{
  "session_id": "xxx-xxx-xxx"
}
```

**响应：**
```json
{
  "status": "success",
  "message": "中断信号已发送"
}
```

### GET /api/history/{session_id}
获取会话历史

**响应：**
```json
{
  "status": "success",
  "session_id": "xxx-xxx-xxx",
  "messages": [
    {
      "role": "human",
      "content": "你好"
    },
    {
      "role": "ai",
      "content": "你好！有什么可以帮你的？"
    }
  ],
  "message_count": 2
}
```

## 🔧 自定义配置

### 修改 LLM

编辑 `backend.py`：

```python
# 使用 OpenAI
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True)

# 使用通义千问
from langchain_community.chat_models import ChatTongyi
llm = ChatTongyi(model="qwen-max", temperature=0)

# 使用本地模型
from langchain_community.chat_models import ChatOllama
llm = ChatOllama(model="llama3")
```

### 添加自定义工具

编辑 `backend.py`：

```python
@tool
def my_custom_tool(param: str) -> str:
    """你的工具描述"""
    # 实现你的逻辑
    return "结果"

# 添加到工具列表
tools = [search_database, calculate, fetch_weather, my_custom_tool]
```

### 修改检查点存储

```python
# 使用 Redis（生产环境推荐）
from langgraph.checkpoint.redis import RedisSaver

checkpointer = RedisSaver(
    redis_url="redis://localhost:6379",
    ttl=86400  # 24小时过期
)

# 使用 PostgreSQL
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:pass@localhost/db"
)
```

## 🎯 核心实现原理

### 1. 流式输出实现

**后端（Python）：**
```python
async def event_generator():
    async for msg, metadata in agent.astream(input_msg, config, stream_mode="messages"):
        if isinstance(msg, AIMessage) and msg.content:
            yield f"event: token\ndata: {msg.content}\n\n"
```

**前端（JavaScript）：**
```javascript
const response = await fetch('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message })
});

const reader = response.body.getReader();
// 读取流并实时显示
```

### 2. Steering 实现

**关键组件：**

1. **Abort Flag（中断标志）**
   ```python
   abort_flags[session_id] = False

   # 在流式循环中检查
   if abort_flags.get(session_id, False):
       yield "event: aborted\ndata: 已中断\n\n"
       break
   ```

2. **Checkpointer（检查点）**
   ```python
   checkpointer = MemorySaver()
   agent = create_react_agent(llm, tools, checkpointer=checkpointer)

   # LangGraph 自动保存每个节点后的状态
   # 中断时状态已保存，新消息到来时自动恢复
   ```

3. **Session ID（会话隔离）**
   ```python
   config = {
       "configurable": {"thread_id": session_id}
   }
   # 每个用户独立的对话线程
   ```
