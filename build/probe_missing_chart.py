# -*- coding: utf-8 -*-
"""验证「库里没有图表数据 ⇒ 浏览态整块隐藏」这条新逻辑真的生效。

做法（不动仓库里的任何数据文件）：
  读 deploy/report.html → 解析壳内 window.RPT_SEED → **在内存里**删掉指定图表
  → 回写成 build/_pv_missing.html → headless 渲染 → 报告实际 DOM 状态。
再跑一次「编辑模式」对照，确认编辑态仍保留可填的占位。

用法：python build/_pv_missing.py [要删掉的图表 key，逗号分隔]
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
DROP = (sys.argv[1] if len(sys.argv) > 1 else 'chartDividend').split(',')

src = io.open(os.path.join(ROOT, 'deploy', 'report.html'), encoding='utf-8').read()

# 定位壳内 RPT_SEED 并解析（不用正则 —— JSON 里也有 '};'）
i = src.find('window.RPT_SEED')
j = src.find('=', i) + 1
while src[j] in ' \t\r\n':
    j += 1
seed, end = json.JSONDecoder().raw_decode(src[j:])
before = len(seed['charts'])
seed['charts'] = [c for c in seed['charts'] if c.get('id') not in DROP]
after = len(seed['charts'])
patched = src[:j] + json.dumps(seed, ensure_ascii=False, separators=(',', ':')) + src[j + end:]

PROBE = """
<script>
setTimeout(function(){
  var out = [];
  var m15 = document.querySelector('#m15') || document.querySelector('[data-chart="%s"]');
  out.push('cards=' + document.querySelectorAll('#mods .card').length);
  out.push('canvas=' + document.querySelectorAll('#mods canvas').length);
  out.push('slots=' + document.querySelectorAll('#mods [data-chart]').length);
  out.push('chartmiss=' + document.querySelectorAll('#mods .rpt-chartmiss').length);
  out.push('slotgone=' + document.querySelectorAll('#mods .rpt-slotgone').length);
  var g = document.querySelector('[data-chart="%s"]');
  if(g){
    var cs = getComputedStyle(g);
    out.push('目标槽位 display=' + cs.display + ' | 高度=' + Math.round(g.getBoundingClientRect().height) +
             ' | 有斜纹空框=' + (g.querySelector('.rpt-chartmiss') ? '是' : '否'));
  }
  out.push('MISS=[' + Array.prototype.map.call(document.querySelectorAll('#mods .rpt-chartmiss'),
            function(x){ return x.textContent.slice(0,32); }).join(' | ') + ']');
  out.push('GONE=[' + Array.prototype.map.call(document.querySelectorAll('#mods .rpt-slotgone'),
            function(x){ return x.getAttribute('data-chart'); }).join(' | ') + ']');
  var d = document.createElement('div'); d.id = 'probeout'; d.textContent = out.join('\\n');
  document.body.appendChild(d);
}, 4000);
</script>
</html>""" % (DROP[0], DROP[0])


def run(html, tag):
    pv = os.path.join(ROOT, 'build', '_pv_missing.html')
    io.open(pv, 'w', encoding='utf-8').write(html)
    url = 'file:///' + pv.replace('\\', '/') + '?code=600456'
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--force-device-scale-factor=1', '--window-size=1440,1000',
           '--virtual-time-budget=20000', '--dump-dom', url]
    r = subprocess.run(cmd, capture_output=True, timeout=500)
    dom = (r.stdout or b'').decode('utf-8', 'replace')
    m = re.search(r'<div id="probeout">(.*?)</div>', dom, re.S)
    print('########', tag)
    print(unescape(m.group(1)) if m else ('未拿到探针输出，DOM 长度 %d' % len(dom)))
    print()


print('壳内 RPT_SEED 图表：%d → %d（内存里删掉 %s）' % (before, after, DROP))
print()

base = patched[:patched.rfind('</html>')]
run(base + PROBE, '浏览态（St.edit = false）')

# 编辑模式对照：强制 St.edit = true 后重渲染
EDIT = """
<script>
setTimeout(function(){
  try{ St.edit = true; document.documentElement.classList.add('edit');
       renderMods(); renderCharts(); }catch(e){ }
}, 2600);
</script>
"""
run(base + EDIT + PROBE, '编辑态（St.edit = true）—— 应保留可填的虚线占位')
