# -*- coding: utf-8 -*-
"""投资标的模块 v2 · 效果截图

与 v1 的区别：不再手填基本面示例值 —— 直接跑**真实** syncQuotes()，
让 行业PE / 细分行业 / 总资产(亿) / 地区 四列由东财数据源自动补齐，截图即为真实效果。
"""
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(BASE, 'deploy', 'index.html')
OUTDIR = os.path.join(BASE, 'build')
PORT = 8903

TX = ['sh600459', 'sh601600', 'sz000807', 'sh600547', 'sh601168', 'sh603993',
      'sz000831', 'sz000970', 'sz002532', 'sz002378', 'sz000630', 'sh601958']

GRP = {'600459': '贵金属', '600547': '贵金属', '601600': '工业金属', '000807': '工业金属',
       '601168': '工业金属', '603993': '工业金属', '000630': '工业金属', '002532': '工业金属',
       '000831': '稀土磁材', '000970': '稀土磁材', '002378': '小金属', '601958': '小金属'}

MODAL_JS = """
    App.stockImportDlg();
    var _t = document.getElementById('s-bulk');
    if(_t){ _t.value = '600459 贵研铂业\\n601600 中国铝业\\n000807,002532\\nsh603993\\n601168 西部矿业\\n002378 章源钨业'; }
    UI.stkFiles = ['自选股.ebk（6）', '有色金属.txt（4）'];
    var _b = document.getElementById('s-files');
    if(_b){ _b.innerHTML = UI.stkFiles.map(function(t){ return '<span class="fx">📄 ' + t + '</span>'; }).join(''); }
"""

# 弹窗截图专用：不走网络，直接给已知基本面值 —— 弹窗必须在固定时刻打开，
# 不能挂在 syncQuotes 的 .then 上（headless 虚拟时间下会被截在 sync 与 then 之间的空隙里，弹窗拍不到）
INJECT_MODAL = """
<style>
  .page{max-width:2280px !important}
</style>
<script>
(function(){
  document.documentElement.className = document.documentElement.className
      .replace('gating','') + ' authed';
  var G = document.getElementById('loginGate'); if(G) G.className = 'gate';
  var TX = __TX__, GRP = __GRP__, EX = __EX__;
  setTimeout(function(){
    S.stocks = TX.map(function(t){
      var r = defaults('stocks', {id:'st_'+t.slice(2), code:t.slice(2), exchange:t.slice(0,2), name:''});
      r.grp = GRP[r.code] || '';
      var e = EX[r.code] || {}; for(var k in e) r[k] = e[k];
      return r;
    });
    App.go('stock'); sortState(); renderStock(); counts();
    __MODALJS__
  }, 900);
})();
</script>
"""

INJECT = """
<style>
  /* 截图专用：把主区放宽，好让 19 列（含 总资产 / 净资产 / 地区 / 操作）一屏拍全 */
  .page{max-width:2280px !important}
  .main{padding:14px 20px !important}
</style>
<script>
(function(){
  document.documentElement.className = document.documentElement.className
      .replace('gating','') + ' authed';                     /* 绕过登录门，仅截图用 */
  var G = document.getElementById('loginGate'); if(G) G.className = 'gate';
  var TX = __TX__, GRP = __GRP__;
  setTimeout(function(){
    S.stocks = TX.map(function(t){
      var r = defaults('stocks', {id:'st_'+t.slice(2), code:t.slice(2), exchange:t.slice(0,2), name:''});
      r.grp = GRP[r.code] || '';
      return r;
    });
    App.go('stock'); sortState(); renderStock();
    syncQuotes({silent:true}).then(function(res){
      renderStock();
      document.title = 'SHOT_READY';
    });
  }, 700);
})();
</script>
"""

