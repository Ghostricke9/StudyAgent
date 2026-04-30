"""
统一工具执行器 - 桥接本地工具、MCP工具、Skills三层

Agent 通过此模块获得完整的工具调用能力。
执行优先级：本地工具 > Skills > MCP工具
"""
import json
import logging

from tools.web_search import web_search, TOOL_SCHEMA as SEARCH_SCHEMA
from tools.web_fetch import fetch_webpage, TOOL_SCHEMA as FETCH_SCHEMA
from tools.file_tools import save_document, TOOL_SCHEMA as SAVE_SCHEMA
from skills.registry import SkillRegistry
from mcp.manager import MCPManager

logger = logging.getLogger(__name__)

LOCAL_TOOLS: dict[str, callable] = {
    "web_search": web_search,
    "fetch_webpage": fetch_webpage,
    "save_document": save_document,
}

LOCAL_TOOL_SCHEMAS = [SEARCH_SCHEMA, FETCH_SCHEMA, SAVE_SCHEMA]


class ToolBridge:
    """统一工具桥接层"""

    def __init__(self, skill_registry: SkillRegistry, mcp_manager: MCPManager):
        self.skills = skill_registry
        self.mcp = mcp_manager

    def get_all_schemas(self) -> list[dict]:
        schemas = list(LOCAL_TOOL_SCHEMAS)
        schemas.extend(self.skills.get_schemas())
        schemas.extend(self.mcp.get_tool_schemas())
        return schemas

    def execute(self, tool_name: str, arguments: dict) -> str:
        # 1. 本地工具
        if tool_name in LOCAL_TOOLS:
            func = LOCAL_TOOLS[tool_name]
            try:
                return func(**arguments)
            except TypeError as e:
                return json.dumps({"error": f"参数错误: {e}"}, ensure_ascii=False)

        # 2. Skills
        if tool_name in self.skills.skills:
            return self.skills.execute(tool_name, arguments)

        # 3. MCP 工具 (前缀 mcp__)
        if tool_name.startswith("mcp__"):
            return self.mcp.execute_tool(tool_name, arguments)

        return json.dumps({
            "error": f"未知工具: {tool_name}",
            "available_tools": list(LOCAL_TOOLS.keys())
            + list(self.skills.skills.keys())
            + list(self.mcp.tool_registry.keys()),
        }, ensure_ascii=False)


def create_bridge() -> ToolBridge:
    skill_registry = SkillRegistry()
    mcp_manager = MCPManager()
    return ToolBridge(skill_registry, mcp_manager)
