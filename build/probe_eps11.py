# -*- coding: utf-8 -*-
"""验收探针：12 份研报的 m29「EPS 与股价历史」是否真的渲染出来 + 0 轴是否像素级对齐
+ m28 的「收盘价 + 成交额」图（chartPrice2）是否已消失。

判据（逐份）：
  m29slot=1          m29 卡片里 chart_eps 槽存在
  epsinst=1          ECharts 实例挂在槽上（真的画出来了，不是空占位）
  canvas>=1          有 canvas 位图
  chartmiss=0        渲染器没标「图表数据缺失」
  p2slot=0           全页已无 chartPrice2 槽
  y0==y1             两轴「0 刻度」的像素 y 完全相同（0 轴两边对齐）
  y0frac==y1frac     两轴 0 位置比例相同（opt 层口径）
  epsn / pxn         EPS 柱点数 / 价格折线点数
  lastpx             价格末点（应＝不复权最新收盘价）

用法：python3 build/probe_eps11.py 000731 600459 ...   （不带参数＝全部 12 份）
"""
import http.server
import io
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
SITE = 'https://liuchaowang.cn/report.html'

RAW_LAST = json.load(io.open(os.path.join(HERE, 'seed', '_raw_last.json'),
                            encoding='utf-8'))['raw_last']
RAW_LAST['600456'] = 23.48      # 样板图口径（build/_eps_opt_600456.py 注释）

