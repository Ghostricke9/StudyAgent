"""
统一工具执行器 - 桥接本地工具、MCP工具、Skills三层

Agent 通过此模块获得完整的工具调用能力。
Skills 采用渐进式披露：Layer 1 注入 system prompt，Layer 2 通过 load_skill 获取正文。
"""
import json
import logging

from tools.web_search import web_search, TOOL_SCHEMA as SEARCH_SCHEMA
from tools.web_fetch import fetch_webpage, TOOL_SCHEMA as FETCH_SCHEMA
from tools.file_tools import save_document, TOOL_SCHEMA as SAVE_SCHEMA
from tools.load_skill import load_skill, TOOL_SCHEMA as LOAD_SKILL_SCHEMA
from mcp.manager import MCPManager

logger = logging.getLogger(__name__)

LOCAL_TOOLS: dict[str, callable] = {
    "web_search": web_search,
    "fetch_webpage": fetch_webpage,
    "save_document": save_document,
    "load_skill": load_skill,
}

LOCAL_TOOL_SCHEMAS = [SEARCH_SCHEMA, FETCH_SCHEMA, SAVE_SCHEMA, LOAD_SKILL_SCHEMA]


class ToolBridge:
    def __init__(self, mcp_manager: MCPManager):
        self.mcp = mcp_manager

    def get_all_schemas(self) -> list[dict]:
        schemas = list(LOCAL_TOOL_SCHEMAS)
        schemas.extend(self.mcp.get_tool_schemas())
        return schemas

    def execute(self, tool_name: str, arguments: dict) -> str:
        if tool_name in LOCAL_TOOLS:
            func = LOCAL_TOOLS[tool_name]
            try:
                return func(**arguments)
            except TypeError as e:
                return json.dumps({"error": f"参数错误: {e}"}, ensure_ascii=False)

        if tool_name.startswith("mcp__"):
            return self.mcp.execute_tool(tool_name, arguments)

        return json.dumps({
            "error": f"未知工具: {tool_name}",
            "available_tools": list(LOCAL_TOOLS.keys()) + list(self.mcp.tool_registry.keys()),
        }, ensure_ascii=False)


def create_bridge() -> ToolBridge:
    mcp_manager = MCPManager()
    return ToolBridge(mcp_manager)
