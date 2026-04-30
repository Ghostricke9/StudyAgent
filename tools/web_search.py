"""
网页搜索工具 - 基于 DuckDuckGo（免费无需 API Key）
"""
import json
import logging

logger = logging.getLogger(__name__)


def web_search(query: str, num_results: int = 5) -> str:
    try:
        from ddgs import DDGS
    except ImportError:
        return json.dumps({
            "error": "请先安装 ddgs: pip install ddgs",
            "results": [],
        }, ensure_ascii=False)

    import time

    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=num_results))
            break
        except Exception as e:
            if "403" in str(e) or "Ratelimit" in str(e):
                wait = (attempt + 1) * 3
                logger.warning(f"DuckDuckGo ratelimit, retrying in {wait}s (attempt {attempt + 1}/3)")
                time.sleep(wait)
            elif attempt < 2:
                logger.warning(f"DuckDuckGo text search failed: {e}, retrying...")
                time.sleep(2)
            else:
                logger.warning(f"DuckDuckGo text search failed: {e}, trying news fallback")
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.news(query, max_results=num_results))
                except Exception as e2:
                    return json.dumps({
                        "error": f"搜索失败: {e2}",
                        "results": [],
                    }, ensure_ascii=False)
                break

    if not results:
        return json.dumps({
            "message": "未找到相关结果，请尝试更换搜索关键词",
            "results": [],
        }, ensure_ascii=False)

    formatted = []
    for i, r in enumerate(results, 1):
        formatted.append({
            "index": i,
            "title": r.get("title", "无标题"),
            "url": r.get("href", r.get("url", "")),
            "snippet": r.get("body", r.get("snippet", ""))[:300],
        })

    return json.dumps({"results": formatted}, ensure_ascii=False)


TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "搜索网页获取与主题相关的资料列表。返回包含标题、URL和摘要的结果。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，建议中英文各搜一次以扩大范围",
                },
                "num_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认5，建议3-8",
                },
            },
            "required": ["query"],
        },
    },
}
