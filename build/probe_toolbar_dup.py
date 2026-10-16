# -*- coding: utf-8 -*-
"""定位「区间按钮组重复」的真正根因：区分
   (a) 同一张图被插了两个 toolbar（St.slots 有重复 key）
   (b) 一个卡片里有两张 zoom 图，各自一个 toolbar（本属正常，用户看到的「重复」）
   (c) 两个 toolbar 在 DOM 里紧挨着（视觉上才是真重复）
"""
import http.server
import os
import re
import socketserver
import subprocess
import sys
import tempfile
import threading
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
SITE = 'https://liuchaowang.cn/report.html'
CODE = (sys.argv[1] if len(sys.argv) > 1 else '600456').strip()
PORT = 8893

PROBE = r"""
<style>*{animation:none !important;transition:none !important}</style>
<script>
var O = [];
setTimeout(function(){
  /* 1. slots 里有没有重复 key */
  var slots = (window.St && St.slots) || [];
  var seen = {}, dupKeys = [];
  slots.forEach(function(s){
    var k = s.key;
    if (seen[k]) dupKeys.push(k + ' x' + (seen[k] + 1));
    else seen[k] = 1;
  });
  O.push('slots总数=' + slots.length + ' 唯一key=' + Object.keys(seen).length);
  O.push('重复key=' + (dupKeys.length ? dupKeys.join(', ') : '无'));

  /* 2. 每个 .rpt-toolbar 的下一个兄弟是不是另一个 toolbar（紧挨着=视觉重复） */
  var tb = document.querySelectorAll('#mods .rpt-toolbar');
  var adj = 0;
  for(var i=0;i<tb.length;i++){
    var nx = tb[i].nextElementSibling;
    var pv = tb[i].previousElementSibling;
    if((nx && /\brpt-toolbar\b/.test(nx.className||'')) ||
       (pv && /\brpt-toolbar\b/.test(pv.className||''))){
      adj++;
      if(adj<=4){
        var c = tb[i].closest('.card');
        var ttl = c ? (c.querySelector('h2')||{textContent:''}).textContent.trim().slice(0,18) : '';
        O.push('紧挨#'+adj+' card=«'+ttl+'» 上一个=«'+String(pv?pv.className:'-').slice(0,24)+
               '» 下一个=«'+String(nx?nx.className:'-').slice(0,24)+'»');
      }
    }
  }
  O.push('紧挨着的toolbar组数=' + adj);

  /* 3. 每个 toolbar 对应哪张图（下一个兄弟的 data-chart） */
  var map = [];
  tb.forEach(function(t){
    var nx = t.nextElementSibling;
    var key = nx && nx.getAttribute ? (nx.getAttribute('data-chart')||'#'+nx.tagName) : 'null';
    var c = t.closest('.card');
    var ttl = c ? (c.querySelector('h2')||{textContent:''}).textContent.trim().slice(0,16) : '';
    var r1 = t.getBoundingClientRect(), r2 = nx ? nx.getBoundingClientRect() : null;
    map.push(key + '@' + Math.round(r1.top) + (r2 ? '→' + Math.round(r2.top) : ''));
  });
  O.push('toolbar→图: ' + map.join(' | '));

  /* 4. 用户截图那张图：销售毛利率 / 销售净利率 / ROE（加权）—— 定位它是哪个模块 */
  var hits = [];
  document.querySelectorAll('#mods .card').forEach(function(c, i){
    var tx = c.textContent || '';
    if(tx.indexOf('销售毛利率') >= 0 && tx.indexOf('ROE') >= 0){
      var n = c.querySelectorAll('.rpt-toolbar').length;
      var cn = c.querySelectorAll('canvas').length;
      hits.push('#' + (i+1) + ' toolbar=' + n + ' canvas=' + cn +
                ' h2=«' + (c.querySelector('h2')||{textContent:''}).textContent.trim().slice(0,20) + '»');
    }
  });
  O.push('毛利率卡: ' + (hits.length ? hits.join(' ; ') : '未找到'));

  document.title = '###' + O.join('\n');
}, 4500);
</script>
"""

src = os.environ.get('RPT_SRC')
if src:
    raw = open(src, encoding='utf-8', errors='replace').read()
else:
    raw = urllib.request.urlopen(SITE, timeout=60).read().decode('utf-8', 'replace')
i = raw.rfind('</body>')
html = raw[:i] + PROBE + raw[i:]
tmp = tempfile.mkdtemp(prefix='tb_')
open(os.path.join(tmp, 'r.html'), 'w', encoding='utf-8').write(html)


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=tmp, **kw)

    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
cmd = [EDGE, '--headless=new', '--user-data-dir=' + os.path.join(tmp, 'prof'),
       '--no-sandbox', '--no-proxy-server', '--disable-gpu',
       '--window-size='+(os.environ.get('WIN','1440,1200')), '--virtual-time-budget=12000',
       '--dump-dom', 'http://127.0.0.1:%d/r.html' % PORT]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=200)
m = re.search(r'<title>###(.*?)</title>', r.stdout, re.S)
print(m.group(1).replace('\\n', '\n') if m else '!! 没抓到')
srv.shutdown()
