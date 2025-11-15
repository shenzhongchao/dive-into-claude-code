"""
状态定义模块
定义 Agent 的状态结构
"""
from typing import Annotated, List, Literal, Optional
import uuid
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TodoItem(BaseModel):
    """Todo 任务项 - 使用 Pydantic 模型

    关键优势：
    - 自动类型验证
    - 自动生成默认值
    - LLM 可以直接生成符合此模型的数据
    """
    # LLM 如果忘记提供 ID，default_factory 会自动创建一个
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])

    # 必填字段
    name: str

    # 字段默认值
    desc: str = ""
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"

    # 可选字段
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    error: Optional[str] = None


class CompressionRecord(BaseModel):
    """压缩记录 - 使用 Pydantic 模型"""
    timestamp: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    removed_messages_count: int


class AgentState(BaseModel):
    """Agent 状态 - 使用 Pydantic 模型

    包含 Claude Code 的所有核心状态：
    - messages: 对话消息列表
    - todo_list: 任务列表
    - compression_history: 压缩历史记录
    - current_tokens: 当前 token 使用量
    - needs_compression: 是否需要压缩
    - human_review_pending: 是否等待人工审查

    关键优势：
    - 在 Pydantic 中使用 LangGraph 的 Reducer
    - 语法是 "Annotated[TYPE, REDUCER] = Field(default_factory=...)"
    """
    # 核心消息状态
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)

    # Todo 任务管理状态
    todo_list: List[TodoItem] = Field(default_factory=list)

    # 上下文压缩状态
    compression_history: List[CompressionRecord] = Field(default_factory=list)
    current_tokens: int = 0
    needs_compression: bool = False

    # 人机协同状态
    human_review_pending: bool = False
    pending_tool_call: Optional[dict] = None

    # # Pydantic v2 配置：允许任意类型（用于 BaseMessage）
    # model_config = {"arbitrary_types_allowed": True}


def create_initial_state() -> dict:
    """创建初始状态 - 返回字典供 LangGraph 使用

    注意：虽然 AgentState 是 Pydantic 模型，但 LangGraph 的输入应该是字典。
    LangGraph 会自动将字典转换为 Pydantic 实例。
    """
    return {
        "messages": [],
        "todo_list": [],
        "compression_history": [],
        "current_tokens": 0,
        "needs_compression": False,
        "human_review_pending": False,
        "pending_tool_call": None
    }


def add_message_to_state(state: AgentState, message: BaseMessage) -> dict:
    """添加消息到状态 - 返回更新字典供 LangGraph 使用"""
    return {"messages": [message]}


def update_todo_list(state: AgentState, todo_list: List[TodoItem]) -> dict:
    """更新 todo 列表 - 返回更新字典供 LangGraph 使用"""
    return {"todo_list": todo_list}


def mark_compression_needed(state: AgentState, current_tokens: int) -> dict:
    """标记需要压缩 - 返回更新字典供 LangGraph 使用"""
    return {
        "current_tokens": current_tokens,
        "needs_compression": True
    }


def add_compression_record(
    state: AgentState,
    record: CompressionRecord
) -> dict:
    """添加压缩记录 - 返回更新字典供 LangGraph 使用"""
    return {
        "compression_history": state.compression_history + [record],
        "needs_compression": False
    }


def set_human_review(
    state: AgentState,
    pending: bool,
    tool_call: Optional[dict] = None
) -> dict:
    """设置人工审查状态 - 返回更新字典供 LangGraph 使用"""
    return {
        "human_review_pending": pending,
        "pending_tool_call": tool_call
    }
