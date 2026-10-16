#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build/shot_logic_fold.py —— 给「解读块就地展开/收起」出一对验收截图。

只显示目标模块卡片（其余 `#mods > .card` 全部 display:none），再滚到那一块，
所以画面干净、一眼能看出折叠态与展开态的差别。

用法：
  python3 build/shot_logic_fold.py <code> <mod> [k] [outdir]
  RPT_SRC=/tmp/live.html python3 build/shot_logic_fold.py 002408 12 0

产物（默认 build/shots/）：
  13_解读块_折叠态_<code>_m<mod>.png
  14_解读块_展开态_<code>_m<mod>.png
"""
import io
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.environ.get('RPT_SRC') or os.path.join(ROOT, 'deploy', 'report.html')
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
WIN = os.environ.get('WIN') or '1400,940'

INJECT = r"""
<script>
(function(){
  var MOD="__MOD__", K=__K__, CLK=__CLICK__;
  /* ⚠️ 两个坑（都踩过，两次出 5988 字节纯白图）：
     ① 这一页是 SPA，库数据要现拉。动手太早 = 滚到还没长高的空白处。
     ② **必须用 MutationObserver 等待，不能用 setTimeout 轮询** ——
        `--headless=new --virtual-time-budget` 的虚拟时钟会被 setTimeout 飞速耗尽，
        不等网络回来就把 20 秒"走完"，截图时 #mods 还是空的 ⇒ 全白。
        MutationObserver 由 DOM 变化驱动，不吃虚拟时间，网络 pending 时虚拟时钟会暂停。
     ③ 不用 scrollTo（滚动在虚拟时间下不可靠），直接把目标卡片以外的东西全隐藏，
        卡片自然升到页首。 */
  function isolate(card){
    var el = card;
    while(el && el.parentNode && el.parentNode !== document.documentElement){
      var p = el.parentNode, kids = p.children;
      for(var i = 0; i < kids.length; i++) if(kids[i] !== el) kids[i].style.display = 'none';
      if(p === document.body) break;
      el = p;
    }
  }
  function act(){
    var card = document.getElementById('m' + MOD);
    if(!card) return;
    var st = document.createElement('style');
    st.textContent = '*{transition:none!important;animation:none!important}';
    document.head.appendChild(st);
    var bs = card.querySelectorAll('.logic');
    if(!bs.length) return;
    var b = bs[K] || bs[0];
    if(CLK) b.click();
    isolate(card);
    window.scrollTo(0, 0);
  }
  var mo = new MutationObserver(function(){
    var card = document.getElementById('m' + MOD);
    if(card && card.querySelectorAll('.logic').length){ mo.disconnect(); act(); }
  });
  mo.observe(document.documentElement, {childList: true, subtree: true});
  /* 兜底：注入时 DOM 可能已经就绪（此时 MutationObserver 不会再有事件） */
  var c0 = document.getElementById('m' + MOD);
  if(c0 && c0.querySelectorAll('.logic').length){ act(); }
})();
</script>
"""


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        kw['directory'] = kw.pop('directory', '/tmp')
        super().__init__(*a, **kw)

    def log_message(self, *a):
        pass


def inject(html, js):
    i = html.rfind('</body>')
    return html[:i] + js + html[i:] if i > 0 else html + js


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def shoot(code, mod, k, click, out, tmp, port, html):
    js = INJECT.replace('__MOD__', str(mod)).replace('__K__', str(k)) \
              .replace('__CLICK__', 'true' if click else 'false')
    io.open(os.path.join(tmp, 'report.html'), 'w', encoding='utf-8').write(inject(html, js))
    url = 'http://127.0.0.1:%d/report.html?code=%s' % (port, code)
    if os.path.exists(out):
        os.remove(out)

    subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                    '--hide-scrollbars', '--window-size=' + WIN,
                    '--virtual-time-budget=20000', '--screenshot=' + out, url],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return os.path.exists(out) and os.path.getsize(out) > 0


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    code, mod = sys.argv[1], sys.argv[2]
    k = sys.argv[3] if len(sys.argv) > 3 else '0'
    outdir = sys.argv[4] if len(sys.argv) > 4 else os.path.join(ROOT, 'build', 'shots')
    os.makedirs(outdir, exist_ok=True)

    html = io.open(SRC, encoding='utf-8', errors='replace').read()
    tmp = tempfile.mkdtemp(prefix='shotlogic_')
    port = free_port()
    srv = HTTPServer(('127.0.0.1', port), lambda *a, **kw: H(*a, directory=tmp, **kw))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.3)
    try:
        pair = [('13_解读块_折叠态', False), ('14_解读块_展开态', True)]
        for tag, click in pair:
            out = os.path.join(outdir, '%s_%s_m%s.png' % (tag, code, mod))
            ok = shoot(code, mod, k, click, out, tmp, port, html)
            print('%s %s' % ('✓' if ok else '✗', out))
    finally:
        srv.shutdown()
    print('src = %s' % SRC)
    return 0


if __name__ == '__main__':
    sys.exit(main())
