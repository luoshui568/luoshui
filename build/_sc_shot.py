# -*- coding: utf-8 -*-
"""槽 29「动态调整」目视取证图 —— 两态全貌 + 细节拼图。

为什么要单独一个脚本：`_sc_test.py` 管断言（--dump-dom 读文本），目视要的是**图**。
两者共用同一套「壳 CSS + scoreLive 段 + 线上真模块 HTML」，所以 JS 直接从
`_sc_test.score_js()` 借，绝不抄第二份。

★ 两个踩过的坑写在这里，别再犯：
  1) `--screenshot` 只截**视口**高度 ⇒ 窗口必须开够高，否则第二段被切掉（1280×1560 时只出到①）；
  2) 别靠肉眼估裁剪坐标 —— 让驱动脚本自己把各元素 `getBoundingClientRect()` 写进
     `<title>`，先 `--dump-dom` 取回来，再按坐标精确裁（估坐标绕了三圈）。

产出（deliver/）：
  研报-槽29动态调整-<code>-<日期>.png    两段全貌：① 静态原貌 ② 调整后
  研报-槽29动态调整-细节-<日期>.png      细节：② 的环形卡 + 两段底部实时条
用法： python _sc_shot.py [--code 002408]
"""
import io
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DELIVER = os.path.join(ROOT, 'deliver')
EDGE = r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
EDGE2 = r'C:/Program Files/Microsoft/Edge/Application/msedge.exe'
STAMP = '20260922'
# ★ 两次运行（dump-dom 量坐标 / screenshot 出图）**必须同视口** ——
#   不给 --window-size 时 headless 默认 800×600，窄视口会把正文换行改掉，
#   量出来的坐标贴到宽截图上就全歪了（踩过：细节拼图裁成了 688px 宽的碎条）。
WIN = '1300,6000'

from _sc_test import score_js                             # noqa: E402
from _apply_score import get_live                          # noqa: E402
import score_lock as SL                                    # noqa: E402

DRIVER = r"""
scoreLive(document);
function inpOf(sec, i){ return document.querySelector('[data-mod="' + sec + '"]').querySelectorAll('.sc-inp')[i]; }
function setI(sec, i, v){
  var el = inpOf(sec, i);
  el.value = v;
  el.dispatchEvent(new Event('input', {bubbles: true}));
  el.dispatchEvent(new Event('change', {bubbles: true}));
}
function dragTo(sec, i, frac){
  var bar = document.querySelector('[data-mod="' + sec + '"]').querySelectorAll('.sc-bar')[i];
  var r = bar.getBoundingClientRect();
  var o = {bubbles: true, cancelable: true, pointerId: 9, pointerType: 'mouse',
           button: 0, buttons: 1, clientX: r.left + r.width * frac,
           clientY: r.top + r.height / 2};
  bar.dispatchEvent(new PointerEvent('pointerdown', o));
  bar.dispatchEvent(new PointerEvent('pointerup', o));
}
/* ② 区：改两项 —— 第 T3 项改成 10、第 D2 项拖到 30%（⇒3 分） */
setI('B', T3, 10);
dragTo('B', D2, 0.3);
/* 把刚拖过的那行留在「拖动中」样式（手柄 + 左侧竖线）—— 真实可达状态，
   静态截图抓不到指针悬停，所以显式摆出来，图上注明 */
document.querySelector('[data-mod="B"]').querySelectorAll('.sc-line')[D2].classList.add('sc-drag');
/* ① 区：给一个输入框聚焦态（**保留原分数**，不改值）——演示「可直接点着改」 */
(function(){ var el = inpOf('A', FOCUS); if(el && el.focus) el.focus(); })();
/* ★ 报坐标（别用肉眼估裁剪位置） */
function bx(sel){
  var el = document.querySelector(sel);
  if(!el) return null;
  var r = el.getBoundingClientRect();
  return [Math.round(r.left), Math.round(r.top + window.pageYOffset),
          Math.round(r.right), Math.round(r.bottom + window.pageYOffset)];
}
document.title = JSON.stringify({
  Ahero: bx('[data-mod="A"] .score-hero'), Acrit: bx('[data-mod="A"] .criteria'),
  Alive: bx('[data-mod="A"] .sc-livebar'),   Bsrc: bx('[data-mod="B"] .criteria + p'),
  Bhero: bx('[data-mod="B"] .score-hero'), Bcrit: bx('[data-mod="B"] .criteria'),
  Blive: bx('[data-mod="B"] .sc-livebar'),   page: document.body.scrollHeight,
  ready: 1
});
"""


def make_page(live, t3, d2, focus, caps):
    css = io.open(os.path.join(HERE, 'report_theme.css'), encoding='utf-8').read()
    js = score_js()
    parts = []
    for sid, ttl in caps:
        parts.append('<div class="card" id="m29%s" data-mod="%s">'
                     '<h2><span class="no">29</span>企业评分</h2>%s</div>'
                     '<p class="shotcap">%s</p>' % (sid, sid, live, ttl))
    page = ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<title>-</title><style>' + css +
            '\nbody{background:#fafafa;padding:18px 22px;max-width:1240px;margin:0 auto;}\n'
            '.shotcap{font:13px/1.7 -apple-system,"Microsoft YaHei",sans-serif;color:#8a8a90;'
            'margin:14px 2px 30px;padding-left:10px;border-left:3px solid #d0202f;}\n'
            '</style></head><body>\n' + '\n'.join(parts) +
            '\n<script>var T3=' + str(t3) + ',D2=' + str(d2) + ',FOCUS=' + str(focus) + ';</script>'
            '\n<script>' + js + '</script>\n<script>' + DRIVER + '</script>\n</body></html>')
    p = os.path.join(HERE, '_sc_shot.html')
    io.open(p, 'w', encoding='utf-8').write(page)
    return p


