# -*- coding: utf-8 -*-
"""体检「负值柱圆角朝向」：dump 每根柱子实际生成的 rect.shape.r，判断
负值柱的圆角是不是落在「柱尖」那头（r=[0,0,7,7]），正柱有没有被误伤。

用法：
    REPORT_SRC=/tmp/livepatch2/report.html python3 build/probe_negr.py 002408 603977
不带 REPORT_SRC 时读 deploy/report.html。

判据：
  · 竖向柱（该系列 yAxis 是 value）值 < 0 ⇒ 期望 r=[0,0,7,7]；值 ≥ 0 ⇒ [7,7,0,0]
  · 横向条形图（yAxis 是 category）⇒ 按设计不翻，期望 [7,7,0,0]
  · 注意：shape.height 在动画未跑完时读出来是 0，**不能用长宽比判方向**，只能看轴类型。
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
DEPLOY = os.path.join(REPO, 'deploy')
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
PORT = 8979

_DUMP = """
setTimeout(function(){
  var out = {};
  try{
    for(var k in St.inst){
      var inst = St.inst[k];
      var o = inst.getOption();
      var sers = o.series || [];
      sers = Array.isArray(sers) ? sers : [sers];
      function types(ax){ ax = ax ? (Array.isArray(ax) ? ax : [ax]) : [];
        return ax.map(function(a){ return a && a.type ? a.type : 'value'; }); }
      var dl = inst.getZr().storage.getDisplayList();
      var bars = [];
      for(var i = 0; i < dl.length; i++){
        var el = dl[i], sh = el.shape;
        if(!sh || sh.width === undefined || sh.height === undefined) continue;
        var eck = null;
        for(var kk in el){ if(kk.indexOf('__ec_inner') === 0){ eck = el[kk]; break; } }
        if(!eck || eck.dataIndex === undefined || eck.seriesIndex === undefined) continue;
        var s = sers[eck.seriesIndex] || {};
        if(String(s.type) !== 'bar') continue;
        var dv = (s.data || [])[eck.dataIndex];
        var v = (dv && typeof dv === 'object') ? dv.value : dv;
        bars.push({si: eck.seriesIndex, di: eck.dataIndex, v: v,
                   r: sh.r === undefined ? null : sh.r});
      }
      out[k] = {xt: types(o.xAxis), yt: types(o.yAxis),
                series: sers.map(function(s){ return {n: s.name, t: s.type,
                                                     yi: s.yAxisIndex || 0}; }),
                bars: bars};
    }
  }catch(err){ out.__err = '' + err; }
  var pre = document.createElement('pre');
  pre.id = 'ZDUMP';
  pre.textContent = 'ZDUMP_START' + JSON.stringify(out) + 'ZDUMP_END';
  document.body.appendChild(pre);
}, 3600);
"""


def build_injected(html):
    inject = '<script>' + _DUMP + '<' + '/script>'
    i = html.rfind('</body>')
    return html[:i] + inject + html[i:]


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DEPLOY, **kw)

    def do_GET(self):
        if self.path.split('?')[0].endswith('report.html'):
            src = os.environ.get('REPORT_SRC', os.path.join(DEPLOY, 'report.html'))
            with open(src, 'rb') as f:
                html = f.read().decode('utf-8', 'replace')
            body = build_injected(html).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def log_message(self, *a):
        pass


def dump(code, n=1):
    url = 'http://localhost:%d/report.html?code=%s' % (PORT, code)
    cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
           '--no-proxy-server', '--user-data-dir=/tmp/edgeprof_nb%d' % n,
           '--window-size=1400,900', '--virtual-time-budget=26000',
           '--dump-dom', url]
    r = subprocess.run(cmd, capture_output=True, timeout=240)
    dom = r.stdout.decode('utf-8', 'replace')
    ms = re.findall(r'ZDUMP_START(\{.*?\})ZDUMP_END', dom, re.S)
    return ms[-1] if ms else None


def norm(r):
    if r is None:
        return '—'
    if isinstance(r, list):
        return '[' + ','.join(str(x) for x in r) + ']'
    return str(r)


def main():
    codes = sys.argv[1:] or ['002408']
    src = os.environ.get('REPORT_SRC', os.path.join(DEPLOY, 'report.html'))
    print('源文件:', src)
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(('127.0.0.1', PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    bad = 0
    nchart = 0
    for n, code in enumerate(codes):
        raw = dump(code, n % 4)
        print('=' * 78)
        print('研报', code)
        if not raw:
            print('  ✗ 没拿到 ZDUMP')
            bad += 1
            continue
        data = json.loads(raw)
        if data.get('__err'):
            print('  ✗ JS 报错', data['__err'])
            bad += 1
            continue
        for k in sorted(data):
            rec = data[k]
            bars = rec.get('bars') or []
            if not any(isinstance(b['v'], (int, float)) and b['v'] < 0 for b in bars):
                continue
            nchart += 1
            print('  ■ %s   xAxis=[%s] yAxis=[%s]'
                  % (k, ','.join(rec['xt']), ','.join(rec['yt'])))
            byname = {}
            for b in bars:
                byname.setdefault(b['si'], []).append(b)
            for si in sorted(byname):
                sdef = rec['series'][si] or {}
                yi = sdef.get('yi') or 0
                ytyp = (rec['yt'][yi] if yi < len(rec['yt']) else 'value')
                horiz = (ytyp != 'value')
                rows = sorted(byname[si], key=lambda x: x['di'])
                print('    %-14s%s' % (str(sdef.get('n'))[:14],
                                       '  [横向]' if horiz else ''))
                print('      %s' % '  '.join(
                    '%s%s%s' % (('%.4g' % b['v']) if isinstance(b['v'], (int, float)) else '?',
                                '↓' if (isinstance(b['v'], (int, float)) and b['v'] < 0) else '',
                                norm(b['r'])) for b in rows))
                for b in rows:
                    if not (isinstance(b['v'], (int, float)) and b['v'] < 0):
                        continue
                    r = b['r']
                    if horiz:      # 横向条形图：按设计保持原样
                        if r != [7, 7, 0, 0]:
                            print('      · 第 %d 项(值 %s) 横向图圆角 %s（非默认，留意）'
                                  % (b['di'], b['v'], norm(r)))
                        continue
                    if not (isinstance(r, list) and r[:2] == [0, 0] and r[2:4] == [7, 7]):
                        bad += 1
                        print('      ✗ 第 %d 项(值 %s) 圆角 %s 不在柱尖那头'
                              % (b['di'], b['v'], norm(r)))
    srv.shutdown()
    print()
    print('含负值柱的图 %d 张，不合格项 %d' % (nchart, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
