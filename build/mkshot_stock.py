# -*- coding: utf-8 -*-
"""投资标的模块 · 效果截图（注入示例标的 + 真实行情）"""
import os
import shutil
import subprocess
import http.server
import socketserver
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(BASE, 'deploy', 'index.html')
OUTDIR = os.path.join(BASE, 'build')
PORT = 8901

TX = ['sh600459', 'sh601600', 'sz000807', 'sh600547', 'sh601168', 'sh603993',
      'sz000831', 'sz000970', 'sz002532', 'sz002378', 'sz000630', 'sh601958']

GRP = {'600459': '贵金属', '600547': '贵金属', '601600': '工业金属', '000807': '工业金属',
       '601168': '工业金属', '603993': '工业金属', '000630': '工业金属', '002532': '工业金属',
       '000831': '稀土磁材', '000970': '稀土磁材', '002378': '小金属', '601958': '小金属'}

# 慢变量（真实来源为财报 / 公司资料；此处为示例值，用于展示列效果）
EXTRA = {
    '600459': {'sub_industry': '贵金属', 'region': '云南', 'total_assets': 252.74, 'ind_pe': 31.8},
    '600547': {'sub_industry': '黄金', 'region': '山东', 'total_assets': 1583.6, 'ind_pe': 34.2},
    '601600': {'sub_industry': '铝', 'region': '北京', 'total_assets': 2150.4, 'ind_pe': 12.6},
    '000807': {'sub_industry': '铝', 'region': '云南', 'total_assets': 486.2, 'ind_pe': 12.6},
    '601168': {'sub_industry': '铅锌', 'region': '青海', 'total_assets': 574.1, 'ind_pe': 18.4},
    '603993': {'sub_industry': '铜钴', 'region': '河南', 'total_assets': 1982.3, 'ind_pe': 18.4},
    '000630': {'sub_industry': '铜', 'region': '安徽', 'total_assets': 782.5, 'ind_pe': 18.4},
    '002532': {'sub_industry': '铝', 'region': '新疆', 'total_assets': 612.8, 'ind_pe': 12.6},
    '000831': {'sub_industry': '稀土', 'region': '江西', 'total_assets': 61.7, 'ind_pe': 46.5},
    '000970': {'sub_industry': '磁材', 'region': '北京', 'total_assets': 118.3, 'ind_pe': 46.5},
    '002378': {'sub_industry': '钨', 'region': '江西', 'total_assets': 74.9, 'ind_pe': 27.3},
    '601958': {'sub_industry': '钼', 'region': '陕西', 'total_assets': 498.6, 'ind_pe': 27.3},
}


def build_probe(mode):
    s = open(SRC, encoding='utf-8').read()
    s = s.replace('backdrop-filter:', 'backdrop-filter-off:')   # headless 下会糊
    inject = """
<script>
(function(){
  document.documentElement.className = document.documentElement.className
      .replace('gating','') + ' authed';                     /* 绕过登录门，仅截图用 */
  var G = document.getElementById('loginGate'); if(G) G.className = 'gate';
  var TX = %s, GRP = %s, EXTRA = %s;
  setTimeout(function(){
    S.stocks = TX.map(function(t){
      var r = defaults('stocks', {id:'st_'+t.slice(2), code:t.slice(2), exchange:t.slice(0,2), name:''});
      r.grp = GRP[r.code] || '';
      var e = EXTRA[r.code] || {};
      for(var k in e) r[k] = e[k];
      return r;
    });
    App.go('stock'); sortState(); renderStock();
    syncQuotes({silent:true}).then(function(){ renderStock(); %s });
  }, 700);
})();
</script>
""" % (TX, GRP, EXTRA, "App.stockImportDlg(); var _t=document.getElementById('s-bulk');"
                      "if(_t){ _t.value='600459 贵研铂业\\n601600 中国铝业\\n000807,002532\\n"
                      "sh603993\\n601168 西部矿业\\n002378 章源钨业'; }"
                      if mode == 'modal' else '')
    s = s.replace('</body>', inject + '\n</body>', 1)
    p = os.path.join(OUTDIR, '_shot_%s.html' % mode)
    open(p, 'w', encoding='utf-8').write(s)
    return p


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


os.chdir(OUTDIR)
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', PORT), Quiet)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

shots = [
    ('list',  '_shot_list.html',  'v_stock_list.png', 1680, 1220, 9000),
    ('modal', '_shot_modal.html', 'v_stock_modal.png', 1280, 980, 12000),
]

for mode, htmlname, png, w, h, budget in shots:
    build_probe(mode)
    prof = os.path.join(OUTDIR, '_shot_prof_%s' % mode)
    # ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
    #   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
    os.makedirs(prof, exist_ok=True)
    out = os.path.join(OUTDIR, png)
    if os.path.exists(out):
        os.remove(out)
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--user-data-dir=' + prof, '--window-size=%d,%d' % (w, h),
           '--virtual-time-budget=%d' % budget, '--screenshot=' + out,
           'http://127.0.0.1:%d/%s' % (PORT, htmlname)]
    subprocess.run(cmd, capture_output=True, timeout=180)
    # ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
    #   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
    os.makedirs(prof, exist_ok=True)
    print('%-22s -> %s   %s' % (mode, png, ('%d KB' % (os.path.getsize(out)//1024)) if os.path.exists(out) else '失败'))

httpd.shutdown()
for f in os.listdir(OUTDIR):
    if f.startswith('_shot_'):
        try:
            os.remove(os.path.join(OUTDIR, f))
        except Exception:
            pass
print('临时文件已清理')
