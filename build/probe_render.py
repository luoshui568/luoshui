# -*- coding: utf-8 -*-
"""本地研报页 headless 体检：真实渲染一遍，统计
  · canvas 数量（== 渲染成功的图表数）
  · 空态框 rpt-chartmiss 的个数与所在模块
  · 被隐藏的孤儿槽位 rpt-slotgone 的个数与 key
只读，不改任何数据。

用法：python build/_probe_render.py [code] [视口宽] [视口高]
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
CODE = sys.argv[1] if len(sys.argv) > 1 else '600456'
W = sys.argv[2] if len(sys.argv) > 2 else '1440'
H = sys.argv[3] if len(sys.argv) > 3 else '1000'

src = io.open(os.path.join(ROOT, 'deploy', 'report.html'), encoding='utf-8').read()

# 探针：渲染完后把每个模块的状态吐到一个 div 里
PROBE = """
<script>
setTimeout(function(){
  var out = [];
  var cards = document.querySelectorAll('#mods .card');
  out.push('cards=' + cards.length);
  out.push('canvas=' + document.querySelectorAll('#mods canvas').length);
  out.push('slots=' + document.querySelectorAll('#mods [data-chart]').length);
  out.push('chartmiss=' + document.querySelectorAll('#mods .rpt-chartmiss').length);
  out.push('slotgone=' + document.querySelectorAll('#mods .rpt-slotgone').length);
  out.push('gr-solo=' + document.querySelectorAll('#mods .grid2.gr-solo').length);
  var miss = [], gone = [];
  for(var i = 0; i < cards.length; i++){
    var c = cards[i];
    var mm = c.querySelectorAll('.rpt-chartmiss');
    for(var j = 0; j < mm.length; j++) miss.push(c.id + ':' + (mm[j].textContent || '').slice(0, 40));
    var gg = c.querySelectorAll('.rpt-slotgone');
    for(var k = 0; k < gg.length; k++) gone.push(c.id + ':' + gg[k].getAttribute('data-chart'));
  }
  out.push('MISS=[' + miss.join(' | ') + ']');
  out.push('GONE=[' + gone.join(' | ') + ']');
  /* 逐模块的图表数 */
  var per = [];
  for(var t = 0; t < cards.length; t++){
    per.push(cards[t].id + '=' + cards[t].querySelectorAll('canvas').length + '/' +
             cards[t].querySelectorAll('[data-chart]').length);
  }
  out.push('PER=' + per.join(' '));
  var d = document.createElement('div'); d.id = 'probeout'; d.textContent = out.join('\\n');
  document.body.appendChild(d);
}, 4000);
</script>
</html>"""

pv = os.path.join(ROOT, 'build', '_pv_render.html')
i = src.rfind('</html>')
io.open(pv, 'w', encoding='utf-8').write(src[:i] + PROBE)

url = 'file:///' + pv.replace('\\', '/') + '?code=' + CODE
cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
       '--force-device-scale-factor=1', '--window-size=%s,%s' % (W, H),
       '--virtual-time-budget=20000', '--dump-dom', url]
r = subprocess.run(cmd, capture_output=True, timeout=600)
dom = (r.stdout or b'').decode('utf-8', 'replace')
m = re.search(r'<div id="probeout">(.*?)</div>', dom, re.S)
if not m:
    print('未拿到探针输出；DOM 长度', len(dom))
    sys.exit(1)
from html import unescape
for line in unescape(m.group(1)).split('\n'):
    print(line)
