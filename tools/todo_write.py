"""
TodoWrite 工具 - 多步任务进度管理

防止模型在长任务中丢失进度、重复执行已完成步骤。
机制：模型通过 todo_write 维护任务列表，框架强制「同时只有一个 in_progress」，
     连续 3 轮不调用 todo 时自动注入提醒。
"""
import json
import logging

logger = logging.getLogger(__name__)

REMINDER_THRESHOLD = 3


class TodoManager:
    def __init__(self):
        self.items: list[dict] = []
        self._rounds_without_todo = 0

    def update(self, items: list) -> str:
        validated, in_progress_count = [], 0
        for item in items:
            status = item.get("status", "pending")
            if status == "in_progress":
                in_progress_count += 1
            validated.append({
                "id": item["id"],
                "text": item["text"],
                "status": status,
            })
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress")
        self.items = validated
        self._rounds_without_todo = 0
        return self.render()

    def render(self) -> str:
        lines = ["## 当前任务列表"]
        for item in self.items:
            icon = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(item["status"], "[?]")
            lines.append(f"- {icon} [{item['status']}] {item['id']}: {item['text']}")
        return "\n".join(lines)

    def mark_round(self, had_todo_call: bool) -> str | None:
        if had_todo_call:
            self._rounds_without_todo = 0
            return None
        self._rounds_without_todo += 1
        if self._rounds_without_todo >= REMINDER_THRESHOLD:
            logger.warning(f"TodoWrite 提醒触发：已连续 {self._rounds_without_todo} 轮未调用 todo_write")
            return self._build_reminder()
        return None

    def _build_reminder(self) -> str:
        if not self.items:
            return (
                f"[系统提醒] 已连续 {self._rounds_without_todo} 轮未更新任务列表。"
                "请调用 todo_write 创建任务计划，确保不遗漏任何步骤。"
            )
        return (
            f"[系统提醒] 已连续 {self._rounds_without_todo} 轮未更新任务列表。"
            "请调用 todo_write 检查当前进度：\n"
            + self.render()
        )


_todo_manager = TodoManager()


def todo_write(todos: list, merge: bool = False) -> str:
    if merge:
        existing_ids = {item["id"] for item in _todo_manager.items}
        for new_item in todos:
            if new_item["id"] not in existing_ids:
                _todo_manager.items.append({
                    "id": new_item["id"],
                    "text": new_item["text"],
                    "status": new_item.get("status", "pending"),
                })
            else:
                for existing in _todo_manager.items:
                    if existing["id"] == new_item["id"]:
                        existing["status"] = new_item.get("status", existing["status"])
                        existing["text"] = new_item.get("text", existing["text"])
                        break
        try:
            return _todo_manager.render()
        except ValueError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    in_progress_count = sum(1 for t in todos if t.get("status") == "in_progress")
    if in_progress_count > 1:
        return json.dumps(
            {"error": "Only one task can be in_progress at a time"},
            ensure_ascii=False,
        )

    _todo_manager.items = [
        {
            "id": t["id"],
            "text": t["text"],
            "status": t.get("status", "pending"),
        }
        for t in todos
    ]
    _todo_manager._rounds_without_todo = 0
    return _todo_manager.render()


def mark_todo_round(had_todo_call: bool) -> str | None:
    return _todo_manager.mark_round(had_todo_call)


def get_todo_manager() -> TodoManager:
    return _todo_manager


TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "todo_write",
        "description": (
            "创建和管理结构化的任务列表，用于跟踪多步任务的进度。"
            "每次更新任务状态时调用此工具。"
            "规则：同时只能有一个任务处于 in_progress 状态。"
            "连续 3 轮不调用此工具将触发系统提醒。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "任务列表，每项包含 id、text 和 status",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "任务唯一标识符",
                            },
                            "text": {
                                "type": "string",
                                "description": "任务描述",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "任务状态：pending=待开始, in_progress=进行中（同时只能有一个）, completed=已完成",
                            },
                        },
                        "required": ["id", "text", "status"],
                    },
                },
                "merge": {
                    "type": "boolean",
                    "description": "是否与现有任务列表合并（true=合并更新, false=全量替换）",
                },
            },
            "required": ["todos"],
        },
    },
}
