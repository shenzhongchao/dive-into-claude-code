"""
压缩提示词模块
实现 Claude Code 的 8 段式压缩策略
"""

# 8 段式压缩提示词（基于 Claude Code 的设计）
COMPRESSION_PROMPT = """Your task is to create a detailed summary of the conversation so far,
paying close attention to the user's explicit requests and your previous actions.
This summary should be thorough in capturing technical details, code patterns,
and architectural decisions that would be essential for continuing development
work without losing context.

Before providing your final summary, wrap your analysis in <analysis> tags to
organize your thoughts and ensure you've covered all necessary points.

Your summary should include the following sections:

1. **Primary Request and Intent**: Capture all of the user's explicit requests and intents in detail

2. **Key Technical Concepts**: List all important technical concepts, technologies, and frameworks discussed.

3. **Files and Code Sections**: Enumerate specific files and code sections examined, modified, or created.
   Pay special attention to the most recent messages and include full code snippets where applicable.

4. **Errors and Fixes**: List all errors that you ran into, and how you fixed them.
   Pay special attention to specific user feedback.

5. **Problem Solving**: Document problems solved and any ongoing troubleshooting efforts.

6. **All User Messages**: List ALL user messages that are not tool results.
   These are critical for understanding the users' feedback and changing intent.

7. **Pending Tasks**: Outline any pending tasks that you have explicitly been asked to work on.

8. **Current Work**: Describe in detail precisely what was being worked on immediately before this summary request.

9. **Optional Next Step**: List the next step that you will take that is related to the most recent work you were doing.

Please provide a comprehensive summary following this structure. Remember to use <analysis> tags
to show your thinking process before the final summary.
"""


# 压缩结果格式化提示词
COMPRESSION_RESULT_PREFIX = """# Conversation Summary (Context Compression)

The following is a compressed summary of our previous conversation to manage context length:

"""


def get_compression_prompt() -> str:
    """获取压缩提示词"""
    return COMPRESSION_PROMPT


def format_compression_result(summary: str) -> str:
    """格式化压缩结果"""
    return f"{COMPRESSION_RESULT_PREFIX}{summary}"


def get_compression_system_prompt() -> str:
    """获取压缩专用的系统提示词"""
    return """You are a specialized AI assistant for conversation summarization.
Your task is to create detailed, structured summaries of conversations while preserving
all critical information needed to continue the work seamlessly.

Focus on:
- Technical accuracy
- Preserving code patterns and architectural decisions
- Capturing all user requests and feedback
- Maintaining context for ongoing work
- Clear, well-organized structure

Always use the <analysis> tag to organize your thoughts before providing the final summary.
"""
