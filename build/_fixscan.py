# -*- coding: utf-8 -*-
"""定位「{'t': xx,  'x': ( ... 'str'),」缺收尾 } 的块（字符串感知，逐字符扫描）。
用法: python _fixscan.py _mk_002408.py
"""
import io, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
path = sys.argv[1]
src = io.open(path, encoding='utf-8').read()
lines = src.split('\n')

# 字符串感知的括号栈
stack = []          # (char, lineno, col)
i = 0
n = len(src)
line = 1
col = 0
errors = []
while i < n:
    ch = src[i]
    if ch == '\n':
        line += 1
        col = 0
        i += 1
        continue
    if ch == '#':
        while i < n and src[i] != '\n':
            i += 1
        continue
    if ch in '"\'':
        q = ch
        triple = src[i:i + 3] == q * 3
        if triple:
            i += 3
            while i < n and src[i:i + 3] != q * 3:
                if src[i] == '\\':
                    i += 2
                    continue
                if src[i] == '\n':
                    line += 1
                i += 1
            i += 3
        else:
            i += 1
            while i < n and src[i] != q:
                if src[i] == '\\':
                    i += 2
                    continue
                if src[i] == '\n':
                    errors.append('L%d: 字符串未闭合' % line)
                    break
                i += 1
            i += 1
        continue
    if ch in '([{':
        stack.append((ch, line, col))
    elif ch in ')]}':
        pair = {')': '(', ']': '[', '}': '{'}[ch]
        if stack and stack[-1][0] == pair:
            stack.pop()
        else:
            top = stack[-1] if stack else None
            errors.append('L%d C%d: 遇到 %s，栈顶是 %s%s'
                          % (line, col, ch,
                             top[0] if top else '空',
                             (' (开于 L%d C%d)' % (top[1], top[2])) if top else ''))
            if stack:
                stack.pop()
    i += 1
    col += 1

for e in errors:
    print(e)
print('--- 未闭合 %d ---' % len(stack))
for c, l, cc in stack[:40]:
    print('  %s @ L%d C%d | %s' % (c, l, cc, lines[l - 1].strip()[:70] if l - 1 < len(lines) else ''))
