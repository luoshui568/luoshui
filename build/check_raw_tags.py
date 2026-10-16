# -*- coding: utf-8 -*-
"""守门：样式表 / 脚本里绝不允许出现裸的 style / script 标签名。

为什么需要它（2026-10-15 真实事故）：
    report_theme.css 第 433 行的一句**注释**里写了 `<style id="rpt-txtstyle">`。
    这份 CSS 会被原样注入页面的样式表块里，浏览器解析样式表处于 RAWTEXT 状态，
    见到 `<style` 就认为「样式表到此结束」⇒ 从那一行往后 1080 行（全文 73%）
    共 386 条 CSS 规则全部失效：解读块点标题展不开、表格细线风丢失、
    时间轴/图表/地图样式全掉。**而且页面不报任何错**，只是「样式莫名其妙没了」。

    本文件是构建产物里唯一一个会整份注入样式表块的源文件，所以它是高危点。
    模板自带样式块 / theme.css 两边都要扫。

用法：
    python3 build/check_raw_tags.py                # 扫默认几个文件
    python3 build/check_raw_tags.py <file> ...     # 扫指定文件
退出码 0 = 干净，1 = 有裸标签。
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# style / script 开标签或闭标签，带或不带属性
PAT = re.compile(r'<\s*/?\s*(style|script)\b', re.I)

DEFAULT = [
    os.path.join(ROOT, 'build', 'report_theme.css'),
    os.path.join(ROOT, 'deploy', 'report.template.html'),
    os.path.join(ROOT, 'deploy', 'app.template.html'),
    os.path.join(ROOT, 'deploy', 'index.template.html'),
    os.path.join(ROOT, 'deploy', 'research.template.html'),
]


def scan(path):
    """返回 [(行号, 原文)]。

    只报**注释里**的裸标签 —— 正常的开 / 闭标签成对出现，是文档结构本身，必须放过。
    判据：把 HTML 里的注释段先挖掉，剩下的裸标签才算问题。
    （真出事故的那处就在 CSS 的 CSS 注释里，模板注释同样要扫。）
    """
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8', errors='replace') as f:
        raw = f.read()
    lines = raw.split('\n')

    # 挖掉 <!-- ... --> 与 /* ... */ 两类注释块
    spans = [(m.start(), m.end()) for m in re.finditer(r'<!--.*?-->', raw, re.S)]
    spans += [(m.start(), m.end()) for m in re.finditer(r'/\*.*?\*/', raw, re.S)]
    spans.sort()
    # 行首偏移 → 字节偏移，用来把命中映射回行号
    line_off, acc = [0], 0
    for ln in lines:
        acc += len(ln) + 1
        line_off.append(acc)

    def in_comment(pos):
        return any(a <= pos < b for a, b in spans)

    hits = []
    for i, line in enumerate(lines, 1):
        start = line_off[i - 1]
        for m in PAT.finditer(line):
            if in_comment(start + m.start()):
                hits.append((i, line.rstrip()[:160]))
                break
    return hits


def main():
    files = sys.argv[1:] or DEFAULT
    bad = 0
    for p in files:
        hits = scan(p)
        if hits is None:
            print('· 跳过（不存在）：%s' % os.path.relpath(p, ROOT))
            continue
        rel = os.path.relpath(p, ROOT)
        if not hits:
            print('✓ %s' % rel)
            continue
        bad += 1
        print('✗ %s —— 发现 %d 行疑似裸标签：' % (rel, len(hits)))
        for i, line in hits:
            print('    L%-6d %s' % (i, line))
    print()
    if bad:
        print('⚠️  %d 个文件有裸标签。注释里提到样式表块 / 脚本标签时，'
              '一律写成不带尖括号的说法，否则注入后会腰斩后面的 CSS。' % bad)
        return 1
    print('✓ 全部干净：没有任何裸标签。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
