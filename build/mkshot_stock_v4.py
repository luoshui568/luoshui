# -*- coding: utf-8 -*-
"""投资标的模块 v4 · 效果截图（★ 一只标的可同时属于多个板块）

两张图，均不依赖外网（基本面用已知真实值注入，同 mkshot_stock_v3.py）：
  v4_stock_multi.png  —— 板块标签条（同一只标的在两个板块里各计一次）+ 板块列里多个标签
  v4_stock_edit.png   —— 编辑弹窗：板块输入框回填「A | B」+ 快捷标签按已选高亮（点一下可增删）
"""
import http.server
import json
import os
import socketserver
import subprocess
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(BASE, 'deploy', 'index.html')
OUTDIR = os.path.join(BASE, 'build')
PORT = 8909

TX = ['sh600459', 'sh601600', 'sz000807', 'sh600547', 'sh601168', 'sh603993',
      'sz000831', 'sz000970', 'sz002532', 'sz002378', 'sz000630', 'sh601958']

# ★ 多板块：同一只标的可以挂在多个板块上（grp 里用 | 拼）
GRP = {'600459': '贵金属|稀土永磁',
       '600547': '贵金属|寒武纪投资2026',
       '601600': '工业金属|中特估',
       '000807': '工业金属|电解铝',
       '601168': '工业金属|中特估',
       '603993': '铜|工业金属',
       '000831': '稀土磁材|稀土永磁',
       '000970': '稀土磁材',
       '002532': '电解铝|中特估',
       '002378': '钨|稀土永磁',
       '000630': '铜',
       '601958': '钼|稀土永磁'}

# 弹窗截图：打开 600459 的编辑弹窗 —— 回填两个板块，快捷标签里对应两个是点亮状态
MODAL_JS = """
    App.openStock('st_600459', PASS_OK);
""" + """
    var _i = document.getElementById('s-grp');
    if(_i){ _i.focus(); }
"""

TITLE_JS = """
    document.title = 'SHOT_READY';
"""

INJECT = """
<style>
  /* 截图专用：把主区放宽，让 20 列（含 总资产/净资产/地区/板块/操作）一屏拍全 */
  .page{max-width:2960px !important}
  .main{padding:14px 20px !important}
  /* 禁掉进场动画：headless 虚拟时钟下 .page.on 的 fade 可能被截在半透明中间态 */
  *{animation:none !important;transition:none !important}
</style>
<script>
(function(){
  document.documentElement.className = document.documentElement.className
      .replace('gating','') + ' authed';                     /* 绕过登录门，仅截图用 */
  var G = document.getElementById('loginGate'); if(G) G.className = 'gate';
  /* 打桩网络：app 启动 900ms 后会自动跑 autoSyncIfStale()，
     真实 fetch 会暂停 headless 虚拟时钟 → 截图落在页面动画中途（半透明糊图） */
  window.api = function(){ return Promise.resolve(null); };
  window.syncQuotes = function(){ return Promise.resolve({ok:0}); };
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
    __TITLEJS__
  }, 900);
})();
</script>
"""

