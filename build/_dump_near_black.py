# -*- coding: utf-8 -*-
"""把「卡片内、渲染成近黑 #211f22」的文字节点按容器路径归类，看还有哪些正文类容器没被覆盖。

用法：python3 build/_dump_near_black.py 002408
      REPORT_SRC=/tmp/live.html python3 build/_dump_near_black.py 002408 600456
"""
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading

REPO = '/Users/luoshui/WorkBuddy/2026-10-10-22-59-27/luoshui'
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
SERVE = '/tmp/nearblack_serve'
PORT = 9014
NEAR_BLACK = ('rgb(33, 31, 34)', 'rgb(35, 35, 38)', 'rgb(33, 32, 34)')

DUMP = r"""
setTimeout(function(){
  var m = {};
  try{
    var all = document.querySelectorAll('#mods .card *');
    var NB = ['rgb(33, 31, 34)', 'rgb(35, 35, 38)'];
    function path(e){
      var p = [], n = e;
      while(n && n.nodeType === 1 && p.length < 4){
        var cls = (n.className && typeof n.className === 'string')
                  ? '.' + n.className.trim().split(/\s+/).join('.') : '';
        p.unshift(n.tagName.toLowerCase() + cls);
        n = n.parentElement;
      }
      return p.join(' > ');
    }
    for(var i = 0; i < all.length; i++){
      var e = all[i];
      var own = '';
      for(var j = 0; j < e.childNodes.length; j++){
        var nd = e.childNodes[j];
        if(nd.nodeType === 3 && nd.nodeValue.trim().length > 1) own += nd.nodeValue.trim();
      }
      if(!own) continue;
      var s = getComputedStyle(e);
      if(NB.indexOf(s.color) < 0) continue;
      var k = path(e) + '  ‖' + s.fontWeight;
      if(!m[k]) m[k] = {n:0, sample:''};
      m[k].n++;
      if(!m[k].sample) m[k].sample = own.slice(0, 30);
    }
  }catch(err){ m.__err = '' + err; }
  var pre = document.createElement('pre'); pre.id = 'ZD';
  pre.textContent = 'ZS' + JSON.stringify(m) + 'ZE';
  document.body.appendChild(pre);
}, 4200);
"""


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SERVE, **kw)

    def log_message(self, *a):
        pass


def main():
    a = sys.argv[1:]
    codes = [x for x in a if not x.startswith('--')]
    src = os.environ.get('REPORT_SRC', os.path.join(REPO, 'deploy', 'report.html'))
    html = open(src, encoding='utf-8', errors='replace').read()
    i = html.rfind('</body>')
    os.makedirs(SERVE, exist_ok=True)
    open(os.path.join(SERVE, 'report.html'), 'w', encoding='utf-8').write(
        html[:i] + '<script>' + DUMP + '<' + '/script>' + html[i:])

    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(('127.0.0.1', PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    for code in codes:
        r = subprocess.run([EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--no-proxy-server',
                            '--user-data-dir=/tmp/edgeprof_nb', '--window-size=1400,1000',
                            '--virtual-time-budget=26000', '--dump-dom',
                            'http://localhost:%d/report.html?code=%s' % (PORT, code)],
                           capture_output=True, timeout=300)
        dom = r.stdout.decode('utf-8', 'replace')
        m = re.search(r'ZS(\{.*?\})ZE', dom, re.S)
        if not m:
            print('%-8s 拿不到 dump' % code); continue
        data = json.loads(m.group(1))
        print('=== %s ===' % code)
        rows = sorted(data.items(), key=lambda kv: -kv[1]['n'])
        for k, v in rows[:40]:
            pth, fw = k.split('  ‖')
            print('  %5d  w%s  %-58s  %s' % (v['n'], fw, pth[:58], v['sample']))
    srv.shutdown()


if __name__ == '__main__':
    main()
