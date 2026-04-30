"""
练习题生成技能 - 根据教学内容生成配套练习题
"""
import json

GENERATE_EXERCISES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_exercises",
        "description": (
            "根据教学章节的内容生成配套练习题。"
            "包含选择题、填空题、简答题和实践题等多种题型。"
            "每题附带参考答案和解析。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chapter_title": {
                    "type": "string",
                    "description": "对应的章节标题",
                },
                "chapter_content": {
                    "type": "string",
                    "description": "该章节的教学内容（由 compile_knowledge 生成）",
                },
                "exercise_count": {
                    "type": "integer",
                    "description": "练习题总数，默认5题",
                },
            },
            "required": ["chapter_title", "chapter_content"],
        },
    },
}

GENERATE_EXERCISES_PROMPT = """## 技能：生成配套练习题

### 对应章节
{{chapter_title}}

### 章节教学内容
{{chapter_content}}

### 出题要求

请为以上章节生成练习题，格式如下：

```markdown
## 练习题：{{chapter_title}}

### 一、选择题（2题）
**第1题** [题目描述]
A. [选项A]
B. [选项B]
C. [选项C]
D. [选项D]

**第2题** [题目描述]
A. [选项A]
B. [选项B]
C. [选项C]
D. [选项D]

### 二、填空题（1题）
**第3题** [包含空格的题目描述，用 ＿＿＿ 表示填空处]

### 三、简答题（1题）
**第4题** [简答题描述]

### 四、实践题（1题）
**第5题** [需要动手实践的题目描述]

---

## 参考答案与解析

### 选择题
**第1题答案：X**
解析：[说明为什么选这个，为什么不选其他的]

**第2题答案：X**
解析：[说明为什么选这个，为什么不选其他的]

### 填空题
**第3题答案：[填空内容]**
解析：[说明填空的依据]

### 简答题
**第4题参考答案：**
[给出参考回答要点]

### 实践题
**第5题参考思路：**
[给出解题思路和关键步骤]
```

### 出题原则
1. 覆盖核心知识点：题目要覆盖本章的关键概念
2. 难度梯度：从基础识记 → 理解应用 → 分析创造
3. 解析详尽：每个答案都要有为什么对/错的分析
4. 实践题有可操作性：提供具体的操作步骤或代码框架
5. 与教学内容紧密关联：不要出超纲题

请直接输出练习题内容，不要输出其他无关内容。"""
