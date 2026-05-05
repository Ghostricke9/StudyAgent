# 📚 StudyHelper — 一个 Agent 框架教学项目

> 如果你正在学习 Claude Code 的 harness 框架源码，或者想理解 **Function Call + Skills + MCP** 三者如何共同构成一个完整 Agent —— 这个项目就是为你准备的。

---

## 目录

- [1. 这个项目是什么](#1-这个项目是什么)
- [2. Agent 框架全景：Harness 架构深度解析](#2-agent-框架全景harness-架构深度解析)
  - [2.1 整体架构图](#21-整体架构图)
  - [2.2 主循环（ReAct Loop）详解](#22-主循环react-loop详解)
  - [2.3 消息流转全链路](#23-消息流转全链路)
  - [2.4 Harness 核心：Tool Registry 模式](#24-harness-核心tool-registry-模式)
- [3. 三层能力体系的定位与关系](#3-三层能力体系的定位与关系)
- [4. 教学：如何添加自己的 Tool](#4-教学如何添加自己的-tool)
- [5. 教学：如何添加自己的 Skill](#5-教学如何添加自己的-skill)
- [6. 教学：如何接入 MCP Server](#6-教学如何接入-mcp-server)
  - [6.1 MCP 协议快速理解](#61-mcp-协议快速理解)
  - [6.2 配置一个新的 MCP Server](#62-配置一个新的-mcp-server)
  - [6.3 MCP 客户端的核心实现](#63-mcp-客户端的核心实现)
  - [6.4 排错指南：MCP 连不上的常见原因](#64-排错指南mcp-连不上的常见原因)
- [7. 快速开始](#7-快速开始)
- [8. 项目结构](#8-项目结构)
- [9. 进阶：如何改造为通用的 Harness 框架](#9-进阶如何改造为通用的-harness-框架)

---

## 1. 这个项目是什么

**StudyHelper** 是一个知识学习智能体，用户输入想学的主题，Agent 自动完成：

```
用户: "我想学微积分"
  → 🔍 搜索网页资料
  → 📥 抓取文章正文
  → 📝 编撰分章节教学教材
  → ✍️ 为每章生成练习题（选择/填空/简答/实践）
  → 💾 保存为 Markdown 文件
```

**但它更重要的角色是作为 Agent 框架的教学蓝图。** 这个项目刻意把 Function Call、Skills、MCP 三个概念拆解为独立层，让你能看清楚每一层是怎么"插"进 Agent 的，以及它们之间的数据如何流动。

如果你在学 Claude Code 的源码，你会发现：
- Claude Code 的 `harness` 就是一个更复杂的 ReAct Loop
- Claude Code 的 `tools/` 目录就是本地工具层
- Claude Code 的 `.mcp.json` 配置就是这个项目的 `mcp_servers.json` 的增强版
- Claude Code 的 Skills 本质上也是"注入提示词"这个模式

---

## 2. Agent 框架全景：Harness 架构深度解析

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                        入口层 (Entry Point)                        │
│   main.py (CLI)  /  ui/app.py (Web)                              │
│   负责：接收用户输入、展示执行过程、输出最终结果                      │
└─────────────────────────────┬────────────────────────────────────┘
                              │ 传入: user_input
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Agent Core (Harness 主循环)                      │
│   agent/core.py                                                   │
│                                                                    │
│   while iteration < MAX_TOOL_CALLS:                                │
│     response = llm.chat(messages, tools=tool_schemas)   ──────┐  │
│     if response has no tool_calls:                            │  │
│       return response.content  ← 最终答案                     │  │
│     for each tool_call in response:                           │  │
│       result = tool_executor(tool_name, tool_args)  ──────┐  │  │
│       messages.append(tool_result)                        │  │  │
│                                                           │  │  │
└───────────────────────────────────────────────────────────┼──┼──┘
                                                            │  │
                  ┌─────────────────────────────────────────┘  │
                  │  tool_schemas (本地 + load_skill + MCP)     │
                  │  system_prompt (含 Skill 描述 - Layer 1)    │
                  ▼                                            │
┌──────────────────────────────────────────────────────────┐   │
│                 LLM Client (大模型接口)                     │   │
│   agent/llm_client.py                                      │   │
│                                                            │   │
│   封装 OpenAI 兼容 API:                                     │   │
│   - chat(messages, tools) → 支持 Function Call 的对话       │   │
│   - parse_tool_calls() → 从响应中提取工具调用               │   │
│   - build_tool_schema() → 构造符合规范的 schema             │   │
└──────────────────────────────────────────────────────────┘   │
                                                               │
                  ┌────────────────────────────────────────────┘
                  │  tool_executor(name, args)
                  ▼
┌──────────────────────────────────────────────────────────────────┐
│              ToolBridge (统一工具执行器)                            │
│   tools/executor.py                                                │
│                                                                    │
│   execute(tool_name, args):                                        │
│     if tool_name in LOCAL_TOOLS:        → 调用本地函数             │
│     elif tool_name.startswith("mcp__"): → 转发给 MCP Server       │
└──────────────────────────────┬────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐
│   本地工具层      │  │  Skills 技能层   │  │    MCP 工具层     │
│                 │  │  (间接调用)      │  │                  │
│ web_search      │  │                 │  │ mcp__fetch        │
│ fetch_webpage   │  │ [启动时]        │  │ mcp__brave_search │
│ save_document   │  │ SkillLoader     │  │ ... (自动发现)     │
│ load_skill ─────┼──┤ 扫描 SKILL.md   │  │                  │
│                 │  │ → 注入 system   │  │ 本质:             │
│ 本质:           │  │   prompt (L1)   │  │ 通过 stdio        │
│ Python 函数     │  │                 │  │ JSON-RPC 调用     │
│ 直接执行        │  │ [运行时]        │  │ 外部进程工具      │
│                 │  │ load_skill()    │  │                  │
│                 │  │ → 返回完整      │  │                  │
│                 │  │   SKILL.md (L2) │  │                  │
└─────────────────┘  └─────────────────┘  └──────────────────┘
```

### 2.2 主循环（ReAct Loop）详解


```python
# agent/core.py 的核心逻辑（简化版）

class Agent:
    def run(self, user_input: str) -> str:
        # 第0步：组装初始消息
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},   # 你是谁，能干什么
            {"role": "user",   "content": user_input},       # 用户想干什么
        ]

        # 第1步：进入循环 —— 这就是 Harness 的核心
        for iteration in range(MAX_TOOL_CALLS):  # 最多迭代 N 次，防止死循环

            # 1a. 把当前所有消息 + 所有可用工具定义发给 LLM
            response = self.llm.chat(
                messages=self.messages,
                tools=self.tool_schemas   # ← 所有工具的 schema 列表
            )

            # 1b. LLM 返回 assistant 消息，追加到历史
            assistant_msg = self.llm.assistant_message(response)
            self.messages.append(assistant_msg)

            # 1c. 检查 LLM 是否想调用工具
            tool_calls = self.llm.parse_tool_calls(response)

            if not tool_calls:
                # LLM 不再需要工具 = 完成了！直接输出文本
                return assistant_msg["content"]

            # 1d. LLM 想调用工具 → 逐个执行
            for tc in tool_calls:
                result = self.tool_executor(tc["name"], tc["arguments"])

                # 1e. 把工具执行结果追加到消息历史
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            # 1f. 回到循环顶部，LLM 看到工具结果后继续决策
            #     可能继续调工具，也可能输出最终答案

        return "达到最大迭代次数"
```

**关键设计决策（对比 Claude Code）：**

| 设计点 | 本项目 | Claude Code 的做法 |
|--------|--------|-------------------|
| 停止条件 | `MAX_TOOL_CALLS` 硬上限 | 用户可中断 + 预算管理 + 自然停止 |
| 消息管理 | 全量 messages 数组 | 更复杂的上下文窗口管理（压缩、摘要） |
| 工具执行 | 串行逐个执行 | 部分工具可并行执行 |
| 错误处理 | 异常被捕获，注入错误消息 | 分级错误：重试/跳过/终止 |
| 流式输出 | 可选 | 深度集成，实时展示工具调用过程 |

### 2.3 消息流转全链路

以下是一次完整调用的消息演变过程：

```python
# ===== 初始状态 =====
messages = [
    {"role": "system", "content": "你是一个知识教学智能助手..."},
    {"role": "user",   "content": "我想学Python装饰器"},
]

# ===== 第1轮：LLM 决策 → 调用 web_search =====
# LLM 返回:
assistant_msg = {
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {"id": "call_001", "function": {"name": "web_search",
         "arguments": '{"query":"Python装饰器教程入门"}'}}
    ]
}
# 执行 web_search → 返回 JSON 搜索结果
# 追加 tool 消息:
messages.append({
    "role": "tool",
    "tool_call_id": "call_001",
    "content": '{"results":[{"title":"Python装饰器详解",...}]}'
})

# ===== 第2轮：LLM 看到搜索结果，决定抓取内容 =====
# LLM 返回: tool_calls → fetch_webpage(url)
# 执行 → 追加 tool 消息

# ===== 第3轮：LLM 看到正文，决定加载编撰技能 =====
# LLM 返回: tool_calls → load_skill(name="knowledge-compiler")
# load_skill 执行 → 返回完整的 SKILL.md 正文（Layer 2 渐进式披露）
# 追加 tool 消息（内容是编撰指导）

# ===== 第4轮：LLM 读到技能指导，按格式生成第1章教材（text 响应）=====
# LLM 可能继续生成第2章、第3章...

# ===== 第N-2轮：LLM 决定加载出题技能 =====
# LLM 返回: tool_calls → load_skill(name="exercise-generator")
# 返回出题指导 → LLM 按格式为每章生成练习题

# ===== 第N轮：全部完成 =====
# LLM 返回: {"role": "assistant", "content": "我已经为你生成了完整的教材..."}
# tool_calls 为空 → 循环终止，返回 content
```

### 2.4 Harness 核心：Tool Registry 模式

在 Claude Code 的源码中，你会看到类似的模式。核心思想是：**工具的定义（schema）和执行（handler）分离，通过注册表管理**。

```python
# ===== 模式抽象 =====
# 任何 Agent 框架都可以用这个模型来描述：

TOOL_REGISTRY = {
    "tool_name_1": {
        "schema": {           # 给 LLM 看的：工具签名（名称、参数、描述）
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": {...}
            }
        },
        "handler": callable,  # 实际执行的：Python 函数 / Skill 提示词 / MCP 远程调用
    },
    "tool_name_2": { ... },
}

# Agent 启动时：
#   1. 遍历 TOOL_REGISTRY，收集所有 schema 发给 LLM
#   2. LLM 调用某个工具时，查找对应的 handler 执行
#   3. 结果追加回消息历史
```

本项目把这个模式扩展为三层，每层的 handler 不同：

| 层 | handler 是什么 | schema 来源 |
|----|---------------|-------------|
| 本地工具 | Python 函数直接调用 | 代码中硬编码的 schema 字典 |
| Skills (load_skill) | `SkillLoader` 返回 SKILL.md 正文 | LLM 通过 `load_skill` 工具按需获取（渐进式披露） |
| MCP | 通过 JSON-RPC 转发到外部进程 | `tools/list` 动态获取，运行时转换 |

---

## 3. 三层能力体系的定位与关系

一个常见误区是把这三者混为一谈。它们的本质区别：

```
Function Call (机制)
    │
    │  是 "LLM 怎么知道要用什么工具" 的机制
    │  本质: OpenAI 原生的 tool_choice="auto" + tools 参数
    │  你的角色: 写 schema 定义，LLM 自动匹配
    │
    ├── 本地工具 (Local Tools)
    │   │
    │   │  是 "工具怎么执行" 的最直接实现
    │   │  本质: Python 函数，输入参数，返回字符串
    │   │  适用: 需要执行代码逻辑的场景（发 HTTP 请求、操作文件、计算）
    │   │  类比 Claude Code: BashTool、ReadTool、WriteTool 等
    │   │
    ├── Skills (技能)
    │   │
    │   │  是 "怎么让 LLM 高质量完成复杂任务" 的提示词工程手段
    │   │  本质: 不是执行代码，而是通过「渐进式披露」让 LLM 获取详细任务指导
    │   │        Layer 1 — system prompt 仅注入技能名 + 一行描述（~20 token/技能）
    │   │        Layer 2 — LLM 按需调用 load_skill(name) 获取完整的 SKILL.md 正文
    │   │  适用: 编撰文档、出题、翻译、审校等纯 LLM 能力可完成的任务
    │   │  类比 Claude Code: 类似 Skills 目录下的 SKILL.md 文件
    │   │
    └── MCP (外部工具)
        │
        │  是 "怎么调用别人写的工具" 的互操作协议
        │  本质: 不是你写的代码，而是别人以标准协议暴露的服务
        │  适用: 需要集成第三方能力（搜索引擎、数据库、API）
        │  类比 Claude Code: .mcp.json 配置的 MCP Servers
        │
```

**数据流对比（同一个"获取网页内容"需求，三种实现路径）：**

```
# 路径1: 本地工具 —— 你写的代码
LLM 调用: fetch_webpage(url="https://...")
  → tools/web_fetch.py: requests.get(url) → BeautifulSoup → 清洗 → 返回文本

# 路径2: Skill —— LLM 能力（不适用于这个需求，Skill 不能发 HTTP）
# Skills 用于纯 LLM 任务，这里仅作对比

# 路径3: MCP —— 调别人的工具
LLM 调用: mcp__fetch(url="https://...")
  → mcp/client.py: JSON-RPC tools/call → MCP Server 进程 → 返回结果
```

---

## 4. 教学：如何添加自己的 Tool

### 模式总结

添加一个本地工具，只需要做 **3 件事**：

```
1. 写一个 Python 函数（输入 dict → 返回 str）
2. 写一个 schema 字典（告诉 LLM 这个工具是干什么的）
3. 在 LOCAL_TOOLS 和 LOCAL_TOOL_SCHEMAS 中注册
```

### 伪例 1：添加"翻译工具"

```python
# ===== 步骤1: 在 tools/ 下新建 translate.py =====

import json

# 1. 写函数：接收参数，返回字符串
def translate_text(text: str, target_language: str = "中文") -> str:
    """翻译工具（这里用伪逻辑演示结构，实际可接任何翻译 API）"""
    # 实际使用时，你可以接 Google Translate API 或调用 LLM
    translated = some_translate_api(text, target_language)
    return json.dumps({
        "original": text,
        "translated": translated,
        "target_language": target_language,
    }, ensure_ascii=False)

# 2. 写 schema：这是 LLM 看到的东西，描述要写清楚
TRANSLATE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "translate_text",
        "description": (
            "将文本翻译成指定语言。"
            "当你需要把英文资料翻译成中文让用户阅读时使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "要翻译的文本内容",
                },
                "target_language": {
                    "type": "string",
                    "description": "目标语言，如'中文'、'英文'、'日语'",
                },
            },
            "required": ["text", "target_language"],
        },
    },
}
```

```python
# ===== 步骤2: 在 tools/executor.py 中注册 =====

# 导入
from tools.translate import translate_text, TRANSLATE_SCHEMA

# 注册函数映射
LOCAL_TOOLS["translate_text"] = translate_text

# 注册 schema
LOCAL_TOOL_SCHEMAS.append(TRANSLATE_SCHEMA)

# 完成！LLM 现在可以调用 translate_text 了
```

### 伪例 2：添加"计算器工具"

```python
# tools/calculator.py

def calculate(expression: str) -> str:
    """安全地计算数学表达式"""
    import json
    try:
        # 安全计算（仅允许数学运算，禁止危险函数）
        allowed = {"__builtins__": {}}
        result = eval(expression, allowed, {"__builtins__": {}})
        return json.dumps({"expression": expression, "result": result})
    except Exception as e:
        return json.dumps({"error": str(e)})

CALCULATOR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "计算数学表达式，如 '2 + 3 * 4'",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式",
                },
            },
            "required": ["expression"],
        },
    },
}
```

### 要点总结

| 关注点 | 注意事项 |
|--------|---------|
| 函数签名 | 参数必须与 schema 中 `properties` 的 key 完全匹配 |
| 返回值 | 必须是 `str`（通常用 `json.dumps` 包装） |
| Schema 描述 | **这是 LLM 唯一能看到的信息**，描述不清楚 LLM 就不会正确调用 |
| required | 必须列出所有必填参数 |
| 错误处理 | 不要抛异常，捕获后用 `json.dumps({"error": "..."})` 返回 |

---

### 伪例 3：TodoWrite 任务管理工具（已内置本项目）

这是本项目**已实现**的一个重要工具，展示了"工具不止是执行逻辑，还可以和框架层双向交互"的设计模式。

**问题背景：** 在多步复杂任务中，LLM 容易"迷路"——忘记做过什么、重复执行已完成步骤、遗漏子任务。TodoWrite 通过两个机制解决这个问题：

```
机制 1: 强制顺序聚焦
  → 同时只能有一个 in_progress 任务
  → 强制性要求 LLM 做完一个再做下一个

机制 2: 静止检测 + 提醒注入
  → 框架层计数：连续 N 轮不调用 todo_write
  → 超过阈值 (3轮) → 自动在消息列表中注入提醒
  → 提醒内容包括当前任务状态，引导 LLM 回到正轨
```

**核心代码解析：**

```python
# tools/todo_write.py 的核心逻辑

class TodoManager:
    def __init__(self):
        self.items: list[dict] = []       # 当前任务列表
        self._rounds_without_todo = 0     # 未调用 todo 的连续轮次

    def update(self, items: list) -> str:
        """验证并更新任务列表，强制只有一个 in_progress"""
        validated, in_progress_count = [], 0
        for item in items:
            status = item.get("status", "pending")
            if status == "in_progress":
                in_progress_count += 1
            validated.append({
                "id": item["id"], "text": item["text"], "status": status
            })
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress")
        self.items = validated
        self._rounds_without_todo = 0     # 调用了 todo → 重置计数
        return self.render()

    def mark_round(self, had_todo_call: bool) -> str | None:
        """每轮 Agent 循环结束后调用，计数并决定是否注入提醒"""
        if had_todo_call:
            self._rounds_without_todo = 0
            return None
        self._rounds_without_todo += 1
        if self._rounds_without_todo >= REMINDER_THRESHOLD:  # 3轮
            return self._build_reminder()
        return None
```

**框架层注入逻辑：**

```python
# agent/core.py 中的集成

class Agent:
    def run(self, user_input: str) -> str:
        for iteration in range(MAX_TOOL_CALLS):
            # 第1步: 每轮开始先检查是否需要注入提醒
            reminder = mark_todo_round(False)  # 先假设本轮无 todo 调用
            if reminder:
                # 作为 system 消息注入到对话历史
                self.messages.append(
                    {"role": "system", "content": f"[TodoWrite 提醒] {reminder}"}
                )

            # 第2步: LLM 决策
            response = self.llm.chat(...)
            tool_calls = parse_tool_calls(response)

            # 第3步: 本轮结束后，告知 TodoManager 是否调用了 todo_write
            had_todo = any(tc["name"] == "todo_write" for tc in tool_calls)
            mark_todo_round(had_todo)  # 如果调用了 → 重置计数器
```

**完整调用时序：**

```
轮次 1: LLM 调用 todo_write(规划任务)  → had_todo=True  → 计数器重置为 0
轮次 2: LLM 调用 web_search            → had_todo=False → 计数器 = 1
轮次 3: LLM 调用 fetch_webpage         → had_todo=False → 计数器 = 2
轮次 4: LLM 调用 fetch_webpage         → had_todo=False → 计数器 = 3 → 注入提醒！
  → 注入: "[TodoWrite 提醒] 已连续3轮未更新任务列表。请调用 todo_write 检查进度..."
轮次 5: LLM 收到提醒，调用 todo_write(标记完成+开启新任务) → 计数器重置
```

**设计要点：**

| 要点 | 说明 |
|------|------|
| 双向交互 | Tool 不再只是"被调用→返回结果"，而是通过全局状态和框架层互相感知 |
| 计数位置 | `mark_round(False)` 在每轮 **开始时** 调用（注入提醒），`mark_round(had_todo)` 在每轮 **结束后** 调用（更新计数器） |
| 提醒内容 | 如果任务列表非空，提醒会包含当前所有任务的渲染结果，帮助 LLM 快速回忆上下文 |
| 合并模式 | `merge=true` 支持增量添加新任务而不丢失已有进度 |

---

### 伪例 4：Subagent 子任务拆分工具（已内置本项目）

这是本项目**已实现**的另一个重要工具，展示了"消息隔离 + 分治法"模式。

**问题背景：** Agent 工作越久，`messages` 数组越臃肿——每一轮的工具调用和结果都被追加到消息历史中。在长任务中，这会导致：
- context window 被大量工具调用记录占满
- LLM 容易被过长的历史分散注意力
- 不同子任务的信息互相污染

Subagent 的解决方案：**大任务拆小，message 分离，每个子任务用全新上下文执行。**

```
主 Agent (Parent)                    子 Agent 1 (Child)              子 Agent 2 (Child)
┌────────────────────┐              ┌──────────────────┐            ┌──────────────────┐
│ messages:          │              │ messages:        │            │ messages:        │
│ [system, user,     │              │ [sub_system,     │            │ [sub_system,     │
│  assistant, tool,  │   task()     │  user_prompt,    │   task()   │  user_prompt,    │
│  assistant, tool,  │──────────────│  assistant,      │────────────│  assistant,      │
│  ...数十轮...]     │  返回摘要     │  tool, ...]      │  返回摘要   │  tool, ...]      │
│                    │◄─────────────│                  │◄───────────│                  │
│                    │              │  ← 上下文隔离 →   │            │  ← 上下文隔离 →   │
└────────────────────┘              └──────────────────┘            └──────────────────┘
```

**工具分层设计：**

```python
# 主 Agent 工具集 = 子 Agent 工具集 + task 工具
PARENT_TOOLS = CHILD_TOOLS + [task]
# 子 Agent 工具集 = 所有本地工具（不含 task，防止递归爆炸）
CHILD_TOOLS = {web_search, fetch_webpage, save_document, load_skill, todo_write}
```

**核心代码解析：**

```python
# tools/subagent.py 的核心逻辑

from agent.llm_client import LLMClient
from config import SUBAGENT_MAX_TOOL_CALLS, build_subagent_system_prompt

def run_subagent(prompt: str) -> str:
    """主 Agent 调用此函数 spawn 一个子 Agent"""
    llm = LLMClient()
    system_prompt = build_subagent_system_prompt()

    # 全新的 messages 数组 —— 上下文隔离的关键！
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},   # 只有主 Agent 传过来的 prompt
    ]

    # 子 Agent 自己的 ReAct 循环
    for iteration in range(SUBAGENT_MAX_TOOL_CALLS):
        response = llm.chat(messages=messages, tools=CHILD_TOOL_SCHEMAS)
        assistant_msg = llm.assistant_message(response)

        if assistant_msg is None:
            break

        messages.append(assistant_msg)

        tool_calls = llm.parse_tool_calls(response)
        if not tool_calls:
            # 子 Agent 完成 → 返回文本摘要给主 Agent
            return assistant_msg.get("content", "")

        # 执行子 Agent 的工具调用
        for tc in tool_calls:
            handler = CHILD_TOOLS.get(tc["name"])
            result = handler(**tc["arguments"])
            messages.append(llm.format_tool_result(tc["id"], result))

    return "(Subagent 已达到最大工具调用次数)"
```

**完整调用时序：**

```
主 Agent 轮次 1-3: 搜索、抓取、分析... messages 已累积 12 条

主 Agent 轮次 4: 决定分治法 → 调用 task(prompt="搜索微积分入门资料并返回3篇最佳文章摘要")
  ├── run_subagent() 被调用
  │   ├── sub_messages = [sub_system, user_prompt]  ← 全新的 2 条消息
  │   ├── 子轮1: web_search("微积分入门教程")        ← sub_messages: 4 条
  │   ├── 子轮2: fetch_webpage(url1)                  ← sub_messages: 6 条
  │   ├── 子轮3: fetch_webpage(url2)                  ← sub_messages: 8 条
  │   ├── 子轮4: 返回 "以下是3篇最佳文章摘要..."      ← 纯文本完成
  │   └── 返回摘要字符串给主 Agent
  └── 主 Agent 收到: "tool_result: 以下是3篇..."

主 Agent messages: 只增加了 1 条 tool_result（而不是子 Agent 内部的 8 条）
主 Agent 轮次 5: 用收到的摘要继续工作，messages 依然清爽
```

**对比：不用 vs 用 Subagent：**

| 维度 | 不用 Subagent | 用 Subagent |
|------|--------------|-------------|
| 主对话 messages 增长 | 每个工具调用都追加，线性膨胀 | 只追加 1 条 tool_result |
| 信息隔离 | 所有信息混在一起 | 子任务独立上下文 |
| 并行能力 | 不支持（串行调用） | 可同时派发多个子 Agent |
| LLM 注意力 | 容易被长历史分散 | 每个 Agent 上下文都清爽 |
| 适用场景 | 简单任务（3-5步） | 复杂大任务（10+步） |

**设计要点：**

| 要点 | 说明 |
|------|------|
| 消息隔离 | `run_subagent` 内部创建全新的 `messages` 数组，与主 Agent 的 `self.messages` 完全独立 |
| 递归防护 | 子 Agent 的工具集 `CHILD_TOOLS` 不含 `task` 工具，防止子 Agent 再产生孙 Agent |
| Prompt 完整性 | 给子 Agent 的 prompt 必须包含所有必要上下文，因为它看不到主对话历史 |
| 安全上限 | `SUBAGENT_MAX_TOOL_CALLS` 独立于主 Agent 的 `MAX_TOOL_CALLS`，默认 15 轮 |
| 返回格式 | 子 Agent 返回纯文本摘要，作为 `tool_result` 注入主 Agent 对话 |

---

## 5. 教学：如何添加自己的 Skill（渐进式披露）

### Skill 的本质

Skill 不直接作为 Function Call 工具。它采用**渐进式披露**：
```
Layer 1 (启动时): System Prompt 仅注入技能名 + 一行描述（极省 token）
Layer 2 (运行时): LLM 调用 load_skill(name) 获取完整 SKILL.md 正文
```

**为什么要有 Skill？** 因为有些任务无法用代码完成——比如"写一篇好文章"、"出一套有质量的题"。这些任务的本质是引导 LLM 进入特定的输出模式。Skill 就是把这种引导**标准化**成可复用的模块，同时用渐进式披露避免撑爆 context window。

### 模式总结

添加一个 Skill，只需要做 **2 件事**：

```
1. 在 skills/ 下新建目录，放入 SKILL.md（含 YAML frontmatter + 正文）
2. 无需注册代码！SkillLoader 启动时自动 rglob("SKILL.md") 扫描
```

### 伪例：添加"学习路线规划"Skill

**步骤1: 创建 `skills/learning-path/SKILL.md`**

```markdown
---
name: learning-path
description: 为用户规划学习路线，分阶段列出要学的内容和资源
tags: [teaching, planning]
---

## 技能：规划学习路线

### 何时使用
当用户想系统学习某个主题时，调用此技能为其规划学习路线。

### 输出格式

请按以下格式输出学习路线：

## [主题] 学习路线图

### 学习概览
- 预计总时长: [估算]
- 推荐学习频率: [建议]

### 阶段一: 基础入门 (预计 X 周)
**学习目标**: [描述]

| 序号 | 知识点 | 推荐资源 | 练习任务 |
|------|--------|----------|----------|
| 1 | ... | ... | ... |

### 阶段二: 核心进阶 (预计 X 周)
...

### 阶段三: 实战应用 (预计 X 周)
...

### 推荐学习资源汇总
- 书籍: [...]
- 视频: [...]
- 项目: [...]

### 阶段性检验标准
[如何判断自己掌握了每个阶段的内容]
```

**步骤2: 什么都不用做！** SkillLoader 在 `Agent` 启动时自动扫描所有 `SKILL.md`：
- frontmatter 中的 `name` 和 `description` 自动注入到 Layer 1（system prompt）
- 技能正文通过 `load_skill("learning-path")` 按需返回（Layer 2）

### 渐进式披露的完整调用流

```
Agent 启动
  ↓
System Prompt 注入:
  Skills available:
    - knowledge-compiler: 将搜索和研究资料编撰成结构化的教材 [writing,teaching]
    - exercise-generator: 根据教学内容生成配套练习题 [teaching,exercise]
    - learning-path: 为用户规划学习路线 [teaching,planning]
  ↓                                  （Layer 1: 仅 3 行，~60 token）

LLM: 用户想学 Python → 我需要先规划学习路线
  → 调用 load_skill("learning-path")
  → 工具返回完整的 SKILL.md 正文     （Layer 2: 按需加载，~500 token）
  → LLM 根据指导生成学习路线图

LLM: 路线规划好了 → 开始搜索资料 → 编撰教材前先加载编撰技能
  → 调用 load_skill("knowledge-compiler")
  → 返回编撰指导 → LLM 逐章生成教材
```

### 关键点

| 关注点 | 注意事项 |
|--------|---------|
| 目录结构 | 每个 Skill 一个独立目录，内含 `SKILL.md` |
| YAML frontmatter | 必须包含 `name` 和 `description`，`tags` 可选 |
| 自动发现 | `SkillLoader._load_all()` 通过 `rglob("SKILL.md")` 自动扫描 |
| 降级解析 | 无 pyyaml 时自动降级为简易 YAML 解析器 |
| load_skill 工具 | 无需为每个 Skill 单独写 schema——一个 `load_skill` 工具通吃所有 Skill |
| 扩展性 | 添加新 Skill 只需新建目录 + SKILL.md，零代码改动 |

### 富 Skill：包含子资源（模板 + 脚本）

Claude Code 等成熟 Agent 框架中的 Skill 往往不止一个 `SKILL.md` 文件，还会附带**模板文件、示例代码、辅助脚本**。本项目的 `document-compiler` 技能就是这样一个例子。

**目录结构：**

```
skills/document-compiler/
├── SKILL.md                    # 技能主文件（必经入口）
├── templates/
│   ├── cover.md                # 教材封面模板
│   └── style_guide.md          # 排版风格指南
└── scripts/
    └── word_counter.py         # 字数统计工具
```

**关键设计：SKILL.md 是入口，子资源按需引用**

```
LLM 调用 load_skill("document-compiler")
  → 返回 SKILL.md 正文
  → 正文中包含子资源文件路径和说明：
      "使用 templates/cover.md 中的模板"
      "执行 python {skill_dir}/scripts/word_counter.py <file> 检查篇幅"
  → LLM 根据引导决定是否查看/执行子资源
```

**SKILL.md 中引用子资源的方式：**

```markdown
## 子资源文件

本技能目录下附带辅助资源：

| 文件 | 用途 |
|------|------|
| `templates/cover.md` | 封面模板 |
| `templates/style_guide.md` | 风格指南 |
| `scripts/word_counter.py` | 字数统计 |
```

LLM 读到这段自然会按需去取用这些子资源——就像你看一个 GitHub 项目的 README 后去翻 `examples/` 目录一样。

**template 文件示例**（`templates/style_guide.md`）：

```markdown
# 教材排版风格指南
- 中英文之间插入空格：`使用 Python 编程`
- 代码块标注语言：```python
- 每章控制在 2000-3000 字
```

**script 文件示例**（`scripts/word_counter.py`）：

```python
"""字数统计 —— 检查章节篇幅"""
import sys, re

def count_words(text: str) -> int:
    en = len(re.findall(r"[a-zA-Z]+", text))
    cn = len(re.findall(r"[\u4e00-\u9fff]", text))
    return en + cn

with open(sys.argv[1], "r") as f:
    text = f.read()
print(f"总字数: {count_words(text)}")
```

### 富 Skill 设计原则

| 原则 | 说明 |
|------|------|
| SKILL.md 为入口 | SkillLoader 只加载 SKILL.md，其他文件由 LLM 根据 SKILL.md 中的指引按需访问 |
| 路径用相对路径 | `templates/cover.md` 而非绝对路径——LLM 能基于 Skill 目录拼接 |
| 脚本最小化 | 脚本应该是简洁的单文件，有明确的输入输出，便于 LLM 理解和执行 |
| 模板用 Markdown | 全文统一 Markdown 格式，减少 LLM 需要处理的文件类型 |
| 引用清晰 | SKILL.md 中明确标注每个子文件的路径和用途 |

---

## 5.5 上下文压缩：三层 Token 管理（已内置本项目）

### 问题背景

Agent 工作越久，`messages` 数组越臃肿——每一次工具调用和结果都被追加到对话历史。在长任务中这会导致：
- Token 使用量线性增长，逼近模型的 context window 上限
- 很旧的工具结果早已过时，却仍然占据大量 Token
- LLM 在决策时容易被远古历史干扰

本项目的解决方案是**三层上下文压缩**，按「无感 → 重压缩 → 自救」递进：

```
Layer 1: micro_compact  — 每轮自动运行，裁剪旧的 tool 结果
Layer 2: auto_compact   — 超过 Token 阈值自动触发，LLM 摘要后替换全部历史
Layer 3: manual_compact — LLM 主动输出 [COMPACT] 请求压缩
```

### Layer 1：静默裁剪（micro_compact）

每轮循环开始时自动执行，对 LLM 完全透明。逻辑极简：

```
扫描 messages 中所有 role="tool" 的消息
只保留最近 N 条（KEEP_RECENT_TOOLS=6）保持完整
其余的 tool 结果 → 内容超过 150 字符就替换为 "[已压缩 原工具结果过长] snippet..."
```

**这是一种"截断为摘要"的策略**——不删除消息（会破坏 tool_call_id 追踪），而是大幅缩减内容。

```python
# agent/compactor.py 核心逻辑

def micro_compact(messages: list[dict]) -> list[dict]:
    tool_indices = [i for i, msg in enumerate(messages) if msg["role"] == "tool"]
    if len(tool_indices) <= KEEP_RECENT_TOOLS:
        return messages  # 还不到阈值，不做任何事

    for idx in tool_indices[:-KEEP_RECENT_TOOLS]:  # 除了最近的 6 条
        content = messages[idx].get("content", "")
        if len(content) > 150:
            snippet = content[:100].replace("\n", " ").strip()
            messages[idx]["content"] = f"[已压缩 原工具结果过长] {snippet}..."
    return messages
```

**调用位置（agent/core.py）：**

```
for iteration in range(MAX_TOOL_CALLS):
    micro_compact(self.messages)        # ← Layer 1：每轮开始自动执行
    ...
    response = self.llm.chat(...)
```

### Layer 2：自动摘要压缩（auto_compact）

当 `estimate_tokens(messages) > COMPACT_TOKEN_THRESHOLD`（默认 12000）时触发：

1. **存档**：将完整 messages 写入 `transcripts/transcript_{timestamp}.jsonl`，确保数据不丢失
2. **摘要**：发一条单独的 LLM 请求，要求生成连续性摘要
3. **替换**：messages 被压缩为单条 system 消息（含摘要），然后重新插入 system prompt

```python
# agent/compactor.py

def auto_compact(messages: list[dict], llm) -> list[dict]:
    # 1. 存档
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with open(transcript_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")

    # 2. LLM 生成摘要
    summary_prompt = "请将以下对话历史压缩为一份连续摘要..." + json.dumps(messages)[:80000]
    response = llm.chat(messages=[{"role": "user", "content": summary_prompt}], tools=None)
    summary = response.choices[0].message.content

    # 3. 替换
    return [{"role": "system", "content": f"[对话已压缩]\n\n{summary}"}]
```

**核心设计约束：**
- **不在主循环中同步等待** —— 这是唯一会阻塞的地方，但只在大阈值才触发
- **保留 system prompt** —— 压缩后 `self.messages.insert(0, {"role": "system", "content": self.system_prompt})` 确保 Agent 人格不丢失
- **摘要的摘要** —— 摘要中包含「用户最初目标 + 已完成步骤 + 当前进度 + 核心信息」

### Layer 3：LLM 自救（manual_compact）

LLM 可以在回复中输出 `[COMPACT]` 来主动请求压缩。这发生在 LLM 意识到上下文太长但还没到阈值、或者 LLM 发现自己需要清空历史才能继续思考时。

```python
# agent/core.py 中的检测逻辑

if not tool_calls:
    content = assistant_msg.get("content", "")
    if "[COMPACT]" in content:
        # 与 Layer 2 同样的压缩流程
        self.messages[:] = auto_compact(self.messages, self.llm)
        self.messages.insert(0, {"role": "system", "content": self.system_prompt})
        continue  # 压缩后继续循环，不返回给用户
    return content  # 正常完成，返回给用户
```

系统提示词中明确告知 LLM 这个能力：
```
## 上下文管理
对话历史会在每轮自动进行轻量压缩（裁剪旧工具结果）。
当上下文极度过长时，你可以输出 `[COMPACT]` 来触发完整压缩。
```

### 完整调用时序

```
第 1-10 轮: micro_compact 每轮执行，但 tool 消息还不到 6 条 → 不做任何事
第 11 轮: micro_compact 开始裁剪第 3-5 轮的 tool 结果
第 15 轮: 大量网页抓取导致 Token 暴涨
  → estimate_tokens: 14500 > 12000 (阈值)
  → auto_compact 触发:
     1. 存档 → transcripts/transcript_1716000000.jsonl
     2. LLM 摘要 → "用户想学微积分，已完成搜索和抓取，正在编撰第3章..."
     3. messages 从 47 条压缩为 2 条 [system_prompt, 摘要]
  → 终端显示: "⚡ 上下文压缩触发 (auto): 14500 tokens → 压缩中..."
             "✓ 压缩完成: 剩余 623 tokens"
第 16 轮: 基于摘要继续工作，messages 只有 4 条

...20 轮后，LLM 发现上下文又很长了...
第 36 轮: LLM 输出 "[COMPACT]" (没有工具调用)
  → manual_compact 触发，同样流程
  → 终端显示: "⚡ 上下文压缩触发 (manual): 11000 tokens → 压缩中..."
```

### 对比：不用 vs 用三层压缩

| 维度 | 不用压缩 | 用三层压缩 |
|------|---------|-----------|
| Token 增长 | 线性增长，迟早超标 | 锯齿形——积累到阈值就压缩 |
| 旧工具结果 | 始终占满 Token | 被自动裁剪为摘要 |
| 数据安全 | — | 每次压缩前存档到 jsonl |
| 成本 | 长对话越来越贵 | 用少量摘要 Token 换大量历史 Token |
| LLM 决策质量 | 被远古信息干扰 | 上下文始终保持清新 |

### 设计要点

| 要点 | 说明 |
|------|------|
| 原地修改 | `micro_compact` 直接修改传入的 messages 列表，不创建副本 |
| 不删消息 | 裁剪 strategy 是「截断内容」而非「删除消息」，保留 tool_call_id 追踪链 |
| 存档优先 | `auto_compact` 先存档再压缩，压缩失败也有恢复手段 |
| 摘要质量 | 摘要 prompt 明确要求保留「目标、结果、进度、核心信息」四个维度 |
| Token 估算 | 优先使用 `tiktoken` 精确估算，降级使用 `chars/3` 粗略估算 |
| 环境变量可调 | `COMPACT_TOKEN_THRESHOLD`、`KEEP_RECENT_TOOLS`、`TRANSCRIPT_DIR` 均可通过 .env 配置 |

---

## 6. 教学：如何接入 MCP Server

### 6.1 MCP 协议快速理解

MCP（Model Context Protocol）是一个让 Agent 调用外部工具的标准化协议。你可以把它理解为"工具界的 USB 协议"——只要工具实现了 MCP，任何 Agent 都能插上就用。

**通信方式：**

```
┌──────────┐        stdin/stdout         ┌────────────────┐
│  Agent   │ ◄══════════════════════════► │  MCP Server     │
│ (Python) │    JSON-RPC 2.0 messages     │ (Node/Python/..)│
└──────────┘                              └────────────────┘

每条消息格式:
  {"jsonrpc":"2.0", "id":1, "method":"tools/list", "params":{}}

握手流程:
  Agent ──initialize(request)──► Server
  Agent ◄──capabilities──────── Server   (Server 返回自己的能力列表)
  Agent ──initialized(notify)──► Server   (通知握手完成)

调用工具:
  Agent ──tools/call(name, args)──► Server
  Agent ◄──result─────────────────  Server
```

### 6.2 配置一个新的 MCP Server

**场景 1：接入官方 MCP Server**

```json
// mcp_servers.json
{
  "mcpServers": {
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"],
      "description": "网页内容抓取 MCP Server",
      "enabled": true          // ← 设为 true 即可启用
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "your-api-key"  // ← 通过环境变量传入密钥
      },
      "enabled": true
    }
  }
}
```

**场景 2：写一个自己的 Python MCP Server 并被 Agent 调用**

这是进阶用法。你可以用 Python 写一个提供自定义工具的 MCP Server，比如一个"自动出题服务"：

```python
# my_exercise_server.py（一个独立的 MCP Server 进程）

import json
import sys

def handle_request(request: dict) -> dict:
    """最简化的 MCP 处理（实际建议用 mcp 官方 Python SDK）"""
    method = request.get("method")
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "exercise-server", "version": "1.0"}
            }
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [{
                    "name": "generate_mcq",
                    "description": "生成选择题",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string"},
                            "count": {"type": "integer"},
                        },
                        "required": ["topic"]
                    }
                }]
            }
        }

    if method == "tools/call":
        tool_name = request["params"]["name"]
        arguments = request["params"]["arguments"]
        # 实际出题逻辑...
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "content": [{"type": "text", "text": f"已生成{arguments.get('count',5)}道{arguments['topic']}选择题"}]
            }
        }

    return {"jsonrpc": "2.0", "id": req_id, "result": {}}

# MCP Server 主循环
for line in sys.stdin:
    request = json.loads(line.strip())
    response = handle_request(request)
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()
```

```json
// mcp_servers.json 中的配置
{
  "mcpServers": {
    "my-exercise-generator": {
      "command": "python",
      "args": ["my_exercise_server.py"],
      "enabled": true
    }
  }
}
```

Agent 启动后，这个 Server 的工具会自动以 `mcp__generate_mcq` 的名字出现在 LLM 的工具列表中。

### 6.3 MCP 客户端的核心实现

理解 [mcp/client.py](file:///d:/project/studyhelper/mcp/client.py) 的这几个关键函数，你就能在任何项目中实现 MCP 集成：

```
MCPClient
├── start()            # 1. spawn 子进程  2. 启动读线程  3. initialize 握手
├── _send_request()    # 发送 JSON-RPC 请求 + 等待响应（Event 同步）
├── _read_loop()       # 后台线程持续读 stdout，匹配 request id
├── _write_line()      # 向 stdin 写入一行 JSON
├── list_tools()       # 调用 tools/list，获取工具列表
├── call_tool()        # 调用 tools/call，执行远程工具
└── stop()             # 关闭 stdin → terminate → kill
```

**MCP → OpenAI Schema 转换：**

```python
# mcp/manager.py 中的核心转换逻辑

def _mcp_to_openai_schema(mcp_tool: dict) -> dict:
    """MCP 的 inputSchema 和 OpenAI 的 function.parameters 结构一致，
       所以基本上直接映射即可"""
    input_schema = mcp_tool.get("inputSchema", {})
    return {
        "type": "function",
        "function": {
            "name": f"mcp__{mcp_tool['name']}",   # ← 加 mcp__ 前缀区分
            "description": mcp_tool.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": input_schema.get("properties", {}),
                "required": input_schema.get("required", []),
            },
        },
    }
```

### 6.4 排错指南：MCP 连不上的常见原因

如果你在还原 Claude Code 的 MCP 逻辑时遇到了连接问题，对照这个清单逐一检查：

| 症状 | 可能原因 | 检查方法 |
|------|---------|---------|
| 进程启动后无响应 | stdin 没有 flush，MCP Server 收不到完整消息 | 确保每行 JSON 后有 `\n` 并调用 `flush()` |
| 一直等待超时 | JSON-RPC 的 `id` 匹配不上 | 确认 req id 在请求和响应中一致（本项目用整数 id） |
| response 内容为空 | 没有读到完整的行 | 检查 `readline()` 是否正确处理了换行符 |
| 「initialize 后没反应」 | 没发 `initialized` 通知 | 这是 MCP 协议要求的：initialize 成后必须发 initialized 通知 |
| 工具注册后 LLM 不调用 | Schema 中 name 和实际注册名不一致 | 检查 `list_tools()` 返回的 name 和 `tool_registry` 中的 key |
| `npx` command not found | 没装 Node.js | `node --version` 确认 |
| 超时后进程僵死 | 没有正确清理子进程 | 确保 `stop()` 能 terminate 和 kill |

---

## 7. 快速开始

### 7.1 安装依赖

```bash
pip install -r requirements.txt
```

核心依赖：
- `openai` — LLM API 调用（Function Calling 依赖）
- `duckduckgo_search` — 免费网页搜索
- `beautifulsoup4` — HTML 解析清洗
- `streamlit` — Web UI
- `rich` — 终端美化

### 7.2 配置

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

兼容任何 OpenAI 格式 API（DeepSeek、通义千问、Ollama 本地模型等）。

### 7.3 运行

```bash
# CLI 模式
python main.py "微积分入门"

# Web UI 模式
streamlit run ui/app.py
# 浏览器打开 http://localhost:8501
```

---

## 8. 项目结构

```
studyhelper/
├── main.py                     # CLI 入口
├── config.py                   # 全局配置、系统提示词
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板
├── mcp_servers.json            # MCP Server 配置文件
│
├── agent/                      # Agent 核心
│   ├── core.py                 # ReAct 主循环（Harness 核心）
│   ├── compactor.py            # 三层上下文压缩（Token 管理）
│   └── llm_client.py           # LLM 客户端（Function Call 封装）
│
├── tools/                      # 本地工具层
│   ├── executor.py             # ToolBridge: 本地 + MCP 统一执行
│   ├── web_search.py           # DuckDuckGo 网页搜索
│   ├── web_fetch.py            # 网页正文抓取 + 清洗
│   ├── file_tools.py           # 文件保存 / 读取
│   ├── load_skill.py           # Skill 按需加载（Layer 2 入口）
│   ├── todo_write.py           # 多步任务进度管理（防丢失+强制顺序聚焦）
│   └── subagent.py              # 子任务拆分与上下文隔离（Subagent 模式）
│
├── skills/                     # Skills 技能层（渐进式披露）
│   ├── registry.py             # SkillLoader: rglob("SKILL.md") 自动扫描
│   ├── knowledge-compiler/     # 技能: 教材编撰
│   │   └── SKILL.md            #   YAML frontmatter + 编撰指导正文
│   ├── exercise-generator/     # 技能: 练习题生成
│   │   └── SKILL.md            #   YAML frontmatter + 出题指导正文
│   └── document-compiler/      # 富 Skill: 教材汇编（含子资源）
│       ├── SKILL.md            #   技能主入口
│       ├── templates/          #   模板文件
│       │   ├── cover.md        #     封面模板
│       │   └── style_guide.md  #     风格指南
│       └── scripts/            #   辅助脚本
│           └── word_counter.py #     字数统计工具
│
├── mcp/                        # MCP 工具层
│   ├── client.py               # stdio JSON-RPC 2.0 客户端
│   └── manager.py              # 多 Server 管理 + schema 转换
│
├── ui/                         # 用户界面
│   └── app.py                  # Streamlit Web UI
│
└── output/                     # 生成文件输出目录
```

---

## 9. 进阶：如何改造为通用的 Harness 框架

这个项目是为特定需求（知识学习助手）设计的。如果你想把它改造成一个**通用的 Agent Harness 框架**来适配各种场景，以下是改造路线图：

### 第1步：把 System Prompt 外部化

```python
# 现在：硬编码在 config.py 中
SYSTEM_PROMPT = "你是一个知识教学智能助手..."

# 改造后：从配置文件加载
class AgentConfig:
    system_prompt: str       # 从 yaml/json 文件读取
    model: str
    base_url: str
    tools_enabled: list[str] # 选择性启用工具
```

### 第2步：把工具注册改为插件式

```python
# 现在：工具在 tools/executor.py 中硬编码导入
from tools.web_search import web_search
LOCAL_TOOLS["web_search"] = web_search

# 改造后：约定式自动发现（类似 Claude Code 的做法）
# tools/
#   __init__.py 自动扫描目录中所有 .py 文件
#   每个文件暴露一个 register(registry) 函数
# Agent 启动时遍历调用，工具自注册
```

### 第3步：增加上下文窗口管理

```python
# 现在：全量 messages 累积
# 问题：长对话会超出 token 限制

# 改造方案：
# 三层压缩
# 1. Token 计数 — 用 tiktoken 计算当前 messages 总 token 数
# 2. 智能截断 — 超过阈值时压缩最旧的 tool 结果或做摘要
# 3. 分层记忆 — 短期记忆（最近N轮）+ 长期记忆（向量检索）
```

### 第4步：增加工具执行策略

```python
# 现在：串行逐个执行
for tc in tool_calls:
    result = executor(tc)

# 改造后：支持并行执行
# 当 LLM 同时返回多个 tool_call 且它们之间无依赖时，并行执行
```

### 第5步：增加中断和恢复机制

```python
# 改造后：
class Agent:
    def run(self, user_input):
        # ...
        for iteration in range(max_iter):
            if self.check_interrupt():  # 用户按 Ctrl+C 或 UI 点停止
                self.save_checkpoint()  # 序列化 messages 到文件
                return "已中断，可恢复"
            # ...
    
    def resume(self):
        # 从 checkpoint 恢复 messages，继续执行
```

---

## 总结：这个项目和 Claude Code 的对照关系

| Claude Code 概念 | 本项目对应 | 学习重点 |
|-----------------|-----------|---------|
| Harness 主循环 | `agent/core.py` 的 `Agent.run()` | ReAct 循环的逻辑 |
| Tool 系统 | `tools/` 目录 + `tools/executor.py` | 工具注册模式 |
| `.mcp.json` | `mcp_servers.json` | MCP 配置格式 |
| MCP Client | `mcp/client.py` | stdio JSON-RPC 实现 |
| Skills 系统 | `skills/` + `load_skill` 工具 | SKILL.md 渐进式披露 (Layer 1→2) |
| System Prompt | `config.py` 的 `SYSTEM_PROMPT` | Agent 人设设计 |
| Context Window 管理 | 本项目未实现 | 需自己补充（见进阶第3步） |
| Tool 并行执行 | 本项目未实现 | 需自己补充（见进阶第4步） |
| TodoWrite 任务管理 | `tools/todo_write.py` + `agent/core.py` 注入逻辑 | 防丢失 + 强制顺序聚焦 |
| Subagent 子任务拆分 | `tools/subagent.py` + `tools/executor.py` 工具分层 | 消息隔离 + 分治法 |
| 三层上下文压缩 | `agent/compactor.py` + `agent/core.py` 集成 | Token 管理 + 防溢出 |
| 任务管理系统（多agent协作基础） | 本项目未实现 | 需自己补充 |
| background_task | 本项目未实现 | 需自己补充 |
| agent_teams | 本项目未实现 | 需自己补充 |
| team_protocols(组内通信标准) | 本项目未实现 | 需自己补充 |
| autonomous_agents(自动认领任务) | 本项目未实现 | 需自己补充 |
| worktree_task_isolation(任务隔离) | 本项目未实现 | 需自己补充 |

---

MIT License