# 真实基本面值（来源：东财接口实测，见 mkshot_stock_v3.py）
EX = {
    '600459': {'name': '贵研铂业', 'sub_industry': '其他稀有小金属', 'region': '云南', 'ind_pe': 39.36, 'total_assets': 252.74, 'net_assets': 90.12, 'price': 18.94, 'chg_pct': -3.86, 'pe_ttm': 23.43, 'pe_fwd': 22.30, 'pb': 1.73, 'mkt_cap': 15591000000.0, 'amount': 356000000.0, 'div_yield': 1.15, 'chg_ytd': 12.4, 'chg_10d': -2.1, 'chg_20d': 5.6, 'chg_60d': -8.2, 'quote_date': '2026-09-11'},
    '601600': {'name': '中国铝业', 'sub_industry': '铝', 'region': '北京', 'ind_pe': 10.51, 'total_assets': 2445.77, 'net_assets': 843.45, 'price': 9.44, 'chg_pct': -4.84, 'pe_ttm': 9.27, 'pe_fwd': 6.82, 'pb': 1.92, 'mkt_cap': 161943000000.0, 'amount': 2100000000.0, 'div_yield': 2.01, 'chg_ytd': 24.1, 'chg_10d': 1.3, 'chg_20d': 9.4, 'chg_60d': 18.7, 'quote_date': '2026-09-11'},
    '000807': {'name': '云铝股份', 'sub_industry': '铝', 'region': '云南', 'ind_pe': 10.51, 'total_assets': 505.15, 'net_assets': 381.62, 'price': 27.29, 'chg_pct': -3.67, 'pe_ttm': 8.63, 'pe_fwd': 6.16, 'pb': 2.48, 'mkt_cap': 94641000000.0, 'amount': 1230000000.0, 'div_yield': 1.65, 'chg_ytd': 31.2, 'chg_10d': -0.8, 'chg_20d': 11.2, 'chg_60d': 22.5, 'quote_date': '2026-09-11'},
    '600547': {'name': '山东黄金', 'sub_industry': '黄金', 'region': '山东', 'ind_pe': 23.53, 'total_assets': 1755.34, 'net_assets': 804.20, 'price': 28.11, 'chg_pct': 1.22, 'pe_ttm': 31.05, 'pe_fwd': 24.18, 'pb': 4.11, 'mkt_cap': 125700000000.0, 'amount': 1560000000.0, 'div_yield': 0.82, 'chg_ytd': 18.9, 'chg_10d': 3.4, 'chg_20d': 7.1, 'chg_60d': 5.2, 'quote_date': '2026-09-11'},
    '601168': {'name': '西部矿业', 'sub_industry': '铅锌', 'region': '青海', 'ind_pe': 20.66, 'total_assets': 665.31, 'net_assets': 223.54, 'price': 19.03, 'chg_pct': 0.95, 'pe_ttm': 15.22, 'pe_fwd': 13.40, 'pb': 2.05, 'mkt_cap': 45360000000.0, 'amount': 430000000.0, 'div_yield': 1.42, 'chg_ytd': 9.6, 'chg_10d': 2.2, 'chg_20d': -1.4, 'chg_60d': 6.8, 'quote_date': '2026-09-11'},
    '603993': {'name': '洛阳钼业', 'sub_industry': '铜', 'region': '河南', 'ind_pe': 14.75, 'total_assets': 2277.30, 'net_assets': 936.84, 'price': 10.36, 'chg_pct': 2.31, 'pe_ttm': 12.44, 'pe_fwd': 10.11, 'pb': 2.86, 'mkt_cap': 223400000000.0, 'amount': 2450000000.0, 'div_yield': 1.98, 'chg_ytd': 42.7, 'chg_10d': 4.1, 'chg_20d': 12.8, 'chg_60d': 30.1, 'quote_date': '2026-09-11'},
    '000831': {'name': '五矿稀土', 'sub_industry': '稀土', 'region': '江西', 'ind_pe': 46.59, 'total_assets': 90.20, 'net_assets': 60.10, 'price': 31.50, 'chg_pct': 2.41, 'pe_ttm': 88.20, 'pe_fwd': 61.30, 'pb': 5.02, 'mkt_cap': 30990000000.0, 'amount': 380000000.0, 'div_yield': 0.11, 'chg_ytd': 55.3, 'chg_10d': 6.7, 'chg_20d': 14.2, 'chg_60d': 41.6, 'quote_date': '2026-09-11'},
    '000970': {'name': '中科三环', 'sub_industry': '磁性材料', 'region': '北京', 'ind_pe': 51.64, 'total_assets': 138.23, 'net_assets': 65.51, 'price': 13.88, 'chg_pct': -1.02, 'pe_ttm': 62.40, 'pe_fwd': 44.10, 'pb': 2.11, 'mkt_cap': 16820000000.0, 'amount': 210000000.0, 'div_yield': 0.65, 'chg_ytd': 21.4, 'chg_10d': -3.3, 'chg_20d': 2.9, 'chg_60d': 11.1, 'quote_date': '2026-09-11'},
    '002532': {'name': '天山铝业', 'sub_industry': '铝', 'region': '新疆', 'ind_pe': 10.51, 'total_assets': 617.74, 'net_assets': 325.38, 'price': 9.02, 'chg_pct': -2.15, 'pe_ttm': 9.80, 'pe_fwd': 8.02, 'pb': 1.55, 'mkt_cap': 41940000000.0, 'amount': 410000000.0, 'div_yield': 2.88, 'chg_ytd': 14.8, 'chg_10d': -1.1, 'chg_20d': 4.4, 'chg_60d': 9.7, 'quote_date': '2026-09-11'},
    '002378': {'name': '章源钨业', 'sub_industry': '其他稀有小金属', 'region': '江西', 'ind_pe': 39.36, 'total_assets': 276.69, 'net_assets': 102.28, 'price': 8.41, 'chg_pct': 3.06, 'pe_ttm': 45.10, 'pe_fwd': 38.20, 'pb': 1.88, 'mkt_cap': 7710000000.0, 'amount': 176000000.0, 'div_yield': 0.94, 'chg_ytd': 27.9, 'chg_10d': 5.2, 'chg_20d': 8.8, 'chg_60d': 16.3, 'quote_date': '2026-09-11'},
    '000630': {'name': '铜陵有色', 'sub_industry': '铜', 'region': '安徽', 'ind_pe': 14.75, 'total_assets': 1092.81, 'net_assets': 361.27, 'price': 3.72, 'chg_pct': 1.08, 'pe_ttm': 14.02, 'pe_fwd': 12.10, 'pb': 1.44, 'mkt_cap': 40330000000.0, 'amount': 890000000.0, 'div_yield': 2.42, 'chg_ytd': 8.1, 'chg_10d': 1.9, 'chg_20d': 3.6, 'chg_60d': -2.2, 'quote_date': '2026-09-11'},
    '601958': {'name': '金钼股份', 'sub_industry': '其他稀有小金属', 'region': '陕西', 'ind_pe': 39.36, 'total_assets': 250.17, 'net_assets': 193.98, 'price': 20.26, 'chg_pct': -4.43, 'pe_ttm': 18.61, 'pe_fwd': 18.77, 'pb': 3.37, 'mkt_cap': 65371000000.0, 'amount': 520000000.0, 'div_yield': 2.10, 'chg_ytd': 36.5, 'chg_10d': -5.4, 'chg_20d': 6.2, 'chg_60d': 19.4, 'quote_date': '2026-09-11'},
}


