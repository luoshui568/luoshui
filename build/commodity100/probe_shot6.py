# -*- coding: utf-8 -*-
"""「内置数据已移除 + 备份面板导出 Excel/CSV」功能截图。

★ 截图站点里把 window.WB_CFG 掏空（本机模式）：演示数据只写进本页 localStorage，
  一条都不会落到 wb_c100_series。演示数据本身是**从云端只读拉下来的真实商品**（7 条），
  这样截图里的名字和用户看到的完全一致。
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
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC_PAGE = os.path.join(ROOT, 'deliver', '大宗商品日线对比图-2005-2026.html')
OUT = os.path.join(ROOT, 'deliver')
SITE = os.path.join(HERE, '_shot6_site')
CLOUD_JSON = os.path.abspath(os.path.join(HERE, '..', 'cloud.json'))
PORT = 8812
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'


def fetch_cloud(limit_rows=8):
    """只读拉云端「我的商品」（未删记录），带 pts —— 用作截图里的演示数据。"""
    cfg = json.load(io.open(CLOUD_JSON, encoding='utf-8'))
    rest = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
    url = rest + 'wb_c100_series?select=id,name,unit,color,tag,note,src,base,pts,up&is_del=eq.false&order=up.asc'
    r = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + cfg['key']})
    rows = json.load(urllib.request.urlopen(r, timeout=60))
    recs = []
    for x in rows[:limit_rows]:
        pts = x.get('pts') or []
        if len(pts) < 2:
            continue
        recs.append({'c': x['id'], 'n': x['name'], 'u': x.get('unit') or '',
                     'col': x.get('color') or '#FF4D6D', 'tag': x.get('tag') or '',
                     'note': x.get('note') or '', 'src': 'upload',
                     'pts': [[int(p[0]), p[1]] for p in pts], 't': 1})
    return recs


def seed_script(recs):
    return ('<script>try{localStorage.setItem("wb_c100_custom_v1",'
            + json.dumps(json.dumps(recs, ensure_ascii=False))
            + ')}catch(e){}</script>')


S_PLAIN = ''      # 什么都不做：只把数据灌进 localStorage，拍首屏

S_BAK = '''
<script>
(async function(){
  try{
    openBak();
    await new Promise(function(r){ setTimeout(r, 400); });
    if(!document.getElementById('bk-xlsx')) document.title = 'ERR 备份按钮没出来';
  }catch(e){ document.title = 'ERR ' + e.message; }
})();
</script>'''


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
    recs = fetch_cloud()
    print('演示数据（只读自云端）：%d 条 —— %s' % (len(recs), ' / '.join(x['n'] for x in recs)))
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE, exist_ok=True)
    src = io.open(SRC_PAGE, encoding='utf-8').read()
    stripped, cnt = re.subn(r'window\.WB_CFG\s*=\s*\{[^}]*\};',
                            'window.WB_CFG = null;   /* 截图站点：本机模式，不写云端 */', src)
    assert cnt == 1, '未能掏空 WB_CFG（匹配 %d 次）' % cnt
    i = stripped.find('<body')
    j = stripped.find('>', i)
    head, body = stripped[:j + 1], stripped[j + 1:]

    # ① 有数据的首屏（chip 区只剩「我的商品」，无内置分组）
    io.open(os.path.join(SITE, 's_plain.html'), 'w', encoding='utf-8').write(
        head + seed_script(recs) + body)
    # ② 备份面板（Excel / CSV / json 三个导出按钮）
    io.open(os.path.join(SITE, 's_bak.html'), 'w', encoding='utf-8').write(
        head + seed_script(recs) + body.replace('</body>', S_BAK + '</body>', 1))
    # ③ 空态（没有任何商品时的提示）
    io.open(os.path.join(SITE, 's_empty.html'), 'w', encoding='utf-8').write(
        head + body)

    SHOTS = [
        ('清理-只剩我的商品.png',   's_plain.html', 1512, 1180, 40000),
        ('导出-备份面板Excel与CSV.png', 's_bak.html',  1512,  900, 40000),
        ('清理-空图提示.png',      's_empty.html', 1512,  820, 40000),
    ]
    srv = serve()
    bad = 0
    for name, page, w, h, b in SHOTS:
        t0 = time.time()
        ok, size = shoot(name, page, w, h, b)
        bad += 0 if ok else 1
        print('  %-32s %s  %8s  %4.1fs' % (name, '✓' if ok else '✗',
                                           ('%.0f KB' % (size / 1024)) if ok else '', time.time() - t0))
    srv.shutdown()
    shutil.rmtree(SITE, ignore_errors=True)
    print('（已清理临时目录；本机模式截图，未写入 wb_c100_series）')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
