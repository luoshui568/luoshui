# -*- coding: utf-8 -*-
"""量 markTxt 为什么 0 命中：把它的判据逐条打出来。"""
import http.server
import os
import re
import socketserver
import subprocess
import sys
import tempfile
import threading

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
PORT = 8891

PROBE = r"""
<script>
var O = [];
setTimeout(function(){
  /* is-txt 打标结果 */
  O.push('is-txt 格数=' + document.querySelectorAll('#mods td.is-txt').length);
  O.push('is-num 格数=' + document.querySelectorAll('#mods td.is-num').length);
  O.push('blockscript 在=' + (typeof window.__rptBlockStyle));

  /* 复刻 markTxt 的判据，逐条看第一格长文本为什么没过 */
  var NUM = /^[-+−–—(（]?\s*[\d,，.．]+\s*(?:%|pct|倍|元|元\/股|元\/吨)?\s*[)）]?$/i;
  var TXT_MIN = 14;
  var cells = document.querySelectorAll('#mods table td');
  var shown = 0, byReason = {短:0, 数字:0, 中文不足:0, 已标:0, 命中:0};
  for (var i = 0; i < cells.length; i++) {
    var td = cells[i], cls = td.className || '';
    var txt = (td.textContent || '').replace(/\s+/g, ' ').trim();
    if (cls.indexOf('is-num') >= 0) { byReason['已标']++; continue; }
    if (txt.length < TXT_MIN) { byReason['短']++; continue; }
    if (NUM.test(txt)) { byReason['数字']++; continue; }
    var han = txt.match(/[\u4e00-\u9fa5]/g);
    if (!han || han.length < TXT_MIN) { byReason['中文不足']++; continue; }
    byReason['命中']++;
    if (shown < 6) { shown++;
      O.push('  应命中 «' + txt.slice(0,26) + '» len=' + txt.length +
             ' 汉=' + (han?han.length:0) + ' 实际class=«' + cls.slice(0,30) + '»' +
             ' align=' + getComputedStyle(td).textAlign);
    }
  }
  O.push('判据分流: ' + JSON.stringify(byReason));

  /* 复刻 is-num 判据，看它命中多少（对照） */
  var n = 0;
  for (var j = 0; j < cells.length; j++) {
    var t = (cells[j].textContent || '').replace(/\s+/g, ' ').trim();
    if (t && t.length <= 22 && NUM.test(t)) n++;
  }
  O.push('NUM 正则可命中=' + n);

  document.title = '###' + O.join('\n');
}, 6000);
</script>
"""

src = os.environ.get('RPT_SRC', '/tmp/blkpatch/report.html')
raw = open(src, encoding='utf-8', errors='replace').read()
i = raw.rfind('</body>')
html = raw[:i] + PROBE + raw[i:]
tmp = tempfile.mkdtemp(prefix='mt_')
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
       '--window-size=1440,1200', '--virtual-time-budget=14000',
       '--dump-dom', 'http://127.0.0.1:%d/r.html' % PORT]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=200)
m = re.search(r'<title>###(.*?)</title>', r.stdout, re.S)
print(m.group(1).replace('\\n', '\n') if m else '!! 没抓到')
srv.shutdown()
