"""
基础工具模块
包含文件操作等基础工具
"""
import os
from pathlib import Path
from langchain_core.tools import tool


@tool
def read_file(file_path: str) -> str:
    """
    读取文件内容

    Args:
        file_path: 文件路径

    Returns:
        文件内容
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File {file_path} does not exist"

        if not path.is_file():
            return f"Error: {file_path} is not a file"

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        return f"Content of {file_path}:\n\n{content}"
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"


@tool
def write_file(file_path: str, content: str) -> str:
    """
    写入文件内容（覆盖）

    Args:
        file_path: 文件路径
        content: 要写入的内容

    Returns:
        操作结果
    """
    try:
        path = Path(file_path)
        # 创建目录（如果不存在）
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing file {file_path}: {str(e)}"


@tool
def edit_file(file_path: str, old_content: str, new_content: str) -> str:
    """
    编辑文件内容（替换）

    Args:
        file_path: 文件路径
        old_content: 要替换的内容
        new_content: 新内容

    Returns:
        操作结果
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File {file_path} does not exist"

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        if old_content not in content:
            return f"Error: Content to replace not found in {file_path}"

        new_file_content = content.replace(old_content, new_content)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_file_content)

        return f"Successfully edited {file_path}"
    except Exception as e:
        return f"Error editing file {file_path}: {str(e)}"


@tool
def list_directory(directory_path: str = ".") -> str:
    """
    列出目录内容

    Args:
        directory_path: 目录路径，默认为当前目录

    Returns:
        目录内容列表
    """
    try:
        path = Path(directory_path)
        if not path.exists():
            return f"Error: Directory {directory_path} does not exist"

        if not path.is_dir():
            return f"Error: {directory_path} is not a directory"

        items = []
        for item in sorted(path.iterdir()):
            item_type = "DIR" if item.is_dir() else "FILE"
            items.append(f"[{item_type}] {item.name}")

        return f"Contents of {directory_path}:\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory {directory_path}: {str(e)}"


@tool
def search_in_files(pattern: str, directory: str = ".", file_extension: str = None) -> str:
    """
    在文件中搜索内容

    Args:
        pattern: 搜索模式
        directory: 搜索目录，默认为当前目录
        file_extension: 文件扩展名过滤（如 .py），可选

    Returns:
        搜索结果
    """
    try:
        path = Path(directory)
        if not path.exists():
            return f"Error: Directory {directory} does not exist"

        results = []
        for file_path in path.rglob(f"*{file_extension or ''}"):
            if file_path.is_file():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if pattern in content:
                            # 找到匹配的行
                            lines = content.split('\n')
                            matches = [
                                f"  Line {i+1}: {line.strip()}"
                                for i, line in enumerate(lines)
                                if pattern in line
                            ]
                            if matches:
                                results.append(f"{file_path}:\n" + "\n".join(matches))
                except:
                    continue

        if not results:
            return f"No matches found for '{pattern}' in {directory}"

        return f"Search results for '{pattern}':\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Error searching files: {str(e)}"


# 导出所有基础工具
def get_base_tools() -> list:
    """获取所有基础工具"""
    return [
        read_file,
        write_file,
        edit_file,
        list_directory,
        search_in_files
    ]