def edge_run(edge, page, extra, budget='6000'):
    return subprocess.run([edge, '--headless=new', '--disable-gpu', '--no-sandbox',
                           '--hide-scrollbars', '--force-device-scale-factor=1',
                           '--virtual-time-budget=' + budget] + extra +
                          ['file:///' + page.replace('\\', '/')],
                          capture_output=True, text=True, errors='replace')


def boxes_of(edge, page):
    r = edge_run(edge, page, ['--window-size=' + WIN, '--dump-dom'])
    m = re.search(r'<title>(.*?)</title>', r.stdout or '', re.S)
    if not m:
        sys.exit('✗ 取不到页面坐标（title 缺失）')
    try:
        return json.loads(m.group(1))
    except Exception as e:
        sys.exit('✗ 坐标 JSON 解析失败：%s｜%s' % (e, m.group(1)[:200]))


def main():
    code = '002408'
    if '--code' in sys.argv:
        code = sys.argv[sys.argv.index('--code') + 1]
    row = get_live(code) or {}
    live = row.get('html') or ''
    if not live:
        sys.exit('✗ 取不到线上 %s 的槽 29' % code)
    name = row.get('name') or code
    base = [int(x) for x in re.findall(r'<div class="sc-val">(\d+)</div>', live)]
    if len(base) != 10:
        sys.exit('✗ %s 不是有分形态' % code)
    t3 = next(i for i in range(10) if base[i] != 10)
    d2 = next((i for i, v in enumerate(base) if v not in (3, 10) and i != t3), 3)
    focus = next(i for i in range(10) if i not in (t3, d2))
    exp = base[:]; exp[t3] = 10; exp[d2] = 3
    tot0 = SL.total_of(base)
    tot1 = SL.total_of(exp)

    caps = [('A', '① 静态原貌（未调整 · 与线上完全一致）｜第 %d 项输入框处于聚焦态，'
                  '演示「可直接点着改分数」' % (focus + 1)),
            ('B', '② 调整后（第 %d 项改成 10、第 %d 项拖到 30%% ⇒ 3 分）：总分 %s → %s、'
                  '评级与环形卡实时重算、徽标由金转红、底部出现「已调整 → %s」与恢复按钮；'
                  '第 %d 项停在「拖动中」样式（手柄仅指针悬停/拖动时出现）'
                  % (t3 + 1, d2 + 1, _f1(tot0), _f1(tot1), _f1(tot1), d2 + 1))]
    page = make_page(live, t3, d2, focus, caps)
    edge = EDGE if os.path.exists(EDGE) else EDGE2

    b = boxes_of(edge, page)
    if not b.get('ready'):
        sys.exit('✗ 驱动没跑完：%s' % b)
    h = int(b['page']) + 40
    print('%s 初评 %s → 调整后 %s ｜ 页高 %s' % (code, _f1(tot0), _f1(tot1), h))

    if not os.path.isdir(DELIVER):
        os.makedirs(DELIVER)
    full = os.path.join(DELIVER, '研报-槽29动态调整-%s-%s.png' % (code, STAMP))
    edge_run(edge, page, ['--window-size=' + WIN,
                          '--screenshot=' + full.replace('\\', '/')])
    if not os.path.exists(full):
        sys.exit('✗ 截图失败')
    print('✓ 两态全貌 %s' % full)

    try:
        from PIL import Image, ImageChops
    except ImportError:
        print('（无 PIL，跳过裁白与细节拼图 —— 用 venv 的 python 跑本脚本即可）')
        print('注：%s %s' % (code, name))
        return 0

    # —— 裁掉底部空白（窗口开高是为了不切内容，多半会留一大片） ——
    im = Image.open(full).convert('RGB')
    w, hh = im.size
    bg = Image.new('RGB', (w, 1), (250, 250, 250))
    last = hh
    for y in range(hh - 1, 0, -30):
        if ImageChops.difference(im.crop((0, y, w, y + 1)), bg).getbbox():
            last = min(hh, y + 40)
            break
    im = im.crop((0, 0, w, last))
    im.save(full)
    print('  裁白后 %d×%d' % im.size)

    # —— 细节拼图：② 的环形卡 + 两段的底部实时条（坐标来自页面自报，不靠估） ——
    pieces = []
    for key, pad in (('Bhero', 14), ('Alive', 10), ('Blive', 10)):
        bb = b.get(key)
        if not bb:
            continue
        x0, y0, x1, y1 = bb
        pieces.append(im.crop((max(0, x0 - pad), max(0, y0 - pad),
                               min(im.size[0], x1 + pad), min(im.size[1], y1 + pad))))
    if pieces:
        gap, bgc = 16, (250, 250, 250)
        W = max(p.size[0] for p in pieces)
        H = sum(p.size[1] for p in pieces) + gap * (len(pieces) - 1)
        canvas = Image.new('RGB', (W, H), bgc)
        y = 0
        for p in pieces:
            canvas.paste(p, (0, y)); y += p.size[1] + gap
        detail = os.path.join(DELIVER, '研报-槽29动态调整-细节-%s.png' % STAMP)
        canvas.save(detail)
        print('✓ 细节拼图 %s（%d×%d，%d 块）' % (detail, W, H, len(pieces)))
    print('注：%s %s' % (code, name))
    return 0


def _f1(x):
    s = ('%.1f' % x)
    return s[:-2] if s.endswith('.0') else s


if __name__ == '__main__':
    sys.exit(main())