# 弹窗截图用的已知基本面值（真实来源见 build/_stock_check.txt）
EX = {
    '600459': {'sub_industry': '其他稀有小金属', 'region': '云南', 'ind_pe': 39.36, 'total_assets': 252.74, 'net_assets': 90.12},
    '601600': {'sub_industry': '铝', 'region': '北京', 'ind_pe': 10.51, 'total_assets': 2445.77, 'net_assets': 843.45},
    '000807': {'sub_industry': '铝', 'region': '云南', 'ind_pe': 10.51, 'total_assets': 505.15, 'net_assets': 381.62},
    '600547': {'sub_industry': '黄金', 'region': '山东', 'ind_pe': 23.53, 'total_assets': 1755.34, 'net_assets': 804.20},
    '601168': {'sub_industry': '铅锌', 'region': '青海', 'ind_pe': 20.66, 'total_assets': 665.31, 'net_assets': 223.54},
    '603993': {'sub_industry': '铜', 'region': '河南', 'ind_pe': 14.75, 'total_assets': 2277.30, 'net_assets': 936.84},
    '000831': {'sub_industry': '稀土', 'region': '江西', 'ind_pe': 46.59, 'total_assets': 59.58, 'net_assets': 50.33},
    '000970': {'sub_industry': '磁性材料', 'region': '北京', 'ind_pe': 51.64, 'total_assets': 138.23, 'net_assets': 65.51},
    '002532': {'sub_industry': '铝', 'region': '新疆', 'ind_pe': 10.51, 'total_assets': 617.74, 'net_assets': 325.38},
    '002378': {'sub_industry': '其他稀有小金属', 'region': '江西', 'ind_pe': 39.36, 'total_assets': 276.69, 'net_assets': 102.28},
    '000630': {'sub_industry': '铜', 'region': '安徽', 'ind_pe': 14.75, 'total_assets': 1092.81, 'net_assets': 361.27},
    '601958': {'sub_industry': '其他稀有小金属', 'region': '陕西', 'ind_pe': 39.36, 'total_assets': 250.17, 'net_assets': 193.98},
}


def build_probe(mode):
    s = open(SRC, encoding='utf-8').read()
    s = s.replace('backdrop-filter:', 'backdrop-filter-off:')   # headless 下会糊
    tpl = INJECT_MODAL if mode == 'modal' else INJECT
    js = (tpl
          .replace('__TX__', json.dumps(TX))
          .replace('__GRP__', json.dumps(GRP, ensure_ascii=False))
          .replace('__EX__', json.dumps(EX, ensure_ascii=False))
          .replace('__MODALJS__', MODAL_JS if mode == 'modal' else ''))
    s = s.replace('</body>', js + '\n</body>', 1)
    p = os.path.join(OUTDIR, '_shot2_%s.html' % mode)
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
    ('list',  'v2_stock_list.png',   2460, 1080, 16000),
    ('modal', 'v2_stock_import.png', 1320, 1020, 8000),
]

for mode, png, w, h, budget in shots:
    html = os.path.basename(build_probe(mode))
    prof = os.path.join(OUTDIR, '_shot2_prof_%s' % mode)
    shutil.rmtree(prof, ignore_errors=True)
    out = os.path.join(OUTDIR, png)
    if os.path.exists(out):
        os.remove(out)
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--user-data-dir=' + prof, '--window-size=%d,%d' % (w, h),
           '--virtual-time-budget=%d' % budget, '--screenshot=' + out,
           'http://127.0.0.1:%d/%s' % (PORT, html)]
    subprocess.run(cmd, capture_output=True, timeout=180)
    shutil.rmtree(prof, ignore_errors=True)
    print('%-8s -> %s   %s' % (mode, png,
          ('%d KB' % (os.path.getsize(out) // 1024)) if os.path.exists(out) else '失败'))

httpd.shutdown()
for f in os.listdir(OUTDIR):
    if f.startswith('_shot2_'):
        try:
            os.remove(os.path.join(OUTDIR, f))
        except Exception:
            pass
print('临时文件已清理')
