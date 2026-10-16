# -*- coding: utf-8 -*-
"""体检「双轴 0 刻度对齐」：把渲染后每个图表的 y 轴 extent / interval / 0 刻度占比 dump 出来。

用法：python3 /tmp/probe_zero.py 600392 603977 600456 000731 000830
"""
import http.server
import os
import re
import socketserver
import subprocess
import sys
import threading

REPO = '/Users/luoshui/WorkBuddy/2026-10-10-22-59-27/luoshui'
DEPLOY = os.path.join(REPO, 'deploy')
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
PORT = 8977

_DUMP = """
setTimeout(function(){
  var out = {__title: document.title, __url: location.search, __charts: {}};
  try{
    for(var k in St.charts){
      var rec = St.charts[k];
      out.__charts[k] = (rec && rec.opt && rec.opt.series ? rec.opt.series : []).map(function(s){
        return {n: s.name, t: s.type, d: (s.data || []).slice(0, 6)};
      });
    }
  }catch(err){ out.__charts = 'ERR ' + err; }
  var axes = {};
  try{
    for(var kk in St.inst){
      var inst = St.inst[kk];
      var ax = [];
      try{
        var opt = inst.getOption();
        var ya = Array.isArray(opt.yAxis) ? opt.yAxis : [opt.yAxis];
        for(var i = 0; i < ya.length; i++){
          var e = null, iv = null;
          try{
            var sc = inst.getModel().getComponent('yAxis', i).axis.scale;
            e = sc.getExtent(); iv = sc.getInterval();
          }catch(err){}
          var o = ya[i] || {};
          ax.push({type:o.type||'value', min:o.min===undefined?null:o.min,
                   max:o.max===undefined?null:o.max,
                   interval:o.interval===undefined?null:o.interval,
                   ext:e, scItv:iv});
        }
      }catch(err){ axes[kk] = {err: ''+err}; continue; }
      axes[kk] = ax;
    }
  }catch(err){ axes['__err'] = ''+err; }
  out.__axes = axes;
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
            with open(os.environ.get('REPORT_SRC', os.path.join(DEPLOY, 'report.html')), 'rb') as f:
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
           '--no-proxy-server', '--user-data-dir=/tmp/edgeprof_zero%d' % n,
           '--window-size=1400,900', '--virtual-time-budget=26000',
           '--dump-dom', url]
    r = subprocess.run(cmd, capture_output=True, timeout=240)
    dom = r.stdout.decode('utf-8', 'replace')
    ms = re.findall(r'ZDUMP_START(\{.*?\})ZDUMP_END', dom, re.S)
    return ms[-1] if ms else None


def main():
    codes = sys.argv[1:] or ['600392']
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(('127.0.0.1', PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    import json
    for n, code in enumerate(codes):
        raw = dump(code, n % 4)
        print('=' * 72)
        print('研报', code)
        if not raw:
            print('  ✗ 没拿到 ZDUMP（页面没渲染完 / 抓取失败）')
            continue
        data = json.loads(raw)
        print('  title=%s  url=%s' % (data.get('__title'), data.get('__url')))
        axes_all = data.get('__axes') or {}
        chs = data.get('__charts') or {}
        for k in sorted(axes_all):
            axes = axes_all[k]
            if isinstance(axes, dict):
                print('  %-22s ERR %s' % (k, axes.get('err')))
                continue
            zfs = []
            seg = []
            for a in axes:
                e = a['ext']
                if e and (e[1] - e[0]) > 0:
                    zf = (0 - e[0]) / (e[1] - e[0])
                    zfs.append(zf)
                    seg.append('ext[%s..%s] itv=%s scItv=%s 0@%.4f'
                               % (e[0], e[1], a['interval'], a.get('scItv'), zf))
                else:
                    zfs.append(None)
                    seg.append('ext=? itv=%s min=%s' % (a['interval'], a['min']))
            flag = ''
            if len(zfs) > 1 and all(z is not None for z in zfs):
                if max(zfs) - min(zfs) < 1e-6:
                    flag = '✓ 0轴对齐 %.4f' % zfs[0] if zfs[0] > 0 else '· 无双轴负值(未接管)'
                else:
                    flag = '✗ 未对齐 %s' % ['%.4f' % z for z in zfs]
            print('  %-22s %s | %s' % (k, ' ‖ '.join(seg), flag))
        print('  ---- 含负数系列的图表（库里的原始数据）----')
        for k in sorted(chs):
            sers = chs[k]
            if not isinstance(sers, list):
                continue
            neg = False
            for s in sers:
                for v in (s.get('d') or []):
                    if isinstance(v, (int, float)) and v < 0:
                        neg = True
            if neg:
                print('  %-22s %s' % (k, [(s['n'], s['t'], s['d']) for s in sers]))
    srv.shutdown()


if __name__ == '__main__':
    main()