PROBE = r"""
<style>*{animation:none !important;transition:none !important}</style>
<script>
setTimeout(function(){
  var o = [];
  var slot = document.querySelector('#mods [data-chart="chart_eps"]');
  o.push('m29slot=' + (slot ? 1 : 0));
  o.push('p2slot=' + document.querySelectorAll('#mods [data-chart="chartPrice2"]').length);
  o.push('card29=' + (slot ? (function(){ var n=slot;
        while(n && n.parentElement && n.parentElement.id!=='mods') n=n.parentElement;
        return n ? (n.className||'?') : '?'; })() : 'none'));
  o.push('canvas=' + document.querySelectorAll('#mods canvas').length);
  o.push('chartmiss=' + document.querySelectorAll('#mods .rpt-chartmiss').length);
  o.push('cards=' + document.querySelectorAll('#mods .card').length);
  var hasE = (typeof echarts !== 'undefined');
  o.push('echarts=' + (hasE ? 1 : 0));
  var inst = null;
  if (hasE && slot) { try { inst = echarts.getInstanceByDom(slot); } catch(e){} }
  o.push('epsinst=' + (inst ? 1 : 0));
  if (inst){
    var op = inst.getOption();
    var a0 = op.yAxis[0], a1 = op.yAxis[1];
    o.push('ax0=' + a0.min + ',' + a0.max + ',' + a0.interval);
    o.push('ax1=' + a1.min + ',' + a1.max + ',' + a1.interval);
    var f0 = (0 - a0.min) / (a0.max - a0.min);
    var f1 = (0 - a1.min) / (a1.max - a1.min);
    o.push('y0frac=' + f0.toFixed(6));
    o.push('y1frac=' + f1.toFixed(6));
    try {
      var p0 = inst.convertToPixel({yAxisIndex: 0}, 0);
      var p1 = inst.convertToPixel({yAxisIndex: 1}, 0);
      o.push('y0px=' + (p0 === null ? 'null' : Math.round(p0 * 100) / 100));
      o.push('y1px=' + (p1 === null ? 'null' : Math.round(p1 * 100) / 100));
      o.push('y0eqy1=' + ((p0 !== null && p1 !== null && Math.abs(p0 - p1) < 0.6) ? 1 : 0));
    } catch(e){ o.push('y0eqy1=ERR'); }
    var s0 = op.series[0], s1 = op.series[1];
    o.push('epsn=' + s0.data.length);
    o.push('pxn=' + s1.data.length);
    o.push('z_bar=' + (s0.z||'-') + ' z_line=' + (s1.z||'-'));
    o.push('area=' + (s1.areaStyle && s1.areaStyle.color ?
        JSON.stringify(s1.areaStyle.color).slice(0,200) : 'none'));
    o.push('lastpx=' + JSON.stringify(s1.data[s1.data.length-1]));
    o.push('firstpx=' + JSON.stringify(s1.data[0]));
    o.push('lasteps=' + JSON.stringify(s0.data[s0.data.length-1]));
  }
  var d = document.createElement('div');
  d.id='probeout'; d.textContent = o.join('\n');
  document.body.appendChild(d);
  document.title='PROBE_DONE';
}, 9000);
</script>
</body>"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


class Srv(socketserver.TCPServer):
    # ★ allow_reuse_address 是**类属性**，在 server_bind 里读 ⇒ 必须在 __init__ 前设好，
    #   构造之后再赋值没用（会撞 Errno 48 Address already in use）。
    allow_reuse_address = True


def one(code, port):
    raw = urllib.request.urlopen(SITE + '?code=' + code, timeout=90).read().decode('utf-8', 'replace')
    page = raw.replace('<head>', '<head><base href="https://liuchaowang.cn/">', 1)
    k = page.rfind('</body>')
    page = page[:k] + PROBE + page[k + len('</body>'):]
    tmp = tempfile.mkdtemp(prefix='eps11_')
    io.open(os.path.join(tmp, 'report.html'), 'w', encoding='utf-8').write(page)
    httpd = Srv(('127.0.0.1', port), lambda *a, **kw: Quiet(*a, directory=tmp, **kw))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    cmd = [EDGE, '--headless=new', '--user-data-dir=' + os.path.join(tmp, 'prof'),
           '--no-sandbox', '--no-proxy-server', '--disable-gpu', '--window-size=1600,1200',
           '--virtual-time-budget=22000', '--dump-dom',
           'http://127.0.0.1:%d/report.html?code=%s' % (port, code)]
    p = subprocess.run(cmd, capture_output=True, timeout=240)
    dom = p.stdout.decode('utf-8', 'replace')
    httpd.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    m = re.search(r'<div id="probeout">(.*?)</div>', dom, re.S)
    if not m:
        return None
    import html as H
    txt = H.unescape(m.group(1)).strip()
    return dict(l.split('=', 1) for l in txt.split('\n') if '=' in l)


def main():
    codes = [a for a in sys.argv[1:] if not a.startswith('--')] or (
        list(RAW_LAST.keys()) if False else
        ['000731', '000762', '000830', '002237', '002408', '600392',
         '600459', '601118', '601958', '603599', '603977'])
    print('%-8s %-7s %-7s %-6s %-6s %-6s %-6s %-25s %-9s %s'
          % ('code', 'm29sl', 'epsinst', 'p2sl', 'y0p', 'y1p', '对齐', '轴[EPS] / [价格]', '末价', '判'))
    bad = []
    for i, code in enumerate(codes):
        r = one(code, 8800 + i)
        if not r:
            print('%-8s  ✗ 探针未跑出来' % code)
            bad.append(code)
            continue
        ok = (r.get('m29slot') == '1' and r.get('epsinst') == '1'
              and r.get('p2slot') == '0' and r.get('chartmiss') == '0'
              and r.get('y0eqy1') == '1' and r.get('y0frac') == r.get('y1frac'))
        last = json.loads(r.get('lastpx', '[]'))
        want = RAW_LAST.get(code)
        px_ok = (len(last) == 2 and want is not None and abs(last[1] - want) < 0.02)
        print('%-8s %-7s %-7s %-6s %-6s %-6s %-6s %-25s %-9s %s'
              % (code, r.get('m29slot'), r.get('epsinst'), r.get('p2slot'),
                 r.get('y0px'), r.get('y1px'), r.get('y0eqy1'),
                 '%s / %s' % (r.get('ax0'), r.get('ax1')),
                 '%s%s' % (last[1] if len(last) == 2 else '?', '' if px_ok else '✗'),
                 '✓' if (ok and px_ok) else '⚠'))
        if not (ok and px_ok):
            bad.append(code)
            for k in sorted(r):
                if k in ('area', 'firstpx', 'lasteps', 'epsn', 'pxn', 'z_bar', 'z_line', 'card29'):
                    print('        %s=%s' % (k, r[k]))
    print('\n%s' % ('全部通过 ✓' if not bad else '未通过：%s' % bad))


if __name__ == '__main__':
    main()
