"""
Streaming + Steering Demo - 后端实现
使用 FastAPI + LangGraph 实现真正的流式输出和中断控制
"""
import os
import time
import asyncio
import uuid
from typing import AsyncGenerator, Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# LangGraph 和 LangChain
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage

# LLM - 根据你的环境选择

from langchain_community.chat_models import ChatTongyi
llm = ChatTongyi(model="qwen3-max", temperature=0)

print(f"✅ LLM 初始化成功: {llm.model_name}")


# ========== 工具定义 ==========
@tool
def search_database(query: str) -> str:
    """在数据库中搜索信息（模拟2秒延迟）"""
    for i in range(10):
        print(f"🔍 搜索: {query} {i}")
        time.sleep(1)
    return f"找到关于 '{query}' 的 3 条结果：结果1、结果2、结果3"


@tool
def calculate(expression: str) -> str:
    """计算数学表达式（模拟1秒延迟）"""
    print(f"🧮 计算: {expression}")
    try:
        for i in range(20):
            print(f"🧮 计算: {expression} {i}")
            time.sleep(0.5)
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"


@tool
def fetch_weather(city: str) -> str:
    """获取城市天气（模拟1.5秒延迟）"""
    print(f"🌤️ 获取天气: {city}")
    time.sleep(1.5)
    weather_data = {
        "北京": "晴天，温度 25°C",
        "上海": "多云，温度 28°C",
        "深圳": "阴天，温度 30°C"
    }
    return weather_data.get(city, f"{city}：晴天，温度 22°C")


# 工具列表
tools = [search_database, calculate, fetch_weather]


# ========== Agent 全局变量 ==========
checkpointer = MemorySaver()
agent = create_react_agent(llm, tools=tools, checkpointer=checkpointer)

# 存储每个会话的中断标志
abort_flags: Dict[str, bool] = {}


# ========== 请求模型 ==========
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # 修改为 Optional，正确处理 null


class AbortRequest(BaseModel):
    session_id: str


# ========== FastAPI 应用 ==========
app = FastAPI(title="Streaming + Steering Demo")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """健康检查"""
    return {"status": "running", "message": "Streaming + Steering Demo Backend"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    流式聊天端点（使用 SSE）
    支持中断和恢复
    """
    print(f"收到请求: {request}")
    print(f"消息: {request.message}")
    print(f"会话ID: {request.session_id}")

    # 生成或使用现有的 session_id
    session_id = request.session_id or str(uuid.uuid4())

    # 初始化中断标志
    abort_flags[session_id] = False

    print(f"\n{'='*60}")
    print(f"[会话 {session_id[:8]}] 新消息: {request.message}")
    print(f"{'='*60}\n")

    async def event_generator() -> AsyncGenerator[str, None]:
        """SSE 事件生成器"""
        try:
            # 配置
            config = {
                "configurable": {"thread_id": session_id}
            }

            # 🔑 检查是否有 pending 的 tool_calls（防止状态不一致）
            current_state = agent.get_state(config)
            if current_state.next and 'tools' in current_state.next:
                print(f"[会话 {session_id[:8]}] ⚠️ 检测到 pending 的 tool_calls，先完成它们")

                # 让 pending 的 tool_calls 执行完成
                async for msg, metadata in agent.astream(None, config, stream_mode="messages"):
                    if isinstance(msg, AIMessage) and msg.content:
                        yield f"event: token\ndata: {msg.content}\n\n"
                        asyncio.sleep(0.1) # 增强演示效果
                print(f"[会话 {session_id[:8]}] ✅ Pending tool_calls 已完成")

            # 输入消息
            input_msg = {"messages": [HumanMessage(content=request.message)]}

            # 发送会话 ID
            yield f"event: session_id\ndata: {session_id}\n\n"

            # 发送开始事件
            yield f"event: start\ndata: 开始处理...\n\n"

            # 流式执行 Agent
            async for msg, metadata in agent.astream(
                input_msg, config, stream_mode="messages"
            ):
                # 检查中断标志
                if abort_flags.get(session_id, False):
                    print(f"[会话 {session_id[:8]}] 🛑 检测到中断信号")
                    yield f"event: aborted\ndata: 执行已中断\n\n"
                    break

                # 只发送 AI 的回复内容
                if isinstance(msg, AIMessage) and msg.content:
                    # 发送 token
                    yield f"event: token\ndata: {msg.content}\n\n"
                    await asyncio.sleep(0.1) # 增强演示效果

            # 发送完成事件
            if not abort_flags.get(session_id, False):
                yield f"event: done\ndata: 完成\n\n"
                print(f"[会话 {session_id[:8]}] ✅ 完成")

        except Exception as e:
            print(f"[会话 {session_id[:8]}] ❌ 错误: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"

        finally:
            # 清理中断标志
            if session_id in abort_flags:
                del abort_flags[session_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/abort")
async def abort_chat(request: AbortRequest):
    """
    中断当前执行
    """
    session_id = request.session_id

    if session_id in abort_flags:
        abort_flags[session_id] = True
        print(f"[会话 {session_id[:8]}] 🛑 收到中断请求")
        return {"status": "success", "message": "中断信号已发送"}
    else:
        return {"status": "not_found", "message": "会话不存在或已结束"}


@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    """
    获取会话历史
    """
    try:
        config = {"configurable": {"thread_id": session_id}}
        state = agent.get_state(config)

        messages = []
        for msg in state.values.get("messages", []):
            messages.append({
                "role": "human" if isinstance(msg, HumanMessage) else "ai",
                "content": msg.content
            })

        return {
            "status": "success",
            "session_id": session_id,
            "messages": messages,
            "message_count": len(messages)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    """
    清除会话历史
    """
    # 注意：MemorySaver 没有直接的删除方法
    # 在生产环境中应该使用 RedisSaver 或其他支持删除的存储
    return {
        "status": "success",
        "message": "会话清除请求已接收（MemorySaver 暂不支持删除）"
    }


if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("🚀 Streaming + Steering Demo 后端启动")
    print("="*60)
    print(f"LLM: {llm.__class__.__name__}")
    print(f"工具数量: {len(tools)}")
    print("API 端点:")
    print("  - POST /api/chat        - 流式聊天")
    print("  - POST /api/abort       - 中断执行")
    print("  - GET  /api/history/:id - 获取历史")
    print("="*60)
    print("\n监听地址: http://localhost:8000")
    print("前端页面: 请在浏览器中打开 frontend.html\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
