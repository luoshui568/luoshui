#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证两件事：
  A. 导出的宽表 Excel 能被页面上传面板正确识别成 31 列（列名 / 单位 / 点数逐列核对）
  B. 云端「我的商品」在全新浏览器里能拉回来、渲染进 chip 区与图表
     （★ 口径 2026-10-13 起：云端只放用户自己的商品；与内置重合的那批导出记录
       已按用户要求删除，所以这里不再断言固定的 31 条 id）

跑法：
  /Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python probe_export_e2e.py
前置：
  先跑过 export_builtin_excel.py（产出桌面 xlsx 与 _export_meta.json）
"""
import functools
import http.server
import io
import json
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
SITE = os.path.join(HERE, '_export_site')
PAGE = 'commodity-daily.html'
PROBE_PAGE = '_export_probe.html'
XLSX_NAME = '_builtin_wide.xlsx'
META = os.path.join(HERE, '_export_meta.json')
PORT = 8806
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'

meta = json.load(io.open(META, encoding='utf-8'))
EXPECT = [{'name': s['name'], 'unit': s['unit'], 'n': s['n']} for s in meta['series']]
EXPECT_IDS = {s['id']: s['n'] for s in meta['series']}
EXPECT_TOTAL = meta['total_points']

DBG = r'''
<pre id="dbg" style="display:none"></pre>
<script>
(function(){
  var EXPECT = __EXPECT__, EXPECT_IDS = __IDS__, EXPECT_TOTAL = __TOTAL__;
  var errs = [], out = [];
  window.addEventListener('error', function(e){ errs.push('ERR: ' + e.message); });
  window.addEventListener('unhandledrejection', function(e){
    errs.push('REJ: ' + ((e.reason && e.reason.message) || e.reason));
  });
  function log(k, v){ out.push(k + ' = ' + v); }
  function sec(t){ out.push(''); out.push('=== ' + t + ' ==='); }
  function id(i){ return document.getElementById(i); }
  function isOpen(){ return id('mask').classList.contains('on'); }
  function click(i){
    var e = id(i);
    if(!e){ out.push('✗ 找不到按钮 ' + i); return false; }
    e.click(); return true;
  }
  function waitFor(fn, ms, tag){
    return new Promise(function(res, rej){
      var t0 = Date.now();
      (function poll(){
        var v; try{ v = fn(); }catch(e){ return rej(new Error(tag + ' 抛错: ' + e.message)); }
        if(v) return res(v);
        if(Date.now() - t0 > (ms || 3000)) return rej(new Error(tag + ' 超时(' + (ms || 3000) + 'ms)'));
        requestAnimationFrame(poll);
      })();
    });
  }
  function post(){
    if(posted) return; posted = true;
    fetch('/__export__', { method: 'POST',
      body: out.join('\n') + '\n\nJS错误: ' + (errs.length ? errs.join(' | ') : '无') });
  }
  var posted = false;
  function mark(t){ out.push('  ⏱ ' + t + ' @' + Math.round(performance.now()) + 'ms'); }
  /* 看门狗：主流程卡住也要把当前进度回传，否则只能看到「没收到探针」 */
  setTimeout(function(){ out.push(''); out.push('★ 看门狗触发：90 秒仍未走完，回传当前进度'); post(); }, 90000);
  window.__post = post;

  (async function(){
    try{
      /* ============ A. 宽表 Excel → 上传面板识别 ============ */
      sec('A. 导出的宽表 Excel 在上传面板里的识别结果');
      mark('脚本启动');
      log('云端状态徽标', (id('cst') || {}).textContent || '(无)');
      click('btn-up');
      await waitFor(function(){ return !!id('fpick'); }, 4000, '打开上传面板');
      mark('上传面板已打开');

      var ab = await (await fetch('__XLSX__')).arrayBuffer();
      mark('xlsx 已下载 ' + ab.byteLength + ' 字节');
      readUpFile(new File([ab], '大宗商品日线-31品种-宽表.xlsx'));
      await waitFor(function(){ return UP.list && UP.list.length; }, 60000, '解析 xlsx');
      mark('xlsx 解析完成');

      log('工作表', UP.names.join(' / '));
      log('日期列 index（应 0）', UP.map.dateCol);
      log('表头行 / 单位行 / 数据起始行（应 0 / 1 / 2）',
          UP.map.hdrRow + ' / ' + UP.map.unitRow + ' / ' + UP.map.dataStart);
      log('识别到的数值列数（应 31）', UP.map.valCols.length);
      log('识别到的列号序列', UP.map.valCols.join(','));
      log('默认已勾选列数（应 31）', UP.pick.size);
      log('汇总按钮文字', (id('up-ok') || {}).textContent || '(无)');
      log('统计条', ((id('up-stat') || {}).textContent || '').replace(/\s+/g, ' ').trim().slice(0, 200));

      var bad = [], tot = 0;
      EXPECT.forEach(function(e, i){
        var it = UP.list[i];
        if(!it){ bad.push('第' + (i+1) + '列 缺失'); return; }
        tot += it.pts.length;
        if(it.name !== e.name) bad.push('第' + (i+1) + '列 名称 ' + JSON.stringify(it.name) + ' ≠ ' + JSON.stringify(e.name));
        if(it.unit !== e.unit) bad.push('第' + (i+1) + '列 单位 ' + JSON.stringify(it.unit) + ' ≠ ' + JSON.stringify(e.unit));
        if(it.pts.length !== e.n) bad.push('第' + (i+1) + '列 ' + it.name + ' 点数 ' + it.pts.length + ' ≠ ' + e.n);
      });
      log('逐列核对不一致项', bad.length ? bad.slice(0, 8).join(' | ') + (bad.length > 8 ? ' …共' + bad.length : '') : '无（31/31 全对）');
      log('解析出的数据点合计（应 ' + EXPECT_TOTAL + '）', tot);
      log('合计是否一致', tot === EXPECT_TOTAL);
      var p0 = UP.list[0], pL = UP.list[UP.list.length - 1];
      log('首列区间', dayToStr(p0.pts[0][0]) + ' → ' + dayToStr(p0.pts[p0.pts.length-1][0]));
      log('末列区间', dayToStr(pL.pts[0][0]) + ' → ' + dayToStr(pL.pts[pL.pts.length-1][0]));
      log('前 3 列名', UP.list.slice(0,3).map(function(x){ return x.name + '(' + x.unit + ',' + x.pts.length + ')'; }).join(' | '));
      log('后 3 列名', UP.list.slice(-3).map(function(x){ return x.name + '(' + x.unit + ',' + x.pts.length + ')'; }).join(' | '));

      /* 关掉面板，不点导入（入库由 export 脚本负责，避免重复） */
      closeDlg();
      await waitFor(function(){ return !isOpen(); }, 3000, '关闭上传面板');
      mark('A 段结束');

      /* ★ 口径（2026-10-13 起）：云端只放「用户自己的商品」——与内置重合的那批
         导出记录已按用户要求删除，所以这里改为断言「云端拉回来的每一条都真的
         进了 chip 区、并归到了某个标签组」，不再按固定 id 列表点名。 */
      sec('B. 云端「我的商品」在页面里的落地');
      log('云端状态徽标', (id('cst') || {}).textContent || '(无)');
      mark('等云端同步');
      await waitFor(function(){
        return CLOUD_STATE === 'on' && CUSTOM.length >= 1;
      }, 60000, '等待云端把我自己的商品拉回来');
      mark('云端同步完成');
      log('已运行 ' + Math.round(performance.now()) + ' ms');
      log('云端状态 CLOUD_STATE / 拉回条数', CLOUD_STATE + ' / ' + CUSTOM.length);
      var ups = CUSTOM.filter(function(s){ return s.src === 'upload'; });
      log('其中上传形式 / 内置覆盖', ups.length + ' / ' + CUSTOM.filter(function(s){ return s.src === 'overlay'; }).length);
      log('每条都进了 chip 区', ups.every(function(s){ return !!document.querySelector('.chip[data-c="' + s.c + '"]'); }));
      log('每条都归到了某个标签组', (function(){
        var tk = customByTag().keys;                 // 页面侧的标签分组清单
        var orph = ups.filter(function(s){ return tk.indexOf(tagOf(s)) < 0; });
        return orph.length ? ('✗ 孤儿：' + orph.map(function(s){ return s.n; }).join(',')) : 'true';
      })());
      log('标签分组', customByTag().keys.join(' / ') || '（无）');
      log('拉回的可显示商品', ups.map(function(s){ return s.n + ' ' + s.pts.length + '点'; }).join(' | ') || '（无）');

      log('ALL.length（内置 + 自定义）', ALL.length);
      log('内置条数 BUILTIN', typeof BUILTIN !== 'undefined' ? BUILTIN : '(未定义)');
      var ds = (chart && chart.data) ? chart.data.datasets.length : -1;
      log('图表 dataset 数', ds);
      log('选中（图上可见）条数 state.active', (typeof state !== 'undefined' && state.active) ? state.active.size : '(未知)');
      log('我这条是否已选中', (typeof state !== 'undefined' && state.active) ? state.active.has(Object.keys(EXPECT_IDS)[0]) : '(未知)');
      log('图表画布尺寸', (id('cv') ? id('cv').width + 'x' + id('cv').height : '(无画布)'));
      log('页面统计卡「日线序列」', (function(){
        var t = document.body.textContent.match(/日线序列\s*([\d]+)\s*条/);
        return t ? t[1] + ' 条' : '(没找到)';
      })());

      /* 抽查：内置黄金的价格覆盖记录（overlay）是否仍正确覆写到内置序列上 */
      var ovg = CUSTOM.filter(function(x){ return x.src === 'overlay' && x.base === 'gold'; })[0];
      if(ovg){
        log('内置 gold 覆盖记录点数 / 图上点数', ovg.pts.length + ' / ' + BYCODE['gold'].pts.length);
        log('覆盖生效（图上用的就是覆盖数据）', BYCODE['gold'].pts.length === ovg.pts.length);
      } else {
        log('内置覆盖记录', '无（当前没改过内置价格）');
      }
    }catch(e){
      out.push('★ 探针中断：' + (e && e.message || e));
    }
    post();
  })();
})();
</script>
'''
DBG = (DBG.replace('__EXPECT__', json.dumps(EXPECT, ensure_ascii=False))
          .replace('__IDS__', json.dumps(EXPECT_IDS, ensure_ascii=False))
          .replace('__TOTAL__', str(EXPECT_TOTAL))
          .replace('__XLSX__', XLSX_NAME))


RESULT = []


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        RESULT.append(self.rfile.read(n).decode('utf-8', 'ignore'))
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')


def serve():
    h = functools.partial(Quiet, directory=SITE)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(('127.0.0.1', PORT), h)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def run_probe(url, timeout=180):
    del RESULT[:]
    cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
           '--window-size=1512,1600', url]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if RESULT:
            break
        time.sleep(0.25)
    time.sleep(0.4)
    try:
        p.terminate(); p.wait(timeout=8)
    except Exception:
        try: p.kill()
        except Exception: pass
    return RESULT[0] if RESULT else '（%.0f 秒内没收到探针回传）' % timeout


def main():
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE, exist_ok=True)
    shutil.copy2(meta['xlsx'], os.path.join(SITE, XLSX_NAME))
    src = io.open(SRC_PAGE, encoding='utf-8').read()
    io.open(os.path.join(SITE, PAGE), 'w', encoding='utf-8').write(src)
    io.open(os.path.join(SITE, PROBE_PAGE), 'w', encoding='utf-8').write(
        src.replace('</body>', DBG + '</body>', 1))
    print('宽表：%s（%.1f KB）' % (os.path.basename(meta['xlsx']),
                                  os.path.getsize(meta['xlsx']) / 1024.0))
    print('期望：31 列 / %d 点 / id 段 %s ... %s'
          % (EXPECT_TOTAL, meta['series'][0]['id'], meta['series'][-1]['id']))
    srv = serve()
    print('\n' + '=' * 76)
    print(run_probe('http://localhost:%d/%s' % (PORT, PROBE_PAGE), timeout=200))
    print('=' * 76)
    srv.shutdown()
    shutil.rmtree(SITE, ignore_errors=True)
    print('\n（已清理探针临时目录 %s）' % os.path.relpath(SITE, HERE))
    return 0


if __name__ == '__main__':
    sys.exit(main())
