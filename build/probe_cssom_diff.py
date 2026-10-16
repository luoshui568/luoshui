# -*- coding: utf-8 -*-
"""CSSOM 级精确 diff：dump 浏览器**实际解析到**的全部 CSS 规则，
比对线上与新产物。用来精确回答「到底多少条规则之前没生效」。

用法：python3 build/probe_cssom_diff.py <A.html> <B.html>
"""
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import tempfile
import threading

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'

PROBE = r"""
<script>
setTimeout(function(){
  var out = [];
  for(var i=0;i<document.styleSheets.length;i++){
    var ss = document.styleSheets[i], rules;
    try{ rules = ss.cssRules; }catch(e){ out.push('!CORS'); continue; }
    if(!rules) continue;
    for(var j=0;j<rules.length;j++){
      var r = rules[j];
      if(r.selectorText !== undefined){
        out.push(r.selectorText + '{' + (r.style.cssText||'').replace(/[\r\n\t]+/g,' ') + '}');
      } else if(r.cssText !== undefined){
        out.push('@' + r.cssText.replace(/[\r\n\t]+/g,' ').slice(0, 4000));
      }
    }
  }
  document.title = '###' + JSON.stringify(out);
}, 5000);
</script>
"""


def dump(path, port):
    raw = open(path, encoding='utf-8', errors='replace').read()
    i = raw.rfind('</body>')
    html = raw[:i] + PROBE + raw[i:]
    tmp = tempfile.mkdtemp(prefix='cd_')
    open(os.path.join(tmp, 'r.html'), 'w', encoding='utf-8').write(html)

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=tmp, **kw)

        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cmd = [EDGE, '--headless=new', '--user-data-dir=' + os.path.join(tmp, 'prof'),
           '--no-sandbox', '--no-proxy-server', '--disable-gpu',
           '--window-size=1440,1200', '--virtual-time-budget=11000',
           '--dump-dom', 'http://127.0.0.1:%d/r.html' % port]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=220)
    srv.shutdown()
    m = re.search(r'<title>###(.*?)</title>', r.stdout, re.S)
    if not m:
        raise SystemExit('!! %s 没抓到' % path)
    return json.loads(m.group(1).replace('\\n', '\n'))


def norm(s):
    return re.sub(r'\s+', '', s)


def main():
    A = [norm(x) for x in dump(sys.argv[1], 8867)]
    B = [norm(x) for x in dump(sys.argv[2], 8869)]
    sa, sb = set(A), set(B)
    print('线上实际解析到 %d 条 / 新产物 %d 条' % (len(A), len(B)))
    lost = [x for x in A if x not in sb]
    gain = [x for x in B if x not in sa]
    print('\n★ 线上有、新产物没有（= 我会弄丢的）：%d 条' % len(lost))
    for x in lost[:30]:
        print('   −', x[:150])
    print('\n新产物新增：%d 条' % len(gain))
    for x in gain[:30]:
        print('   +', x[:150])


if __name__ == '__main__':
    main()