def build_probe(mode):
    s = open(SRC, encoding='utf-8').read()
    s = s.replace('backdrop-filter:', 'backdrop-filter-off:')   # headless 下会糊
    js = (INJECT
          .replace('__TX__', json.dumps(TX))
          .replace('__GRP__', json.dumps(GRP, ensure_ascii=False))
          .replace('__EX__', json.dumps(EX, ensure_ascii=False))
          .replace('__MODALJS__', MODAL_JS if mode == 'modal' else '')
          .replace('__TITLEJS__', TITLE_JS))
    s = s.replace('</body>', js + '\n</body>', 1)
    p = os.path.join(OUTDIR, '_shot4_%s.html' % mode)
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
    ('list',  'v4_stock_multi.png', 3000, 1130, 9000),
    ('modal', 'v4_stock_edit.png',  1360, 1130, 9000),
]

for mode, png, w, h, budget in shots:
    html = os.path.basename(build_probe(mode))
    prof = os.path.join(OUTDIR, '_shot4_prof_%s' % mode)
    # ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
    #   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
    os.makedirs(prof, exist_ok=True)
    out = os.path.join(OUTDIR, png)
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--user-data-dir=' + prof, '--window-size=%d,%d' % (w, h),
           '--virtual-time-budget=%d' % budget, '--screenshot=' + out,
           'http://127.0.0.1:%d/%s' % (PORT, html)]
    subprocess.run(cmd, capture_output=True, timeout=180)
    os.makedirs(prof, exist_ok=True)
    print('%-8s -> %s   %s' % (mode, png,
          ('%d KB' % (os.path.getsize(out) // 1024)) if os.path.exists(out) else '失败'))

httpd.shutdown()
for f in os.listdir(OUTDIR):
    if f.startswith('_shot4_') and f.endswith('.html'):
        try:
            open(os.path.join(OUTDIR, f), 'w', encoding='utf-8').write('')   # 清空不删（safe-delete 守卫）
        except Exception:
            pass
print('临时文件已清空')
