"""
StudyHelper Agent - CLI 入口
知识学习智能助手：搜索资料 → 编撰教材 → 生成练习题
"""
import argparse
import json
import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.text import Text

from config import OUTPUT_DIR, build_system_prompt
from agent.core import Agent
from agent.llm_client import LLMClient
from tools.executor import create_bridge

console = Console()
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

ICON_MAP = {"pending": "⬜", "in_progress": "⟳", "completed": "✅"}
STATUS_LABEL = {"pending": "待开始", "in_progress": "进行中", "completed": "已完成"}
TOOL_ICONS = {
    "web_search": "🔍",
    "fetch_webpage": "📥",
    "save_document": "💾",
    "load_skill": "📖",
    "todo_write": "📋",
    "task": "🚀",
}

_last_todo_items: list[dict] = []
_round_tools: list[tuple[str, str, str]] = []


def _todo_changed(new_items: list[dict]) -> bool:
    if len(new_items) != len(_last_todo_items):
        return True
    for a, b in zip(_last_todo_items, new_items):
        if a["status"] != b["status"] or a["text"] != b["text"]:
            return True
    return False


def _render_todo_panel(items: list[dict]):
    if not items:
        return
    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("icon", width=2)
    table.add_column("text", ratio=1)
    table.add_column("status", width=6, justify="right")
    for item in items:
        icon = ICON_MAP.get(item["status"], "❓")
        style = "bold cyan" if item["status"] == "in_progress" else ""
        status_text = STATUS_LABEL.get(item["status"], item["status"])
        status_style = {"in_progress": "cyan", "completed": "green", "pending": "dim"}.get(item["status"], "")
        table.add_row(icon, Text(item["text"], style=style), Text(status_text, style=status_style))
    panel = Panel(table, title="[bold]📋 任务进度[/]", border_style="blue", padding=(1, 1))
    console.print(panel)


def _render_tool_line(tool_name: str, result_preview: str):
    icon = TOOL_ICONS.get(tool_name, "🔧")
    name_colored = f"[bold yellow]{tool_name}[/]"
    preview = result_preview[:100].replace("\n", " ").strip()
    console.print(f"  {icon} {name_colored} [dim]→[/] {preview}")


def on_agent_step(event_type: str, name: str, detail: str):
    global _last_todo_items, _round_tools

    if event_type == "tool_start":
        _round_tools.append(("start", name, detail))

    elif event_type == "tool_end":
        _round_tools.append(("end", name, detail))

    elif event_type == "todo_update":
        try:
            items = json.loads(detail)
        except (json.JSONDecodeError, TypeError):
            return
        if _todo_changed(items):
            _last_todo_items = items
            _render_todo_panel(items)

    elif event_type == "compact_start":
        console.print(f"\n[bold yellow]⚡ 上下文压缩触发 ({name}):[/] {detail} tokens → 压缩中...")

    elif event_type == "compact_end":
        console.print(f"[bold green]✓ 压缩完成:[/] 剩余 {detail} tokens")

    elif event_type == "round_end":
        round_num = int(detail) if detail.isdigit() else detail
        for evt, tname, tdetail in _round_tools:
            if evt == "end":
                _render_tool_line(tname, tdetail)
        _round_tools = []
        console.print(f"[dim]── 第 {round_num} 轮 ──[/]")


def main():
    parser = argparse.ArgumentParser(description="知识学习智能助手")
    parser.add_argument("topic", nargs="?", help="你想学习的主题，如 '微积分入门'")
    parser.add_argument("--output", "-o", default=OUTPUT_DIR, help="输出目录")
    args = parser.parse_args()

    if not args.topic:
        args.topic = console.input("[bold green]请输入你想学习的主题:[/] ")

    console.print(Panel.fit(
        "[bold yellow]StudyHelper Agent[/]\n"
        "智能检索网页资料 → 编撰教学教材 → 生成配套练习题",
        border_style="blue",
    ))

    console.print(f"\n[bold]📚 学习主题:[/] {args.topic}")
    console.print(f"[bold]📁 输出目录:[/] {args.output}\n")
    console.print("[dim]正在初始化 Agent...[/]")

    bridge = create_bridge()
    llm = LLMClient()
    agent = Agent(
        llm=llm,
        tool_schemas=bridge.get_all_schemas(),
        tool_executor=bridge.execute,
        on_step=on_agent_step,
        system_prompt=build_system_prompt(),
    )

    console.print("[dim]Agent 就绪！开始工作...[/]\n")

    try:
        result = agent.run(args.topic)
    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断[/]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]运行出错: {e}[/]")
        logging.getLogger().exception("Agent run failed")
        sys.exit(1)

    if _last_todo_items:
        console.print()
        _render_todo_panel(_last_todo_items)

    console.rule("[bold]最终结果")
    console.print(Markdown(result))

    console.print(f"\n[dim]💡 文件已保存到 {OUTPUT_DIR} 目录[/]")

    try:
        bridge.mcp.shutdown()
    except Exception:
        pass


if __name__ == "__main__":
    main()
