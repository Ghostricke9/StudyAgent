"""
StudyHelper Agent - CLI 入口
知识学习智能助手：搜索资料 → 编撰教材 → 生成练习题
"""
import argparse
import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from config import OUTPUT_DIR, build_system_prompt
from agent.core import Agent
from agent.llm_client import LLMClient
from tools.executor import create_bridge

console = Console()
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def on_agent_step(event_type: str, name: str, detail: str):
    if event_type == "tool_start":
        console.print(f"\n[bold cyan]🔧 调用工具:[/] {name}")
    elif event_type == "tool_end":
        preview = detail[:200].replace("\n", " ")
        console.print(f"   [dim]结果: {preview}...[/]")


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
    console.rule("[bold]Agent 执行过程")

    try:
        result = agent.run(args.topic)
    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断[/]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]运行出错: {e}[/]")
        logging.getLogger().exception("Agent run failed")
        sys.exit(1)

    console.rule("[bold]最终结果")
    console.print(Markdown(result))

    console.print(f"\n[dim]💡 文件已保存到 {OUTPUT_DIR} 目录[/]")

    try:
        bridge.mcp.shutdown()
    except Exception:
        pass


if __name__ == "__main__":
    main()
