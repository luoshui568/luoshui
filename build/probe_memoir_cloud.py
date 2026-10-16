#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「回忆录」线上云端写入自检（会真的写一条到 wb_memoirs，跑完打印 id 供清理）。

做三件事：
  1. 用无头浏览器打开线上 memoir.html（**云端模式**，不作弊）
  2. 点真实按钮「＋ 新建笔记」→ 改标题 → 改正文 → 等自动保存
  3. Python 侧用 REST 回读那一行，确认（a）写进去了（b）Origin 白名单放行（c）字段齐全
跑完自己不做清理：把 id 打印出来，由调用方决定（生产表只留用户自己的内容）。

跑法：/Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python build/probe_memoir_cloud.py
"""
import functools
import http.server
import io
import json
import os
import re
import socketserver
import subprocess
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest' % CFG['envId']
PAGE = 'https://liuchaowang.cn/memoir.html'
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
PORT = 8853
TITLE = '云写入自检-可删'
RESULT = []

INJ = r'''
<script>
(function(){
  var out = [];
  function put(k, v){ out.push(k + ' = ' + v); }
  function sleep(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
  (async function(){
    try{
      var t0 = Date.now();
      while(Date.now() - t0 < 20000){
        if(typeof UI !== 'undefined' && UI.mode === 'cloud'){ break; }
        await sleep(200);
      }
      put('UI.mode', UI.mode);
      put('徽标', (document.getElementById('modeBadge') || {}).textContent);
      put('起始条数', NOTES.length);
      document.querySelector('.rnew').click();
      await sleep(250);
      put('新建后条数', NOTES.length);
      put('新建 id', UI.cur);
      var et = document.getElementById('etitle');
      et.value = '@TITLE@';
      et.dispatchEvent(new Event('input', { bubbles: true }));
      var eb = document.getElementById('ebody');
      eb.innerHTML = '<div>这是一次写入自检，跑完会被删除。</div>' +
                     '<div><b>加粗</b> · <span style="font-size:24px;color:#c0392b">大号红字</span></div>';
      eb.dispatchEvent(new Event('input', { bubbles: true }));
      await sleep(2600);                     /* 等 1.2s 防抖 + 网络往返 */
      put('保存状态', (document.getElementById('saveState') || {}).textContent);
      put('自动保存后 UI.dirty', UI.dirty);
      /* 再改一次标题，验证 PATCH 通道 */
      et.value = '@TITLE@' + '-改';
      et.dispatchEvent(new Event('input', { bubbles: true }));
      document.getElementById('btnPin').click();      /* 置顶 → 又一次 upsert */
      await sleep(2600);
      put('二次保存状态', (document.getElementById('saveState') || {}).textContent);
      out.push('__OK__');
    }catch(e){ out.push('✗ ' + (e && e.message)); out.push('__OK__'); }
    try{ await fetch('/', { method:'POST', body: out.join('\n') }); }catch(e){}
  })();
})();
</script>
'''


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        RESULT.append(self.rfile.read(n).decode('utf-8', 'replace'))
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')


def main():
    import shutil
    site = os.path.join(HERE, '_mem_cloud')
    shutil.rmtree(site, ignore_errors=True)
    os.makedirs(site)
    # 一个空壳页，只为把探针脚本托管在同源 http://localhost 上（避免 file:// 的 Origin=null）
    io.open(os.path.join(site, 'index.html'), 'w', encoding='utf-8').write(
        '<!DOCTYPE html><html><body></body></html>')

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(('127.0.0.1', PORT), functools.partial(Quiet, directory=site))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    # ★ 抓**线上字节**、用 localhost 托管来跑：既验的是线上那一份代码，
    #   Origin=http://localhost:<port> 又在网关白名单内（127.0.0.1 不在，所以 URL 必须写 localhost）。
    raw = urllib.request.urlopen(urllib.request.Request(
        PAGE, headers={'User-Agent': 'wb-probe'}), timeout=40).read().decode('utf-8', 'replace')
    print('线上字节 %d bytes' % len(raw))
    assert 'var DEV_MODE = false;' in raw, '线上字节里找不到 DEV_MODE 开关'
    k = raw.rfind('</body>')
    io.open(os.path.join(site, 'probe.html'), 'w', encoding='utf-8').write(
        raw[:k] + INJ.replace('@TITLE@', TITLE) + raw[k:])

    cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
           '--window-size=1440,1100', 'http://localhost:%d/probe.html' % PORT]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 150 and not RESULT:
        time.sleep(0.3)
    try:
        p.terminate(); p.wait(timeout=8)
    except Exception:
        pass
    httpd.shutdown()
    shutil.rmtree(site, ignore_errors=True)

    print(RESULT[0] if RESULT else '（没收到回传）')
    print('-' * 70)

    # ---- REST 回读：确认真的落到 wb_memoirs ----
    def get(qs):
        from urllib.parse import quote
        req = urllib.request.Request(REST + '/wb_memoirs' + quote(qs, safe='?=&*.,'),
                                     headers={'Authorization': 'Bearer ' + CFG['key']})
        return json.loads(urllib.request.urlopen(req, timeout=30).read().decode('utf-8'))

    rows = get('?title=like.*' + TITLE + '*&select=*')
    print('REST 回读命中 %d 行' % len(rows))
    for r in rows:
        print('  id=%s' % r['id'])
        print('  title=%r' % r['title'])
        print('  pin=%s  is_del=%s  words=%s' % (r['pin'], r['is_del'], r['words']))
        print('  body=%s' % Stringish(r['body']))
    ok = len(rows) == 1 and rows[0]['pin'] is True and 'font-size' in (rows[0]['body'] or '')
    print('-' * 70)
    print('结论：' + ('✓ 云端写入通道正常（新建 + 自动保存 + PATCH 置顶 都落库）'
                    if ok else '✗ 云端写入有问题'))
    if rows:
        print('★ 需要清理的记录 id：%s' % rows[0]['id'])
    return 0 if ok else 1


def Stringish(s):
    s = str(s or '')
    return re.sub(r'\s+', ' ', s)[:160]


if __name__ == '__main__':
    raise SystemExit(main())
