"""
Claude Code Demo - 使用示例
展示各种核心功能的使用方法
"""
import asyncio
from main import ClaudeCodeDemo
from config import ClaudeCodeConfig, LLMConfig, TokenConfig


async def example_1_basic_usage():
    """示例 1: 基础使用"""
    print("\n" + "="*60)
    print("示例 1: 基础使用 - 简单计算")
    print("="*60)

    app = ClaudeCodeDemo()
    await app.run("帮我计算 123 + 456 等于多少？")


async def example_2_file_operations():
    """示例 2: 文件操作"""
    print("\n" + "="*60)
    print("示例 2: 文件操作")
    print("="*60)

    app = ClaudeCodeDemo()
    await app.run("""
    请帮我完成以下操作：
    1. 列出当前目录的内容
    2. 读取 README.md 文件的前 10 行
    3. 并列出的目录内容写入tmp.txt中
    """)


async def example_3_complex_task():
    """示例 3: 复杂任务（自动使用 TodoList）"""
    print("\n" + "="*60)
    print("示例 3: 复杂任务 - 自动任务管理")
    print("="*60)

    app = ClaudeCodeDemo()
    await app.run("""
    帮我完成以下任务：
    1. 分析 nodes 目录下的代码结构
    2. 找出所有的 Python 文件
    3. 统计每个模块的文件数量
    4. 生成一个简单的项目结构报告,并将其写到当前文件夹的project_report.md中
    """)


async def example_4_subagent():
    """示例 4: SubAgent 使用"""
    print("\n" + "="*60)
    print("示例 4: SubAgent - 代码分析")
    print("="*60)

    app = ClaudeCodeDemo()
    await app.run("""
    请使用代码分析专家（code-analyzer）来分析 main.py 文件，
    关注以下方面：
    1. 代码质量
    2. 可能的性能问题
    3. 改进建议
    """)


async def example_5_human_loop():
    """示例 5: 人机协同"""
    print("\n" + "="*60)
    print("示例 5: 人机协同 - 需要确认的操作")
    print("="*60)

    app = ClaudeCodeDemo()
    await app.run("""
    我需要创建一个新的配置文件。
    请先询问我想要什么样的配置，然后再创建文件。
    """)


async def example_6_custom_config():
    """示例 6: 自定义配置"""
    print("\n" + "="*60)
    print("示例 6: 自定义配置")
    print("="*60)

    # 创建自定义配置
    config = ClaudeCodeConfig(
        llm=LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            temperature=0.3  # 更低的温度，更确定的输出
        ),
        token=TokenConfig(
            max_context_tokens=50000,  # 较小的上下文
            compression_threshold=0.85  # 更早触发压缩
        ),
        debug=True  # 启用调试输出
    )

    app = ClaudeCodeDemo(config)
    await app.run("测试自定义配置：计算 1+1")


async def example_7_compression():
    """示例 7: 上下文压缩演示"""
    print("\n" + "="*60)
    print("示例 7: 上下文压缩")
    print("="*60)

    # 使用较小的 token 限制来快速触发压缩
    config = ClaudeCodeConfig(
        token=TokenConfig(
            max_context_tokens=5000,  # 小的上下文
            compression_threshold=0.7  # 低阈值，容易触发
        )
    )

    app = ClaudeCodeDemo(config)
    thread_id = "compression-test"

    # 发送多条消息，触发压缩
    messages = [
        "请详细介绍一下 Python 的历史",
        "继续讲讲 Python 的主要特性",
        "Python 有哪些流行的框架？",
        "详细说说 Django 框架",
        "现在总结一下我们讨论的所有内容"
    ]

    for msg in messages:
        await app.run(msg, thread_id=thread_id)


async def example_8_interactive():
    """示例 8: 交互式模式"""
    print("\n" + "="*60)
    print("示例 8: 交互式模式")
    print("="*60)

    app = ClaudeCodeDemo()
    await app.run_interactive()


async def main():
    """运行所有示例"""
    print("\n🎯 Claude Code Demo - 使用示例集合\n")

    examples = [
        ("基础使用", example_1_basic_usage),
        ("文件操作", example_2_file_operations),
        ("复杂任务", example_3_complex_task),
        ("SubAgent", example_4_subagent),
        ("人机协同", example_5_human_loop),
        ("自定义配置", example_6_custom_config),
        ("上下文压缩", example_7_compression),
        ("交互式模式", example_8_interactive),
    ]

    print("请选择要运行的示例：\n")
    for i, (name, _) in enumerate(examples, 1):
        print(f"{i}. {name}")
    print(f"{len(examples) + 1}. 运行所有示例（除了交互式）")
    print("0. 退出")

    try:
        choice = input("\n请输入选项 (0-{}): ".format(len(examples) + 1)).strip()

        if choice == "0":
            print("再见！")
            return

        if choice == str(len(examples) + 1):
            # 运行所有示例（除了交互式）
            for name, func in examples[:-1]:  # 排除最后一个交互式
                try:
                    await func()
                except Exception as e:
                    print(f"\n❌ 示例 '{name}' 出错: {e}\n")
        else:
            # 运行单个示例
            idx = int(choice) - 1
            if 0 <= idx < len(examples):
                _, func = examples[idx]
                await func()
            else:
                print("无效的选项")

    except ValueError:
        import traceback
        traceback.print_exc()
        print("请输入有效的数字")
    except KeyboardInterrupt:
        print("\n\n再见！")


if __name__ == "__main__":
    asyncio.run(main())
