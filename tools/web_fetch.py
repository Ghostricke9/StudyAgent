"""
网页内容抓取工具 - 获取网页并提取正文
"""
import json
import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _clean_html(html: str) -> str:
    """从 HTML 中提取干净的正文文本"""
    soup = BeautifulSoup(html, "lxml" if _has_lxml() else "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped) > 20:
            lines.append(stripped)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    if len(cleaned) > 8000:
        cleaned = cleaned[:8000] + "\n\n... [内容过长, 已截断]"

    return cleaned


def _has_lxml() -> bool:
    try:
        import lxml
        return True
    except ImportError:
        return False


def fetch_webpage(url: str) -> str:
    """抓取网页内容并返回清洗后的文本"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        return json.dumps({
            "error": f"网页请求失败: {e}",
            "url": url,
        }, ensure_ascii=False)

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        return json.dumps({
            "warning": f"非文本内容 (Content-Type: {content_type})，可能无法正确解析",
            "preview": resp.text[:500],
        }, ensure_ascii=False)

    try:
        resp.encoding = resp.apparent_encoding or "utf-8"
        text = _clean_html(resp.text)
    except Exception as e:
        return json.dumps({
            "error": f"HTML解析失败: {e}",
            "raw_preview": resp.text[:1000],
        }, ensure_ascii=False)

    if not text.strip():
        return json.dumps({
            "warning": "未能提取到有效文本内容，页面可能为纯JS渲染",
            "url": url,
        }, ensure_ascii=False)

    return json.dumps({
        "url": url,
        "content": text,
        "length": len(text),
    }, ensure_ascii=False)


TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_webpage",
        "description": "获取指定网页的正文文本内容。自动去除广告、导航等无关内容，适合抓取文章、教程等。",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的网页URL",
                },
            },
            "required": ["url"],
        },
    },
}
