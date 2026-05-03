"""
字数统计工具 —— 检查章节篇幅是否符合规范（每章 2000-3000 字）。
用法: python word_counter.py <file_path>
"""
import sys
import re

STYLE_GUIDE_MIN = 2000
STYLE_GUIDE_MAX = 3000


def count_chinese(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def count_words(text: str) -> int:
    en_words = len(re.findall(r"[a-zA-Z]+", text))
    cn_chars = count_chinese(text)
    return en_words + cn_chars


def readability_check(word_count: int) -> str:
    if word_count < STYLE_GUIDE_MIN:
        return f"[偏短] {word_count} 字 < 推荐下限 {STYLE_GUIDE_MIN}，建议补充内容"
    if word_count > STYLE_GUIDE_MAX:
        return f"[偏长] {word_count} 字 > 推荐上限 {STYLE_GUIDE_MAX}，建议拆分或精简"
    return f"[合格] {word_count} 字，推荐范围 {STYLE_GUIDE_MIN}-{STYLE_GUIDE_MAX}"


def main():
    if len(sys.argv) < 2:
        print("用法: python word_counter.py <file_path>")
        sys.exit(1)

    filepath = sys.argv[1]
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"文件不存在: {filepath}")
        sys.exit(1)

    words = count_words(text)
    cn = count_chinese(text)
    lines = text.count("\n") + 1

    print(f"文件: {filepath}")
    print(f"  总字数: {words} (中文 {cn} + 英文 {words - cn})")
    print(f"  总行数: {lines}")
    print(f"  篇幅评估: {readability_check(words)}")


if __name__ == "__main__":
    main()
