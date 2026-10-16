# -*- coding: utf-8 -*-
"""临时排障：dump 某个卡片直接子元素的 tag/class/computed，用来定位选择器为什么没命中。"""
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
SERVE = '/tmp/dbgmod_serve'
PORT = 9005

DUMP = r"""
setTimeout(function(){
  var out = [];
  try{
    var c = document.getElementById('m__MOD__');
    for(var k = 0; k < c.children.length; k++){
      var e = c.children[k], s = getComputedStyle(e);
      out.push({i:k, tag:e.tagName, cls:e.className, fs:s.fontSize, lh:s.lineHeight,
                color:s.color, bl:s.borderLeftWidth + ' ' + s.borderLeftStyle + ' ' + s.borderLeftColor,
                bg:(s.backgroundImage !== 'none' ? 'IMG' : s.backgroundColor),
                pad:s.padding, mt:s.marginTop, mb:s.marginBottom, fw:s.fontWeight,
                txt:(e.textContent || '').replace(/\s+/g, ' ').slice(0, 34)});
    }
  }catch(err){ out = [{err: '' + err}]; }
  var pre = document.createElement('pre'); pre.id = 'ZD';
  pre.textContent = 'ZS' + JSON.stringify(out) + 'ZE';
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
    code = a[a.index('--code') + 1] if '--code' in a else '002408'
    mod = a[a.index('--mod') + 1] if '--mod' in a else '5'
    src = os.environ.get('REPORT_SRC', os.path.join(REPO, 'deploy', 'report.html'))
    html = open(src, encoding='utf-8', errors='replace').read()
    i = html.rfind('</body>')
    os.makedirs(SERVE, exist_ok=True)
    open(os.path.join(SERVE, 'report.html'), 'w', encoding='utf-8').write(
        html[:i] + '<script>' + DUMP.replace('__MOD__', mod) + '<' + '/script>' + html[i:])
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(('127.0.0.1', PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    r = subprocess.run([EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--no-proxy-server',
                        '--user-data-dir=/tmp/edgeprof_dbg', '--window-size=1400,900',
                        '--virtual-time-budget=24000', '--dump-dom',
                        'http://localhost:%d/report.html?code=%s' % (PORT, code)],
                       capture_output=True, timeout=300)
    srv.shutdown()
    m = re.search(r'ZS(\[.*?\])ZE', r.stdout.decode('utf-8', 'replace'), re.S)
    if not m:
        print('拿不到 dump')
        return
    for rec in json.loads(m.group(1)):
        print('%-3s %-4s %-12s fs=%-7s lh=%-9s color=%-18s bl=%-28s bg=%-22s pad=%-18s m=%s/%s fw=%s | %s'
              % (rec.get('i'), rec.get('tag'), (rec.get('cls') or '')[:12], rec.get('fs'), rec.get('lh'),
                 rec.get('color'), rec.get('bl'), (rec.get('bg') or '')[:22], (rec.get('pad') or '')[:18],
                 rec.get('mt'), rec.get('mb'), rec.get('fw'), rec.get('txt')))


if __name__ == '__main__':
    main()
