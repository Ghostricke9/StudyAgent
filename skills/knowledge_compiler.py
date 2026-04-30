"""
知识编撰技能 - 将搜索和研究资料整理成结构化教学教材
"""
import json

COMPILE_KNOWLEDGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "compile_knowledge",
        "description": (
            "将已有的研究资料和网页内容编撰成结构化的教学教材。"
            "分章节组织，包含关键概念、详细讲解、代码/公式示例、小节总结。"
            "请分次调用，每次编撰一个章节。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "教材主题，如 'Python面向对象编程'",
                },
                "chapter_title": {
                    "type": "string",
                    "description": "本章标题，如 '第1章：类与对象基础'",
                },
                "chapter_number": {
                    "type": "integer",
                    "description": "章节编号",
                },
                "source_materials": {
                    "type": "string",
                    "description": "本章参考的研究资料（来自网页抓取的内容摘要）",
                },
            },
            "required": ["topic", "chapter_title", "source_materials"],
        },
    },
}

COMPILE_KNOWLEDGE_PROMPT = """## 技能：编撰教学教材 - {{topic}}

### 当前任务
为【{{chapter_title}}】编撰教材内容。

### 参考资料
{{source_materials}}

### 编撰要求

请严格按照以下 Markdown 格式输出本章内容：

```markdown
# {{topic}}

## {{chapter_title}}

### 本章目标
- [列出3-5个本章学习目标]

### 关键概念
| 概念 | 解释 |
|------|------|
| 概念1 | 简明解释 |
| 概念2 | 简明解释 |

### 详细讲解
[分小节详细讲解本章知识点，每个小节包含：
- 概念引入（为什么需要这个知识）
- 核心内容讲解
- 代码示例或公式推导（如适用）
- 常见误区或注意事项]

### 示例
[提供1-2个完整的代码/公式/案例示例]

### 本章小结
[3-5句话总结本章关键知识点]

### 进阶思考
[1-2个引导读者深入思考的问题]
```

### 编撰原则
1. 循序渐进：从基础概念到深层原理
2. 理论与实践结合：每个概念配合实际示例
3. 语言清晰：避免过于学术化，用通俗语言解释复杂概念
4. 保留原出处：引用参考资料中的重要数据或观点时标注来源
5. 控制篇幅：本章内容控制在2000-3000字

请直接输出编撰好的教材内容，不要输出其他无关内容。"""
