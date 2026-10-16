# -*- coding: utf-8 -*-
"""逐元素计算样式对比：把线上字节与候选产物分别渲染，比对同一批元素的
computed style。用于回答「我这份产物除了预期修复，有没有悄悄改变别的观感」。

判据：除白名单里的预期变化外，差异数应为 0。
用法：python3 build/probe_style_diff.py <A.html> <B.html>
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
<style>*{animation:none !important;transition:none !important}</style>
<script>
setTimeout(function(){
  /* 采一批有代表性的元素，记录计算样式指纹 */
  var out = {};
  var sels = [
    '#mods .card', '#mods .card h2', '#mods .card h3', '#mods .card p',
    '#mods .card table', '#mods .card table th', '#mods .card table td',
    '#mods .card table tbody td:first-child',
    '#mods .logic', '#mods .logic .lt', '#mods .logic .lv',
    '#mods .hist', '#mods .hist .h-title', '#mods .hist .h-card',
    '#mods .tc-item', '#mods .rpt-toolbar', '#mods .rpt-toolbar button',
    '#mods .verdict', '#mods .score-hero', '#mods .sh3-top',
    '#mods .iflow', '#mods .val-hero', '#mods .essence', '#mods .risk-item'
  ];
  var props = ['display','color','backgroundColor','backgroundImage','textAlign',
               'fontSize','fontWeight','lineHeight','borderRadius','borderLeftColor',
               'gridTemplateColumns','padding','margin','overflowWrap','wordBreak'];
  sels.forEach(function(s){
    var el = document.querySelector(s);
    if(!el){ out[s] = null; return; }
    var cs = getComputedStyle(el), rec = {};
    props.forEach(function(p){ rec[p] = cs[p]; });
    out[s] = rec;
  });
  /* 表格逐格对齐统计 */
  var al = {};
  document.querySelectorAll('#mods table td').forEach(function(td){
    var a = getComputedStyle(td).textAlign;
    al[a] = (al[a]||0)+1;
  });
  out['__td-align'] = al;
  /* 元素数量指纹 */
  out['__counts'] = {
    cards: document.querySelectorAll('#mods .card').length,
    table: document.querySelectorAll('#mods table').length,
    td: document.querySelectorAll('#mods table td').length,
    toolbar: document.querySelectorAll('#mods .rpt-toolbar').length,
    logic: document.querySelectorAll('#mods .logic').length,
    canvas: document.querySelectorAll('#mods canvas').length
  };
  document.title = '###' + JSON.stringify(out);
}, 5500);
</script>
"""


def render(path, port):
    raw = open(path, encoding='utf-8', errors='replace').read()
    i = raw.rfind('</body>')
    html = raw[:i] + PROBE + raw[i:]
    tmp = tempfile.mkdtemp(prefix='sd_')
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
           '--window-size=1440,1200', '--virtual-time-budget=13000',
           '--dump-dom', 'http://127.0.0.1:%d/r.html' % port]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=220)
    srv.shutdown()
    m = re.search(r'<title>###(.*?)</title>', r.stdout, re.S)
    if not m:
        raise SystemExit('!! %s 没抓到 title' % path)
    return json.loads(m.group(1).replace('\\n', '\n'))


def main():
    a, b = sys.argv[1], sys.argv[2]
    A = render(a, 8861)
    B = render(b, 8863)
    diffs = []
    for k in sorted(set(A) | set(B)):
        va, vb = A.get(k), B.get(k)
        if va == vb:
            continue
        if isinstance(va, dict) and isinstance(vb, dict):
            for p in sorted(set(va) | set(vb)):
                if va.get(p) != vb.get(p):
                    diffs.append((k, p, va.get(p), vb.get(p)))
        else:
            diffs.append((k, '(整块)', va, vb))
    print('=== 逐元素计算样式对比 ===')
    print('A =', a)
    print('B =', b)
    print('差异 %d 处' % len(diffs))
    for k, p, va, vb in diffs[:40]:
        print('  %-34s %-18s A=%-28s B=%s' % (k, p, str(va)[:28], str(vb)[:28]))


if __name__ == '__main__':
    main()
