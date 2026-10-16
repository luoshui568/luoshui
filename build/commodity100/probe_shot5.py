# -*- coding: utf-8 -*-
"""「商品标签分组 + 管理面板批量删除」功能截图。

★ 截图站点里把 window.WB_CFG 掏空（本机模式）：
   演示数据只存在于页内内存，一条都不会写进 wb_c100_series。
"""
import functools
import http.server
import io
import json
import os
import re
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
SITE = os.path.join(HERE, '_shot5_site')
META = os.path.join(HERE, '_export_meta.json')
PORT = 8811
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
  /* 演示数据：一条都不进云端（截图站点已把 WB_CFG 掏空） */
  function seed(){
    var mk = function(id, name, tag, unit, base, n, note){
      var s = BYCODE[base];
      return { c: 'u_demo_' + id, n: name, m: '自定义上传', u: unit, col: freeColor(), tag: tag,
               pts: (s.pts0 || s.pts).slice(-n).map(function(p){ return [p[0], p[1]]; }),
               note: note, src: 'upload', t: Date.now() };
    };
    var recs = [
      mk('m1', '钼精矿 · Mo · 45% · 河南', '钼系', '元/吨', 'copper', 900, '来自 现货价钼精矿.xlsx · 第 2 列'),
      mk('m2', '钼铁 · FeMo60 · 洛阳市 · 栾川', '钼系', '元/吨', 'zinc', 900, '来自 现货价钼精矿.xlsx · 第 4 列'),
      mk('m3', '焦煤 · 大商所', '钢铁原料', '元/吨', 'crude', 900, '来自 焦煤日线.xlsx · 第 2 列'),
      mk('m4', '黄金 · 现货（我自己整理的）', '贵金属', '元/克', 'gold', 900, '来自 黄金现货.xlsx · 第 2 列'),
      mk('m5', '天然气 · 华东到岸', '', '美元/百万英热', 'gas_i', 900, '来自 天然气到岸价.xlsx · 第 2 列')
    ];
    recs.forEach(function(r){ CUSTOM.push(r); state.active.add(r.c); });
    afterCustomChange();
  }
  window.__T = {
    waitFor: waitFor, seed: seed,
    wideFile: function(){
      return fetch('__XLSX__').then(function(r){ return r.arrayBuffer(); })
        .then(function(ab){ return new File([ab], '大宗商品日线-31品种-宽表.xlsx'); });
    },
    scrollTo: function(sel){
      var el = document.querySelector(sel);
      if(el) window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 24);
    }
  };
})();
</script>
'''.replace('__XLSX__', XLSX_NAME)

S_UP = r'''
<script>
(async function(){
  try{
    openUpload();
    await __T.waitFor(function(){ return document.getElementById('fpick'); }, 4000, 'open');
    var f = await __T.wideFile();
    readUpFile(f);
    await __T.waitFor(function(){ return UP.list && UP.list.length >= 31; }, 30000, 'parse');
    var t = document.getElementById('up-tag');
    t.value = '钼系';
    t.dispatchEvent(new Event('input', { bubbles: true }));
    await __T.waitFor(function(){ return document.querySelector('#up-rows tr'); }, 4000, 'rows');
  }catch(e){ document.title = 'ERR ' + e.message; }
})();
</script>'''

S_CHIPS = r'''
<script>
(async function(){
  try{
    __T.seed();
    await __T.waitFor(function(){ return document.querySelectorAll('.gt[data-tag]').length >= 4; }, 6000, 'chips');
    /* 不滚动：把窗口开够高，chip 区自然落在可见范围内（滚动容易落到空白带） */
  }catch(e){ document.title = 'ERR ' + e.message; }
})();
</script>'''

S_MGR = r'''
<script>
(async function(){
  try{
    __T.seed();
    openMgr();
    await __T.waitFor(function(){ return document.querySelector('input.mg-ck'); }, 5000, 'mgr');
    document.getElementById('mg-all').click();          // 全选：展示批量操作条
  }catch(e){ document.title = 'ERR ' + e.message; }
})();
</script>'''

SHOTS = [
    ('标签-上传面板选标签.png', 's_up.html',    S_UP,    1512, 1180, 60000),
    ('标签-chip区按标签分组.png', 's_chips.html', S_CHIPS, 1512, 1120, 40000),
    ('标签-管理面板批量删除.png', 's_mgr.html',   S_MGR,   1512, 1050, 40000),
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
    meta = json.load(io.open(META, encoding='utf-8'))
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE, exist_ok=True)
    shutil.copy2(meta['xlsx'], os.path.join(SITE, XLSX_NAME))
    src = io.open(SRC_PAGE, encoding='utf-8').read()
    stripped, cnt = re.subn(r'window\.WB_CFG\s*=\s*\{[^}]*\};',
                            'window.WB_CFG = null;   /* 截图站点：本机模式，不写云端 */', src)
    assert cnt == 1, '未能掏空 WB_CFG（匹配 %d 次）' % cnt
    for name, page, js, w, h, b in SHOTS:
        io.open(os.path.join(SITE, page), 'w', encoding='utf-8').write(
            stripped.replace('</body>', HELPERS + js + '</body>', 1))
    srv = serve()
    bad = 0
    for name, page, js, w, h, b in SHOTS:
        t0 = time.time()
        ok, size = shoot(name, page, w, h, b)
        bad += 0 if ok else 1
        print('  %-28s %s  %8s  %4.1fs' % (name, '✓' if ok else '✗',
                                           ('%.0f KB' % (size / 1024)) if ok else '', time.time() - t0))
    srv.shutdown()
    shutil.rmtree(SITE, ignore_errors=True)
    print('（已清理临时目录；本机模式截图，未写入 wb_c100_series）')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
