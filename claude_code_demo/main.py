"""
Claude Code Demo - 主入口
基于 Python LangGraph 实现的 Claude Code 核心功能演示
"""
import asyncio
import uuid
import sys
import os
from typing import Optional


from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatTongyi

# 尝试相对导入，如果失败则使用绝对导入

from config import ClaudeCodeConfig, get_default_config
from core.graph import build_graph, visualize_graph
from core.state import create_initial_state


# 修复 Windows 控制台编码问题
def setup_console_encoding():
    """设置控制台编码为 UTF-8"""
    if sys.platform == "win32":
        try:
            # 设置控制台代码页为 UTF-8
            os.system("chcp 65001 > nul")
            # 重新配置标准输出
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass


def safe_print(text: str, **kwargs):
    """安全打印，处理 Windows 控制台编码问题"""
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        # 在 Windows 上移除不支持的字符
        text = text.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
        print(text, **kwargs)


class ClaudeCodeDemo:
    """Claude Code Demo 应用"""

    def __init__(self, config: Optional[ClaudeCodeConfig] = None):
        """
        初始化应用

        Args:
            config: 配置对象，默认使用默认配置
        """
        self.config = config or get_default_config()

        # 初始化 LLM
        self.llm = self._init_llm()

        # 构建图
        self.app = build_graph(self.config, self.llm)

        safe_print("✅ Claude Code Demo initialized")
        safe_print(f"   LLM: {self.config.llm.provider} - {self.config.llm.model}")
        safe_print(f"   Max tokens: {self.config.token.max_context_tokens}")
        safe_print(f"   Compression threshold: {self.config.token.compression_threshold}")

    def _init_llm(self):
        """初始化语言模型"""
        if self.config.llm.provider == "openai":
            return ChatOpenAI(
                model=self.config.llm.model,
                temperature=self.config.llm.temperature,
                api_key=self.config.llm.api_key
            )
        elif self.config.llm.provider == "tongyi":
            return ChatTongyi(
                model=self.config.llm.model,
                temperature=self.config.llm.temperature,
                dashscope_api_key=self.config.llm.api_key
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.config.llm.provider}")

    async def run(self, message: str, thread_id: Optional[str] = None):
        """
        运行 Agent，支持人工确认

        Args:
            message: 用户消息
            thread_id: 线程 ID，用于会话持久化
        """
        from langgraph.types import Command

        if thread_id is None:
            thread_id = str(uuid.uuid4())

        print(f"\n{'='*60}")
        print(f"Thread ID: {thread_id}")
        print(f"User: {message}")
        print(f"{'='*60}\n")

        # 准备输入 - 使用完整的初始状态
        input_data = create_initial_state()
        input_data["messages"] = [HumanMessage(content=message)]

        # 配置
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 100
        }

        # 执行循环，处理可能的 interrupt
        while True:
            # 简化版本：直接使用 ainvoke
            result = await self.app.ainvoke(input_data, config)
            final_message = result["messages"][-1]
            print(f"\nAssistant: {final_message.content}\n")

            # 检查是否被中断（需要人工确认）
            state = await self.app.aget_state(config)

            # 如果没有下一个节点，说明执行完成
            if not state.next:
                break

            # 检查是否有 interrupt 值
            if hasattr(state, 'tasks') and state.tasks:
                # 有待处理的任务，可能是 interrupt
                interrupt_found = False
                for task in state.tasks:
                    if hasattr(task, 'interrupts') and task.interrupts:
                        # 找到 interrupt 信息
                        interrupt_data = task.interrupts[0].value
                        interrupt_found = True

                        # 显示确认信息
                        print("\n" + "="*60)
                        # interrupt_data 包含 "question" 字段（来自 ask_human 工具）
                        question = interrupt_data.get("question", interrupt_data.get("message", "Approval required"))
                        print(question)
                        print("="*60)

                        # 获取用户输入
                        user_input = input("\nYour response: ").strip()

                        # 使用 Command 恢复执行
                        input_data = Command(resume=user_input)
                        break

                if interrupt_found:
                    continue

            # 没有找到 interrupt，但还有 next，可能是其他情况，退出
            break

    async def run_interactive(self):
        """交互式运行"""
        thread_id = str(uuid.uuid4())
        safe_print("\n🤖 Claude Code Demo - Interactive Mode")
        safe_print("Type 'exit' to quit, 'new' to start a new conversation\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() == "exit":
                    print("Goodbye!")
                    break

                if user_input.lower() == "new":
                    thread_id = str(uuid.uuid4())
                    print(f"Started new conversation (thread: {thread_id})\n")
                    continue

                if not user_input:
                    continue

                await self.run(user_input, thread_id=thread_id)

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")

    def visualize(self, output_path: str = "graph.png"):
        """
        可视化图结构

        Args:
            output_path: 输出文件路径
        """
        png_data = visualize_graph(self.app)
        if png_data:
            with open(output_path, "wb") as f:
                f.write(png_data)
            safe_print(f"✅ Graph visualization saved to {output_path}")
        else:
            safe_print("❌ Failed to generate graph visualization")


async def main():
    """主函数"""
    # 设置控制台编码
    setup_console_encoding()

    # 创建配置
    config = get_default_config()

    # 创建应用
    app = ClaudeCodeDemo(config)

    # 可视化图（可选）
    app.visualize("claude_code_graph.png")

    # 运行示例
    print("\n" + "="*60)
    print("Claude Code Demo - Example Usage")
    print("="*60 + "\n")

    # 示例 1: 简单问答
    # await app.run("帮我计算 123 + 456 等于多少？")

    # 示例 2: 文件操作（需要确认）
    # await app.run("请帮我创建一个文件 test.txt，内容是 'Hello, Claude Code!'")

    # 示例 3: 复杂任务（会使用 TodoList）
    await app.run("帮我分析一下当前目录下的所有 Python 文件，找出可能的代码质量问题")

    # 交互式模式
    # await app.run_interactive()


if __name__ == "__main__":
    asyncio.run(main())
