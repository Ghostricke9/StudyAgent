"""
MCP 管理器 - 管理多个 MCP Server, 聚合工具, 并桥接到 Agent 的 tool_executor
"""
import json
import logging
import os
from typing import Any

from mcp.client import MCPClient

logger = logging.getLogger(__name__)


def _mcp_to_openai_schema(mcp_tool: dict) -> dict:
    """将 MCP tool schema 转换为 OpenAI function calling schema"""
    input_schema = mcp_tool.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    return {
        "type": "function",
        "function": {
            "name": f"mcp__{mcp_tool['name']}",
            "description": mcp_tool.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


class MCPManager:
    def __init__(self, config_path: str = "mcp_servers.json"):
        self.clients: dict[str, MCPClient] = {}
        self.tool_registry: dict[str, tuple[str, str]] = {}
        self._load_config(config_path)

    def _load_config(self, config_path: str):
        if not os.path.exists(config_path):
            logger.warning(f"MCP 配置文件不存在: {config_path}")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        servers = config.get("mcpServers", {})
        for name, cfg in servers.items():
            if not cfg.get("enabled", False):
                continue

            client = MCPClient(
                name=name,
                command=cfg["command"],
                args=cfg.get("args", []),
                env=cfg.get("env"),
            )
            if client.start():
                self.clients[name] = client
                self._register_tools(name, client)
            else:
                logger.warning(f"跳过 MCP Server '{name}': 启动失败")

    def _register_tools(self, server_name: str, client: MCPClient):
        tools = client.list_tools()
        for tool in tools:
            tool_name = tool.get("name", "")
            if not tool_name:
                continue
            prefixed = f"mcp__{tool_name}"
            self.tool_registry[prefixed] = (server_name, tool_name)
            logger.info(f"注册 MCP 工具: {prefixed} (来自 {server_name})")

    def get_tool_schemas(self) -> list[dict]:
        schemas = []
        for server_name, client in self.clients.items():
            if not client.is_running():
                continue
            for tool in client.list_tools():
                schemas.append(_mcp_to_openai_schema(tool))
        return schemas

    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        if tool_name not in self.tool_registry:
            return json.dumps({
                "error": f"MCP 工具未注册: {tool_name}",
            }, ensure_ascii=False)

        server_name, original_name = self.tool_registry[tool_name]
        client = self.clients.get(server_name)
        if not client or not client.is_running():
            return json.dumps({
                "error": f"MCP Server '{server_name}' 未运行",
            }, ensure_ascii=False)

        try:
            return client.call_tool(original_name, arguments)
        except Exception as e:
            return json.dumps({
                "error": f"MCP 工具调用失败: {e}",
            }, ensure_ascii=False)

    def shutdown(self):
        for name, client in self.clients.items():
            logger.info(f"关闭 MCP Server '{name}'")
            client.stop()
        self.clients.clear()
        self.tool_registry.clear()
