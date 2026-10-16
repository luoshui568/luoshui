#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据文库页 · 真机 E2E 探针（Edge headless + 本地 http 服务）。

  python3 probe_datalib_e2e.py

覆盖三件事：
  1) 页面能不能从云端把三张表读出来并渲染（模块卡 / 数据集 / 行情序列）
  2) 零依赖 xlsx 解析器能不能正确读出「日期列 + 中文 + 数字 + 多工作表」
  3) 上传弹窗 → 解析 → 预览那条交互链有没有报错
为什么走 http://localhost 而不是 file://：网关有 Origin 白名单，file:// 的 Origin 是 null 会被挡；
localhost 在白名单里（见项目 README 的取数说明）。
"""
import datetime
import functools
import http.server
import io
import os
import socketserver
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, 'deploy_site')
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
PORT = 8791
XLSX = os.path.join(SITE, '_e2e_commodity.xlsx')

DBG = r'''
<pre id="dbg" style="position:fixed;left:0;top:0;z-index:99999;background:#000;color:#0f0;
  font:12px monospace;padding:6px;max-width:1400px;white-space:pre-wrap"></pre>
<script>
function report(lines){ document.getElementById('dbg').textContent = lines.join('\n'); }
window.addEventListener('load', function(){
  var t = 0;
  var iv = setInterval(function(){
    t++;
    var done = (S.mods.length || S.files.length || S.series.length || S.err);
    if(!done && t < 40) return;
    clearInterval(iv);
    var cards = document.querySelectorAll('#grid .mod');
    var secRows = document.querySelectorAll('#serBox tbody tr');
    report([
      'mods=' + S.mods.length + ' files=' + S.files.length + ' series=' + S.series.length + ' err=' + (S.err || '无'),
      '卡片数=' + cards.length + ' 行情行数=' + secRows.length,
      '统计=' + document.getElementById('stats').textContent.replace(/\s+/g, ' ').trim().slice(0, 120),
      '模块=' + S.mods.map(function(m){ return m.icon + m.title + '(' + m.tag + ')→' + m.url; }).join(' | '),
      '数据集=' + (S.files.length ? S.files.map(function(f){ return f.name + '/' + f.rows_n + '行'; }).join(' | ') : '（空）'),
      '行情=' + S.series.slice(0, 3).map(function(s){ return s.id + ':' + s.n; }).join(' | ') + ' …共' + S.series.length + '条',
      '首卡HTML=' + (cards.length ? cards[0].outerHTML.replace(/\s+/g, ' ').slice(0, 260) : ''),
      '错误=' + (window.__DL_ERR.length ? window.__DL_ERR.join(' ; ') : '无')
    ]);
  }, 250);
});
</script>
'''

XLSXDBG = r'''
<pre id="dbg" style="position:fixed;left:0;top:0;z-index:99999;background:#000;color:#0f0;
  font:12px monospace;padding:6px;max-width:1400px;white-space:pre-wrap"></pre>
<script>
/* ⚠️ 不能用 setTimeout 收结果：无头 + 虚拟时间里定时器会被瞬间跳过去，
   而解压是真实异步工作 —— 定时器先到，会读到「还没解析完」的中间态。
   改成按帧轮询：解析完（U.grids 非空）或出错才收工。 */
var out = [], frames = 0;
function report(){ document.getElementById('dbg').textContent = out.join('\n'); }
function dump(){
  var names = Object.keys(U.grids);
  out.push('等待帧数=' + frames);
  out.push('工作表=' + names.join(' / '));
  var g = U.grid || [];
  out.push('首表行×列=' + g.length + ' × ' + (g[0] ? g[0].length : 0));
  g.slice(0, 5).forEach(function(r, i){ out.push('  r' + (i + 1) + ': ' + JSON.stringify(r)); });
  out.push('末行: ' + JSON.stringify(g[g.length - 1]));
  out.push('下拉框=' + (document.getElementById('upSheet') ? document.getElementById('upSheet').options.length + ' 个工作表' : 'N/A'));
  out.push('预览DOM行数=' + document.querySelectorAll('#pv tbody tr').length);
  out.push('预览表头=' + Array.prototype.map.call(document.querySelectorAll('#pv thead th'), function(t){ return t.textContent; }).join(' | '));
  out.push('名称框=' + (document.getElementById('upName') ? document.getElementById('upName').value : 'N/A'));
  out.push('入库按钮可用=' + (document.getElementById('upGo') && !document.getElementById('upGo').disabled));
  out.push('解析提示=' + document.getElementById('upInfo').textContent.replace(/\s+/g, ' ').slice(0, 110));
  out.push('错误=' + (window.__DL_ERR.length ? window.__DL_ERR.join(' ; ') : '无'));
  report();
}
function poll(){
  frames++;
  if(Object.keys(U.grids).length || /失败|✗/.test(document.getElementById('upInfo').textContent) || frames > 900){ dump(); return; }
  requestAnimationFrame(poll);
}
window.addEventListener('load', function(){
  fetch('_e2e_commodity.xlsx').then(function(r){ return r.arrayBuffer(); }).then(function(ab){
    out.push('文件字节=' + ab.byteLength); report();
    DL.uploadForm();
    DL.readFile(new File([ab], '_e2e_commodity.xlsx'));
    requestAnimationFrame(poll);
  }).catch(function(e){ out.push('FAIL ' + e.message); report(); });
});
</script>
'''


def make_xlsx():
    """造一份贴近真实的商品数据表：日期列（真正的日期格式）+ 中文名 + 数字 + 第二张表。"""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = '有色金属现货'
    ws.append(['日期', '品种', '现货价(元/吨)', '涨跌幅%', '备注'])
    base = datetime.date(2024, 1, 2)
    for i in range(30):
        d = base + datetime.timedelta(days=i)
        ws.append([d, ['铜', '铝', '锌'][i % 3], 68000 + i * 137.5,
                   round((i % 7) - 3 + 0.25, 2), '测试数据' if i % 5 == 0 else ''])
    ws2 = wb.create_sheet('贵金属')
    ws2.append(['日期', '品种', '价格(元/克)'])
    for i in range(8):
        ws2.append([base + datetime.timedelta(days=i), '黄金', 480.5 + i])
    wb.save(XLSX)
    return os.path.getsize(XLSX)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    h = functools.partial(Quiet, directory=SITE)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(('127.0.0.1', PORT), h)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def run_dump(url, wait=9000):
    cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
           '--window-size=1440,1600', '--virtual-time-budget=%d' % wait, '--dump-dom', url]
    dom = subprocess.run(cmd, capture_output=True, timeout=300).stdout.decode('utf-8', 'ignore')
    i = dom.find('id="dbg"')
    if i < 0:
        return 'DBG NOT FOUND'
    return dom[i:i + 2600].split('>')[1].split('<')[0]


def main():
    n = make_xlsx()
    print('测试用 xlsx：%s（%d 字节）' % (os.path.basename(XLSX), n))
    srv = serve()

    # 1) 基础渲染（真实数据来自云端）
    html = io.open(os.path.join(SITE, 'datalib.html'), encoding='utf-8').read()
    io.open(os.path.join(SITE, '_e2e_read.html'), 'w', encoding='utf-8').write(
        html.replace('</body>', DBG + '</body>', 1))
    print('\n=== 1. 数据文库读取渲染 ===')
    print(run_dump('http://localhost:%d/_e2e_read.html' % PORT))

    # 2) xlsx 解析链
    io.open(os.path.join(SITE, '_e2e_xlsx.html'), 'w', encoding='utf-8').write(
        html.replace('</body>', XLSXDBG + '</body>', 1))
    print('\n=== 2. 零依赖 xlsx 解析 ===')
    print(run_dump('http://localhost:%d/_e2e_xlsx.html' % PORT, 12000))

    srv.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
