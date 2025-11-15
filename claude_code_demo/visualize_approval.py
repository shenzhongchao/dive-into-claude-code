"""
生成人工确认流程的可视化图
"""
from main import ClaudeCodeDemo
from config import ClaudeCodeConfig


def visualize_approval_graph():
    """生成带有人工确认功能的图可视化"""
    print("生成图可视化...")

    # 创建应用
    config = ClaudeCodeConfig(debug=True)
    demo = ClaudeCodeDemo(config)

    # 可视化
    try:
        png_data = demo.visualize("claude_code_approval_graph.png")
        print("✓ 图已保存到: claude_code_approval_graph.png")
        print("\n图结构概览:")
        print("  - 节点: agent, tools, approval, compression")
        print("  - 关键路径: agent → approval → tools")
        print("  - 条件边: should_continue() 识别敏感工具")
        return True
    except Exception as e:
        print(f"✗ 可视化失败: {e}")
        return False


if __name__ == "__main__":
    visualize_approval_graph()
