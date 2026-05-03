"""
Skills 渐进式披露加载器

两层披露模式（Layer 1 → Layer 2）：
  Layer 1（System Prompt）: 只注入技能名称 + 一行简短描述，极省 token
  Layer 2（Tool Result）: LLM 调用 load_skill(name) 时返回完整 SKILL.md 正文

SKILL.md 格式：
  ---
  name: my-skill
  description: 一句话描述
  tags: [tag1, tag2]
  ---
  正文内容...
"""
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).resolve().parent


class SkillLoader:
    """渐进式披露的技能加载器"""

    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self.skills: dict[str, dict] = {}
        self._load_all()

    def _load_all(self):
        if not self.skills_dir.exists():
            return
        for f in sorted(self.skills_dir.rglob("SKILL.md")):
            text = f.read_text(encoding="utf-8")
            meta, body = self._parse_frontmatter(text)
            name = meta.get("name", f.parent.name)
            self.skills[name] = {
                "meta": meta,
                "body": body,
                "path": str(f),
            }
            logger.info(f"已加载技能: {name} ({f})")

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text
        try:
            import yaml
            meta = yaml.safe_load(match.group(1)) or {}
        except ImportError:
            meta = self._parse_simple_frontmatter(match.group(1))
        except Exception:
            meta = {}
        return meta, match.group(2).strip()

    def _parse_simple_frontmatter(self, raw: str) -> dict:
        """简易 YAML 解析（无 pyyaml 依赖时的降级方案，支持 string/int/list）"""
        result = {}
        list_key = None
        list_values = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- ") and list_key:
                list_values.append(stripped[2:].strip())
                continue
            if list_key:
                result[list_key] = list_values
                list_key = None
                list_values = []
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if val == "":
                    list_key = key
                    list_values = []
                elif val.startswith("[") and val.endswith("]"):
                    result[key] = [v.strip() for v in val[1:-1].split(",") if v.strip()]
                else:
                    if val.isdigit():
                        val = int(val)
                    result[key] = val
        if list_key:
            result[list_key] = list_values
        return result

    # ========== Layer 1: 注入 system prompt ==========

    def get_descriptions(self) -> str:
        """Layer 1: 仅返回技能名 + 一句话描述，注入 system prompt"""
        if not self.skills:
            return "(no skills available)"
        lines = []
        for name, skill in self.skills.items():
            desc = skill["meta"].get("description", "No description")
            tags = skill["meta"].get("tags", "")
            line = f"  - {name}: {desc}"
            if tags:
                line += f" [{', '.join(tags) if isinstance(tags, list) else tags}]"
            lines.append(line)
        return "\n".join(lines)

    # ========== Layer 2: 按需加载完整正文 ==========

    def get_content(self, name: str) -> str:
        """Layer 2: 返回完整 SKILL.md 正文，供 LLM 读取后执行任务"""
        skill = self.skills.get(name)
        if not skill:
            available = ", ".join(self.skills.keys())
            return f"Error: Unknown skill '{name}'. Available: {available}"
        return f"<skill name=\"{name}\">\n{skill['body']}\n</skill>"


SKILL_LOADER = SkillLoader()
