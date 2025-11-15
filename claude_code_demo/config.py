"""
Claude Code Demo 配置文件
包含所有核心配置参数
"""
import os
from dataclasses import dataclass
from typing import Literal


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: Literal["openai", "tongyi"] = "openai"
    model: str = "gpt-5-mini"
    temperature: float = 0
    api_key: str = None

    def __post_init__(self):
        if self.api_key is None:
            if self.provider == "openai":
                self.api_key = os.getenv("OPENAI_API_KEY")
            elif self.provider == "tongyi":
                self.api_key = os.getenv("DASHSCOPE_API_KEY")


@dataclass
class TokenConfig:
    """Token 管理配置"""
    max_context_tokens: int = 100000  # 最大上下文 token
    compression_threshold: float = 0.92  # 压缩阈值 92%
    reserved_output_tokens: int = 4096  # 预留输出 token

    @property
    def trigger_compression_tokens(self) -> int:
        """触发压缩的 token 数"""
        return int(self.max_context_tokens * self.compression_threshold)


@dataclass
class SubAgentConfig:
    """SubAgent 配置"""
    type: str
    system_prompt: str
    allowed_tools: list = None  # None 表示所有工具（除了 TaskTool）


@dataclass
class TodoConfig:
    """Todo 任务管理配置"""
    max_concurrent_tasks: int = 5  # 最大并发任务数
    enable_auto_management: bool = True  # 启用自动任务管理


@dataclass
class HumanLoopConfig:
    """人机协同配置"""
    enable_review: bool = True  # 启用人工审查
    review_tool_names: list = None  # 需要审查的工具名称

    def __post_init__(self):
        if self.review_tool_names is None:
            self.review_tool_names = ["Read", "Write", "Edit"]


@dataclass
class CheckpointConfig:
    """检查点配置"""
    provider: Literal["memory", "redis", "postgresql"] = "memory"
    redis_url: str = "redis://localhost:6379"
    db_url: str = "postgresql://user:pass@localhost/dbname"


@dataclass
class ClaudeCodeConfig:
    """Claude Code Demo 主配置"""
    llm: LLMConfig = None
    token: TokenConfig = None
    subagent: list = None  # List[SubAgentConfig]
    todo: TodoConfig = None
    human_loop: HumanLoopConfig = None
    checkpoint: CheckpointConfig = None

    # 调试选项
    debug: bool = False
    enable_langsmith: bool = False

    def __post_init__(self):
        # 初始化默认配置
        if self.llm is None:
            self.llm = LLMConfig()
        if self.token is None:
            self.token = TokenConfig()
        if self.todo is None:
            self.todo = TodoConfig()
        if self.human_loop is None:
            self.human_loop = HumanLoopConfig()
        if self.checkpoint is None:
            self.checkpoint = CheckpointConfig()
        if self.subagent is None:
            self.subagent = self._get_default_subagents()

        # LangSmith 配置
        if self.enable_langsmith:
            os.environ["LANGSMITH_TRACING"] = "true"

    @staticmethod
    def _get_default_subagents() -> list:
        """获取默认的 SubAgent 配置"""
        return [
            SubAgentConfig(
                type="general-purpose",
                system_prompt="""You are a general-purpose AI assistant specialized in handling complex multi-step tasks.
- Excel at file searches, content analysis, and code understanding
- Approach complex problems systematically and break them down
- Always provide detailed and accurate analysis results""",
                allowed_tools=None  # 所有工具
            ),
            SubAgentConfig(
                type="code-analyzer",
                system_prompt="""You are a code analysis expert focused on:
- Code quality assessment and improvement recommendations
- Architecture design analysis and optimization
- Performance bottleneck identification and solutions
- Security vulnerability detection and fix suggestions
Please provide specific, actionable technical recommendations""",
                allowed_tools=["read_file", "search_in_files", "list_directory"]
            ),
            SubAgentConfig(
                type="document-writer",
                system_prompt="""You are a technical writing expert focused on:
- Clear and accurate technical documentation
- User-friendly operation guides
- Complete API documentation and examples
- Structured project documentation
Ensure readability and practicality of documentation""",
                allowed_tools=["read_file", "write_file", "edit_file"]
            )
        ]


# 创建默认配置实例
def get_default_config() -> ClaudeCodeConfig:
    """获取默认配置"""
    return ClaudeCodeConfig()


# 从环境变量创建配置
def get_config_from_env() -> ClaudeCodeConfig:
    """从环境变量创建配置"""
    config = ClaudeCodeConfig()

    # 覆盖 LLM 配置
    if os.getenv("LLM_PROVIDER"):
        config.llm.provider = os.getenv("LLM_PROVIDER")
    if os.getenv("LLM_MODEL"):
        config.llm.model = os.getenv("LLM_MODEL")

    # 覆盖调试选项
    config.debug = os.getenv("DEBUG", "false").lower() == "true"
    config.enable_langsmith = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"

    return config
