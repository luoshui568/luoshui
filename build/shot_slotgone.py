# -*- coding: utf-8 -*-
"""空图表槽位「改前 / 改后」对照取证图。

A 面板 = 库里有图（正常渲染）
B 面板 = 库里的图不见了（在内存里删掉，不动任何数据文件）→ 新版逻辑应整块消失
两个面板都只显示「历年分红明细」所在的那一个模块卡片，滚到图槽位置截图。

用法：python build/_shot_slotgone.py
"""
import io
import json
import os
import re
import subprocess
import sys
from html import unescape

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
KEY = 'chartDividend'
DESK = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\deliver'   # 2026-09-21 起不再落桌面

src = io.open(os.path.join(ROOT, 'deploy', 'report.html'), encoding='utf-8').read()

# ---- B：内存里删掉那张图 ----------------------------------------------------
i = src.find('window.RPT_SEED')
j = src.find('=', i) + 1
while src[j] in ' \t\r\n':
    j += 1
seed, end = json.JSONDecoder().raw_decode(src[j:])
seed['charts'] = [c for c in seed['charts'] if c.get('id') != KEY]
missing = src[:j] + json.dumps(seed, ensure_ascii=False, separators=(',', ':')) + src[j + end:]

# ---- 只显示目标模块 + 关掉动画 + 滚到图槽 ----------------------------------
def solo(html):
    inject = """
<style>
  .wrap > *:not(#mods){display:none !important;}
  #mods > .card{display:none !important;}
  #mods > .card#shotcard{display:block !important;animation:none !important;opacity:1 !important;margin-top:0 !important;}
  *,*::before,*::after{animation:none !important;transition:none !important;}
  body{padding-top:0 !important;}
  .rbar,nav.toc,#foot,.rpt-mask{display:none !important;}
</style>
<script>
setTimeout(function(){
  var el = document.querySelector('[data-chart="%s"]');
  var c = el;
  if(c){
    while(c && c !== document.body && !(c.className||'').match(/(^|\\s)card(\\s|$)/)) c = c.parentNode;
    if(c && c !== document.body) c.id = 'shotcard';
  }
  /* 不滚动：把目标卡片顶到页面最上面，靠足够高的视口把整张卡片一次拍完
     （B 版里图槽是 display:none，getBoundingClientRect 会返回全 0，滚不了） */
  window.scrollTo(0, 0);
}, 3200);
</script>
</html>""" % KEY
    k = html.rfind('</html>')
    return html[:k] + inject


def shoot(html, tag):
    pv = os.path.join(ROOT, 'build', '_sg_%s.html' % tag)
    io.open(pv, 'w', encoding='utf-8').write(solo(html))
    out = os.path.join(ROOT, 'build', '_sg_%s.png' % tag)
    url = 'file:///' + pv.replace('\\', '/') + '?code=600456'
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--force-device-scale-factor=1', '--window-size=1240,1750',
           '--virtual-time-budget=16000', '--screenshot=' + out, url]
    subprocess.run(cmd, capture_output=True, timeout=500)
    print(tag, os.path.exists(out), os.path.getsize(out) if os.path.exists(out) else 0)
    return out


a = shoot(src, 'ok')        # 有图
b = shoot(missing, 'gone')  # 图没了

# ---- 拼接 ------------------------------------------------------------------
from PIL import Image, ImageDraw

ia = Image.open(a).convert('RGB')
ib = Image.open(b).convert('RGB')
W = max(ia.width, ib.width)
PAD, BAR, GAP = 0, 46, 14
canvas = Image.new('RGB', (W, BAR + ia.height + GAP + BAR + ib.height), '#f2f2f2')
d = ImageDraw.Draw(canvas)


def bar(y, text, color):
    d.rectangle([0, y, W, y + BAR], fill=color)
    d.text((18, y + 15), text, fill='#ffffff')


y = 0
bar(y, 'A · 库里有这张图（正常渲染）', '#3a3a40')
y += BAR
canvas.paste(ia, (0, y))
y += ia.height + GAP
bar(y, 'B · 库里的图被删掉了 —— 新版逻辑：整块不再出现（不再有「暂无数据」空框）', '#0b6ea8')
y += BAR
canvas.paste(ib, (0, y))

out = os.path.join(DESK, '研报-空图表不再显示空框-20260920.png')
canvas.save(out)
print('OK ->', out, canvas.size)
