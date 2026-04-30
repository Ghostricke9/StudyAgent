"""
MCP 客户端 - 通过 stdio 与 MCP Server 通信 (JSON-RPC 2.0)

MCP 协议要点:
  1. Transport: stdio (stdin/stdout)
  2. 编码: JSON-RPC 2.0, 每条消息以换行符分隔
  3. 握手: initialize(请求) → initialized(通知)
  4. 工具发现: tools/list
  5. 工具调用: tools/call
"""
import json
import logging
import subprocess
import threading
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

READ_TIMEOUT = 30
INIT_TIMEOUT = 10


class MCPClient:
    """单个 MCP Server 的客户端"""

    def __init__(self, name: str, command: str, args: list[str], env: dict | None = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env
        self.process: subprocess.Popen | None = None
        self._pending: dict[int, threading.Event] = {}
        self._results: dict[int, dict] = {}
        self._lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._running = False
        self.server_info: dict = {}

    def start(self) -> bool:
        """启动 MCP Server 进程并完成初始化握手"""
        try:
            merged_env = None
            if self.env:
                import os
                merged_env = os.environ.copy()
                merged_env.update(self.env)

            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=merged_env,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except FileNotFoundError:
            logger.error(f"MCP Server '{self.name}': 找不到命令 '{self.command}'")
            return False
        except Exception as e:
            logger.error(f"MCP Server '{self.name}': 启动失败 - {e}")
            return False

        self._running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

        try:
            result = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "clientInfo": {
                    "name": "studyhelper",
                    "version": "1.0.0",
                },
            }, timeout=INIT_TIMEOUT)

            self.server_info = result
            self._send_notification("initialized", {})
            logger.info(f"MCP Server '{self.name}' 初始化成功, 能力: {json.dumps(result, ensure_ascii=False)[:200]}")
            return True
        except Exception as e:
            logger.error(f"MCP Server '{self.name}': 初始化握手失败 - {e}")
            self.stop()
            return False

    def stop(self):
        """停止 MCP Server"""
        self._running = False
        if self.process:
            try:
                self.process.stdin.close()
            except Exception:
                pass
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

    def list_tools(self) -> list[dict]:
        """获取该 MCP Server 提供的工具列表"""
        try:
            result = self._send_request("tools/list", {})
            return result.get("tools", [])
        except Exception as e:
            logger.error(f"MCP Server '{self.name}': 获取工具列表失败 - {e}")
            return []

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        """调用 MCP Server 上的工具"""
        result = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        content = result.get("content", [])
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    texts.append(item["text"])
                elif isinstance(item, str):
                    texts.append(item)
            return "\n".join(texts)
        elif isinstance(content, str):
            return content
        return json.dumps(result, ensure_ascii=False)

    def is_running(self) -> bool:
        return self._running and self.process is not None and self.process.poll() is None

    def _send_request(self, method: str, params: dict, timeout: float = READ_TIMEOUT) -> dict:
        req_id = self._next_id()
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        event = threading.Event()
        with self._lock:
            self._pending[req_id] = event
            self._results.pop(req_id, None)

        self._write_line(json.dumps(request))

        if not event.wait(timeout=timeout):
            with self._lock:
                self._pending.pop(req_id, None)
            raise TimeoutError(f"MCP request '{method}' 超时 ({timeout}s)")

        with self._lock:
            result = self._results.pop(req_id, {})

        if "error" in result:
            err = result["error"]
            raise RuntimeError(f"MCP error [{err.get('code')}]: {err.get('message')}")
        return result.get("result", {})

    def _send_notification(self, method: str, params: dict):
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        self._write_line(json.dumps(notification))

    def _write_line(self, data: str):
        if self.process and self.process.stdin and self._running:
            try:
                self.process.stdin.write(data + "\n")
                self.process.stdin.flush()
            except Exception as e:
                logger.error(f"MCP Server '{self.name}': 写入失败 - {e}")
                self._running = False

    def _read_loop(self):
        """后台线程持续读取 stdout 的响应"""
        while self._running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(f"MCP Server '{self.name}': 无法解析消息 - {line[:200]}")
                    continue

                req_id = msg.get("id")
                if req_id is not None:
                    with self._lock:
                        self._results[req_id] = msg
                        event = self._pending.pop(req_id, None)
                    if event:
                        event.set()
            except Exception as e:
                if self._running:
                    logger.error(f"MCP Server '{self.name}': 读取异常 - {e}")
                break

        self._running = False
        logger.info(f"MCP Server '{self.name}': 读取线程退出")

    @staticmethod
    def _next_id() -> int:
        return int(time.time() * 1000000) % 2147483647
