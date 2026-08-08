#!/usr/bin/env python3
"""Structural balance checker for .alva source files.

alva 是 S-expression 语言：列表括号必须严格配对。这个工具在任何编译/语义
检查之前先做词法级平衡校验，报告：
  - 未闭合的 '(' 及其打开位置（按打开顺序列出，帮助快速定位）；
  - 多余的 ')' 及其位置；
  - 未闭合的字符串字面量。
它正确处理字符串内的转义（\" \\ \n 等），不会把字符串内容里的括号算进去。

用法：
  python scripts/check_parens.py <file.alva>...
  python scripts/check_parens.py --check-tree <dir> [--exclude <substr>]
      # 递归扫描目录，跳过路径中包含 <substr> 的文件
      # （例如故意不配对的 golden 用例目录）

退出码：0 = 全部平衡；1 = 存在结构错误。
"""

import os
import sys


def check(text, path):
    """Return (ok, problems) where problems is a list of human-readable strings."""
    stack = []  # (line, col) of each open '(' not yet closed
    problems = []
    line = 1
    col = 0
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            # string literal; handle escapes, stop at closing quote
            i += 1
            closed = False
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    closed = True
                    i += 1
                    break
                if text[i] == "\n":
                    break
                i += 1
            if not closed:
                problems.append(f"{path}:{line}:{col}: unterminated string literal")
            continue
        if c == ";":
            # comment to end of line
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "(":
            stack.append((line, col))
        elif c == ")":
            if stack:
                stack.pop()
            else:
                problems.append(f"{path}:{line}:{col}: unexpected ')' (no matching '(')")
        elif c == "\n":
            line += 1
            col = 0
            i += 1
            continue
        i += 1
        col += 1
    for (l, c) in stack:
        problems.append(f"{path}:{l}:{c}: unclosed '('")
    return (not problems and not stack), problems


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: check_parens.py <file.alva>... | --check-tree <dir>")
        return 2
    files = []
    if args[0] == "--check-tree":
        root = args[1]
        exclude = None
        if len(args) > 2 and args[2] == "--exclude":
            exclude = args[3]
        for dirpath, _dirs, names in os.walk(root):
            for name in names:
                if name.endswith(".alva"):
                    full = os.path.join(dirpath, name)
                    if exclude and exclude in full.replace("\\", "/"):
                        continue
                    files.append(full)
    else:
        files = args
    ok = True
    for f in sorted(files):
        with open(f, encoding="utf-8") as fh:
            text = fh.read()
        good, problems = check(text, f)
        if good:
            print(f"PASS parens {os.path.basename(f)}")
        else:
            ok = False
            print(f"FAIL parens {os.path.basename(f)}")
            for p in problems[:10]:
                print(f"  {p}")
            if len(problems) > 10:
                print(f"  ... and {len(problems) - 10} more")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
