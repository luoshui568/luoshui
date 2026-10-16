# -*- coding: utf-8 -*-
"""「导出宽表 → 上传形式」功能截图。
   只读云端（localhost 在网关白名单内），不往 wb_c100_series 写任何东西。
"""
import functools
import http.server
import io
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC_PAGE = os.path.join(ROOT, 'deliver', '大宗商品日线对比图-2005-2026.html')
OUT = os.path.join(ROOT, 'deliver')
SITE = os.path.join(HERE, '_shot4_site')
XLSX_SRC = os.path.join(HERE, '_export_meta.json')
PORT = 8810
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
XLSX_NAME = '_builtin_wide.xlsx'

HELPERS = r'''
<script>
(function(){
  function waitFor(fn, max, label){
    var n = 0;
    return new Promise(function(res, rej){
      (function tick(){
        var v = null;
        try{ v = fn(); }catch(e){ return rej(e); }
        if(v) return res(v);
        if(++n > max) return rej(new Error('timeout ' + label));
        requestAnimationFrame(tick);
      })();
    });
  }
  /* 只读截图：把云端关掉，绝不写 wb_c100_series */
  window.__T = {
    waitFor: waitFor,
    cloud: function(){ return waitFor(function(){ return CLOUD_STATE !== 'wait'; }, 40000, 'cloud'); },
    wideFile: function(){
      return fetch('__XLSX__').then(function(r){ return r.arrayBuffer(); })
        .then(function(ab){ return new File([ab], '大宗商品日线-31品种-宽表.xlsx'); });
    }
  };
})();
</script>
'''.replace('__XLSX__', XLSX_NAME)

S_UP = r'''
<script>
(async function(){
  try{
    await __T.cloud();
    openUpload();
    await __T.waitFor(function(){ return document.getElementById('fpick'); }, 4000, 'open');
    var f = await __T.wideFile();
    readUpFile(f);
    await __T.waitFor(function(){ return UP.list && UP.list.length >= 31; }, 30000, 'parse');
    await __T.waitFor(function(){ return document.querySelector('#up-rows'); }, 4000, 'rows');
  }catch(e){ document.title = 'ERR ' + e.message; }
})();
</script>'''

S_MGR = r'''
<script>
(async function(){
  try{
    await __T.cloud();
    await __T.waitFor(function(){ return CUSTOM.length >= 31; }, 40000, 'sync');
    openMgr();
    await __T.waitFor(function(){ return document.querySelector('button[data-rm]'); }, 5000, 'mgr');
  }catch(e){ document.title = 'ERR ' + e.message; }
})();
</script>'''

SHOTS = [
    ('导出-宽表识别31列.png', 's_up.html',  S_UP,  1720, 1500, 60000),
    ('导出-我的商品31条.png', 's_mgr.html', S_MGR, 1720, 1300, 60000),
]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    h = functools.partial(Quiet, directory=SITE)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(('127.0.0.1', PORT), h)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def shoot(name, page, w, h, budget):
    out = os.path.join(OUT, name)
    if os.path.exists(out):
        os.remove(out)
    cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
           '--hide-scrollbars', '--window-size=%d,%d' % (w, h),
           '--virtual-time-budget=%d' % budget, '--screenshot=' + out,
           'http://localhost:%d/%s' % (PORT, page)]
    subprocess.run(cmd, capture_output=True, timeout=300)
    return os.path.exists(out), (os.path.getsize(out) if os.path.exists(out) else 0)


def main():
    import json
    meta = json.load(io.open(XLSX_SRC, encoding='utf-8'))
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE, exist_ok=True)
    shutil.copy2(meta['xlsx'], os.path.join(SITE, XLSX_NAME))
    src = io.open(SRC_PAGE, encoding='utf-8').read()
    for name, page, js, w, h, b in SHOTS:
        io.open(os.path.join(SITE, page), 'w', encoding='utf-8').write(
            src.replace('</body>', HELPERS + js + '</body>', 1))
    srv = serve()
    for name, page, js, w, h, b in SHOTS:
        t0 = time.time()
        ok, size = shoot(name, page, w, h, b)
        print('  %-26s %s  %8s  %4.1fs' % (name, '✓' if ok else '✗',
                                           ('%.0f KB' % (size / 1024)) if ok else '', time.time() - t0))
    srv.shutdown()
    shutil.rmtree(SITE, ignore_errors=True)
    print('（已清理临时目录；全程只读云端，未写入 wb_c100_series）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
