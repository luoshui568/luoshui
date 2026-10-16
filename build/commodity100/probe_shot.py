#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给「我的商品」功能出视觉截图（上传面板 / 编辑面板 / 选择区 / 主图对比）。

和 probe_mine_e2e.py 一样的约束：临时目录自建、不碰 deploy_site/。
异步等待一律用 requestAnimationFrame（虚拟时间会瞬间跳过 setTimeout）。
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC_PAGE = os.path.join(ROOT, 'deliver', '大宗商品日线对比图-2005-2026.html')
OUT = os.path.join(ROOT, 'deliver')
SITE = os.path.join(HERE, '_shot_site')
XLSX = os.path.join(SITE, '_shot.xlsx')
PORT = 8795
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'

HELPERS = r'''
<script>
(function(){
  function waitFor(fn, max, label){
    return new Promise(function(res, rej){
      var n = 0;
      (function tick(){
        var v = null;
        try{ v = fn(); }catch(e){ return rej(e); }
        if(v) return res(v);
        if(++n > max) return rej(new Error('timeout ' + label));
        requestAnimationFrame(tick);
      })();
    });
  }
  function mkFile(){
    return fetch('_shot.xlsx').then(function(r){ return r.arrayBuffer(); })
      .then(function(ab){ return new File([ab], '沪铜现货.xlsx'); });
  }
  async function upload(name){
    var f = await mkFile();
    openUpload();
    readUpFile(f);
    await waitFor(function(){ return UP.res && UP.res.pts.length >= 2; }, 4000, 'parse');
    document.getElementById('up-name').value = name || '沪铜现货';
    document.getElementById('up-unit').value = '元/吨';
    return CUSTOM.length;
  }
  window.__T = { waitFor: waitFor, upload: upload, mkFile: mkFile };
})();
</script>
'''

# --- 场景脚本 ---------------------------------------------------------------
S_UPLOAD = r'''
<script>
(async function(){
  try{
    await __T.upload('沪铜现货');
    document.getElementById('up-stat').innerHTML =
      document.getElementById('up-stat').innerHTML + '　·　把鼠标放到日期列/价格列上可随时改选';
  }catch(e){ document.title = 'ERR ' + e.message; }
})();
</script>'''

S_EDIT = r'''
<script>
(async function(){
  try{
    await __T.upload('沪铜现货');
    commitUpload();
    await __T.waitFor(function(){ return CUSTOM.length === 1; }, 400, 'commit');
    state.active.add(CUSTOM[0].c);
    buildChips(); redraw();
    openEdit(CUSTOM[0].c);
  }catch(e){ document.title = 'ERR ' + e.message; }
})();
</script>'''

S_CHIPS = r'''
<script>
(async function(){
  try{
    await __T.upload('沪铜现货');
    commitUpload();
    await __T.waitFor(function(){ return CUSTOM.length === 1; }, 400, 'commit');
    var ab = await (await fetch('_shot.xlsx')).arrayBuffer();
    openUpload();
    readUpFile(new File([ab], '螺纹钢.xlsx'));
    await __T.waitFor(function(){ return UP.res && UP.res.pts.length >= 2; }, 4000, 'p2');
    var to = UP.names[1];
    document.getElementById('up-sheet').onchange({ target: { value: to } });
    await __T.waitFor(function(){ return UP.sheet === to && UP.res && UP.res.pts.length >= 2; }, 3000, 'p3');
    document.getElementById('up-name').value = '螺纹钢现货';
    document.getElementById('up-unit').value = '元/吨';
    commitUpload();
    await __T.waitFor(function(){ return CUSTOM.length === 2; }, 400, 'commit2');
    closeDlg();
    /* 两条自定义都勾上，截图里才看得到选中态的颜色 */
    CUSTOM.forEach(function(s){ state.active.add(s.c); });
    buildChips(); redraw();
  }catch(e){ document.title = 'ERR ' + e.message; }
})();
</script>'''

S_MAIN = r'''
<script>
(async function(){
  try{
    await __T.upload('沪铜现货');
    commitUpload();
    await __T.waitFor(function(){ return CUSTOM.length === 1; }, 400, 'commit');
    state.active.add(CUSTOM[0].c);
    state.active.add('gold'); state.active.add('copper');
    buildChips();
    setRangeDays(365 * 3, '3y');
    await __T.waitFor(function(){ return chart && chart.scales.x; }, 200, 'chart');
    var r = cbox.getBoundingClientRect();
    cbox.dispatchEvent(new MouseEvent('mousemove', {
      clientX: r.left + r.width * 0.62, clientY: r.top + r.height * 0.46, bubbles: true }));
    await __T.waitFor(function(){ return XH.on; }, 120, 'xh');
  }catch(e){ document.title = 'ERR ' + e.message; }
})();
</script>'''

