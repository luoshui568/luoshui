# -*- coding: utf-8 -*-
"""第五版目录（竖线段 + 动态 hover）：把本地 CSS(nav.toc 段) 与 renderToc/tocSpy 搬到线上文件。

用法：python build/_toc5_mk.py
输入：_work/live.html（curl 线上 a8c64132 版）
输出：_work/p5.html（待发布）、_work/p5_prev.html（冻动画，供截图）
⚠️ /tmp 会被会话清空，工作文件一律放项目内。
"""
import io
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(ROOT, 'build/report_theme.css')
TPL = os.path.join(ROOT, 'deploy/report.template.html')
LIVE = os.path.join(ROOT, '_work/live.html')
OUT = os.path.join(ROOT, '_work/p5.html')
PREV = os.path.join(ROOT, '_work/p5_prev.html')

END = '核心结论（2026-10-14 版式重做）'


def css_seg(s):
    """目录样式段的 [起, 止)。起点 = 主规则 nav.toc{ 前最近的一条注释（横幅）。
    ⚠️ 不能用「左侧竖排目录」定位：`.wrap` 那条注释里也写了这四个字。"""
    k = s.index('nav.toc{')
    i = s.rindex('/*', 0, k)
    j = s.rindex('/*', 0, s.index(END))
    return i, j


def grab(s, a, b):
    i = s.index(a)
    j = s.index(b, i)
    return i, j, s[i:j]


M_R0 = '/* 序号补零：目录条要显示成 01'
M_R1 = '/* 左侧竖排目录：滚动时高亮'
M_S0 = 'function tocSpy(){'
M_S1 = 'var _tocTick = 0;'

css = io.open(CSS, encoding='utf-8').read()
tpl = io.open(TPL, encoding='utf-8').read()
live = io.open(LIVE, encoding='utf-8').read()

ci, cj = css_seg(css)
li, lj = css_seg(live)
new_css, old_css = css[ci:cj], live[li:lj]

assert 'tc-step' in new_css and 'max-width:1427px' in new_css, 'CSS 段抓错（本地）'
assert 'tc-step' not in old_css, '线上已经是新版了？'
print('线上段：%d 字节 / nav.toc{×%d / 1427 断点=%s'
      % (len(old_css.encode()), old_css.count('nav.toc{'), 'max-width:1427px' in old_css))
print('CSS 段 %d → %d 字节' % (len(old_css.encode()), len(new_css.encode())))

ti, tj, new_render = grab(tpl, M_R0, M_R1)
ti2, tj2, new_spy = grab(tpl, M_S0, M_S1)
li3, lj3, old_render = grab(live, M_R0, M_R1)
li2, lj2, old_spy = grab(live, M_S0, M_S1)
print('renderToc %d → %d ／ tocSpy %d → %d'
      % (len(old_render.encode()), len(new_render.encode()),
         len(old_spy.encode()), len(new_spy.encode())))
assert li < li3 < lj3 <= li2, '段偏移顺序异常'

out = live[:li2] + new_spy + live[lj2:]
out = out[:li3] + new_render + out[lj3:]
out = out[:li] + new_css + out[lj:]

io.open(OUT, 'w', encoding='utf-8').write(out)
b = out.encode()
print('写出 p5.html %d 字节  md5=%s' % (len(b), hashlib.md5(b).hexdigest()[:8]))

kill = ('<style>*,*::before,*::after{animation:none !important;'
        'transition:none !important}</style>')
io.open(PREV, 'w', encoding='utf-8').write(out.replace('</head>', kill + '</head>'))
print('写出 p5_prev.html（冻动画）')

# 严格超集自检：按各自文件的段边界抠掉三处替换后，其余字节必须逐字节相同
oi, oj = css_seg(out)
a = (live[:li] + live[lj:]).replace(old_render, '', 1).replace(old_spy, '', 1)
bb = (out[:oi] + out[oj:]).replace(new_render, '', 1).replace(new_spy, '', 1)
print('超集自检：其余字节 %s' % ('✅ 一致' if a == bb else '❌ 不一致 %d/%d' % (len(a), len(bb))))
