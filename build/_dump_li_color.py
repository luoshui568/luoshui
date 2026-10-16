# -*- coding: utf-8 -*-
"""一次性排障：dump 某个研报每张卡片里 ul/li/li b/p/b/h3/h4 的 computed 颜色与字重。

用法：python3 build/_dump_li_color.py 002408            # 用 deploy/report.html
      REPORT_SRC=/tmp/live.html python3 build/_dump_li_color.py 002408
输出里只列「含 ul 或有 b」的卡片，避免刷屏。
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
SERVE = '/tmp/licolor_serve'
PORT = 9011

DUMP = r"""
setTimeout(function(){
  var out = [];
  try{
    var cards = document.querySelectorAll('#mods > .card');
    for(var i = 0; i < cards.length; i++){
      var c = cards[i];
      var rec = {no: c.id, h3: null, h4: null, p: null, b_in_p: null, ul: null, li: null, b_in_li: null, strong_in_li: null, card: null};
      function cs(e){
        if(!e) return null;
        var s = getComputedStyle(e);
        return {color: s.color, fw: s.fontWeight, fs: s.fontSize, lh: s.lineHeight, tag: e.tagName};
      }
      rec.card = cs(c);
      rec.h3 = cs(c.querySelector(':scope > h3'));
      rec.h4 = cs(c.querySelector(':scope > h4'));
      var p = c.querySelector(':scope > p:not(.src):not(.muted)');
      rec.p = cs(p);
      rec.b_in_p = cs(p ? p.querySelector('b,strong') : null);
      var ul = c.querySelector(':scope > ul, :scope > ol');
      rec.ul = cs(ul);
      var li = ul ? ul.querySelector(':scope > li') : null;
      rec.li = cs(li);
      rec.b_in_li = cs(li ? li.querySelector('b') : null);
      rec.strong_in_li = cs(li ? li.querySelector('strong') : null);
      rec.hasUL = !!ul;
      rec.liN = ul ? ul.children.length : 0;
      out.push(rec);
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
                            '--user-data-dir=/tmp/edgeprof_lc', '--window-size=1400,1000',
                            '--virtual-time-budget=26000', '--dump-dom',
                            'http://localhost:%d/report.html?code=%s' % (PORT, code)],
                           capture_output=True, timeout=300)
        dom = r.stdout.decode('utf-8', 'replace')
        m = re.search(r'ZS(\[.*?\])ZE', dom, re.S)
        if not m:
            print('%-8s 拿不到 dump' % code)
            continue
        data = json.loads(m.group(1))
        print('=== %s ===' % code)

        def fmt(x):
            if not x:
                return '—'
            return '%s %s/%s lh%s' % (x['color'], x['fw'], x['fs'], x['lh'])
        for rec in data:
            if 'err' in rec:
                print('  ERR', rec['err']); continue
            if not rec.get('hasUL') and not rec.get('b_in_p'):
                continue
            print('  [%s]%s card=%s' % (rec['no'], ' 含ul(%d li)' % rec['liN'] if rec['hasUL'] else '', fmt(rec['card'])))
            for k in ('h3', 'h4', 'p', 'b_in_p', 'ul', 'li', 'b_in_li', 'strong_in_li'):
                if rec.get(k):
                    print('      %-13s %s' % (k, fmt(rec[k])))
    srv.shutdown()


if __name__ == '__main__':
    main()