S_GAP = r'''
<script>
(async function(){
  try{
    var ab = await (await fetch('_shot.xlsx')).arrayBuffer();
    openUpload();
    readUpFile(new File([ab], '锌锭现货.xlsx'));
    await __T.waitFor(function(){ return UP.res && UP.res.pts.length >= 2; }, 4000, 'p');
    var to = '跳日现货';
    document.getElementById('up-sheet').onchange({ target: { value: to } });
    await __T.waitFor(function(){ return UP.sheet === to && UP.res && UP.res.pts.length >= 2; }, 3000, 'p2');
    document.getElementById('up-name').value = '锌锭现货';
    document.getElementById('up-unit').value = '元/吨';
    commitUpload();
    await __T.waitFor(function(){ return CUSTOM.length === 1; }, 400, 'commit');
    openEdit(CUSTOM[0].c);
  }catch(e){ document.title = 'ERR ' + e.message; }
})();
</script>'''

SHOTS = [
    ('我的商品-上传面板.png', 'shot_upload.html', S_UPLOAD, 1512, 1500),
    ('我的商品-编辑面板.png', 'shot_edit.html', S_EDIT, 1512, 1560),
    ('我的商品-补数据点.png', 'shot_gap.html', S_GAP, 1512, 1560),
    ('我的商品-选择区.png', 'shot_chips.html', S_CHIPS, 1512, 1560),
    ('我的商品-主图对比.png', 'shot_main.html', S_MAIN, 1512, 2400),
]


def make_xlsx():
    """两列（日期 + 价格），贴近用户手上的那种简单表。"""
    import datetime
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = '沪铜现货'
    ws.append(['日期', '现货价(元/吨)'])
    v = 68000
    for i in range(46):
        d = datetime.date(2023, 5, 8) + datetime.timedelta(days=i * 2)
        v = v + ((i % 7) - 3) * 230 + 60
        ws.append([d, round(v, 1)])
    for r in range(2, 48):
        ws.cell(row=r, column=1).number_format = 'yyyy-mm-dd'
    ws2 = wb.create_sheet('螺纹钢现货')
    ws2.append(['日期', '现货价(元/吨)'])
    v = 3900
    for i in range(46):
        d = datetime.date(2023, 5, 8) + datetime.timedelta(days=i * 2)
        v = v + ((i % 5) - 2) * 26 + 9
        ws2.append([d, round(v, 1)])
    for r in range(2, 48):
        ws2.cell(row=r, column=1).number_format = 'yyyy-mm-dd'

    # 表 3：数据不全 —— 4 个月只给了 8 天，用来展示编辑面板里「间隔」列的缺口标记
    ws3 = wb.create_sheet('跳日现货')
    ws3.append(['日期', '现货价(元/吨)'])
    gaps = ['2023-05-08', '2023-05-22', '2023-06-19', '2023-07-03',
            '2023-08-14', '2023-09-04', '2023-10-09', '2023-11-06']
    gv = [21400, 21260, 21850, 22100, 21640, 22480, 22930, 22710]
    for ds, x in zip(gaps, gv):
        y, m, dd = (int(t) for t in ds.split('-'))
        ws3.append([datetime.date(y, m, dd), x])
    for r in range(2, 10):
        ws3.cell(row=r, column=1).number_format = 'yyyy-mm-dd'

    wb.save(XLSX)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


def serve():
    h = functools.partial(Quiet, directory=SITE)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(('127.0.0.1', PORT), h)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE, exist_ok=True)
    make_xlsx()
    src = io.open(SRC_PAGE, encoding='utf-8').read()
    srv = serve()
    for out_name, page, script, w, h in SHOTS:
        io.open(os.path.join(SITE, page), 'w', encoding='utf-8').write(
            src.replace('</body>', HELPERS + script + '</body>', 1))
        out = os.path.join(OUT, out_name)
        cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
               '--hide-scrollbars', '--window-size=%d,%d' % (w, h),
               '--virtual-time-budget=22000', '--screenshot=' + out,
               'http://localhost:%d/%s' % (PORT, page)]
        r = subprocess.run(cmd, capture_output=True, timeout=300)
        ok = os.path.exists(out)
        print('%-28s %s  %s' % (out_name, 'OK' if ok else 'FAIL',
                                ('%d KB' % (os.path.getsize(out) / 1024)) if ok else r.stderr.decode()[:200]))
    srv.shutdown()
    shutil.rmtree(SITE, ignore_errors=True)
    print('（已清理临时目录）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
