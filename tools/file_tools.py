"""
文件工具 - 保存生成的教材文件
"""
import json
import os
import logging

from config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def save_document(content: str, filename: str, format: str = "md") -> str:
    """保存文档到输出目录"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
    if not safe_filename.strip():
        safe_filename = "output"

    if not safe_filename.endswith(f".{format}"):
        safe_filename = f"{safe_filename}.{format}"

    filepath = os.path.join(OUTPUT_DIR, safe_filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return json.dumps({"error": f"文件保存失败: {e}"}, ensure_ascii=False)

    return json.dumps({
        "success": True,
        "filepath": os.path.abspath(filepath),
        "filename": safe_filename,
        "size": len(content),
    }, ensure_ascii=False)


def load_document(filepath: str) -> str:
    """加载已保存的文档"""
    if not os.path.exists(filepath):
        return json.dumps({"error": f"文件不存在: {filepath}"}, ensure_ascii=False)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception as e:
        return json.dumps({"error": f"文件读取失败: {e}"}, ensure_ascii=False)


TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "save_document",
        "description": "将生成的教材、练习题等内容保存为文件到本地",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要保存的完整内容",
                },
                "filename": {
                    "type": "string",
                    "description": "文件名（不含路径），如 '微积分入门教材'",
                },
                "format": {
                    "type": "string",
                    "enum": ["md", "txt", "html"],
                    "description": "文件格式，推荐 md（Markdown）",
                },
            },
            "required": ["content", "filename"],
        },
    },
}
