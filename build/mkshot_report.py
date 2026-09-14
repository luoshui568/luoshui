# -*- coding: utf-8 -*-
"""本轮交付效果截图（研报页红主题 + 编辑面板 + 工作台跳转）

产出（都在 build/ 下）：
  v5_report_top.png    研报页顶部：红色 hero + 8 项 KPI + 核心结论
  v5_report_chart.png  研报页图表区：真数据渲染的 ECharts（红色主题）
  v5_report_panel.png  编辑模式 + 数据管理面板「页眉与结论」（8 项 KPI 可编辑表）
  v5_report_grid.png   图表数据表编辑器（改数字即写库）
  v5_stock_link.png    工作台投资标的：名称/代码是研报链接，📄 标记已有研报

要点（踩过的坑，勿简化）：
  * 截图前必须 `<style>*{animation:none!important;transition:none!important}`，
    否则 headless 虚拟时钟会把动画截在半透明中间态 → 灰糊图。
  * `backdrop-filter` 在 headless 下会糊，替换掉。
  * report.html 的 `</body>` 有**两处**（ECharts 压缩库里有一段字符串含 `</body>`），
    注入探针必须用 rfind 取最后一处。
  * 研报页**不打桩网络**（就是要拍真数据），靠虚拟时钟在 fetch 挂起时暂停的特性等它加载完。
"""
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
DEPLOY = os.path.join(BASE, 'deploy')
OUTDIR = os.path.join(BASE, 'build')
PORT = 8931
CODE = '600456'

CSS_KILL = """
<style>
  *{animation:none !important;transition:none !important}
  .page{max-width:1500px !important}
</style>
"""

# ---------- 研报页：顶部 ----------
RPT_TOP = CSS_KILL + """
<script>
setTimeout(function(){ document.title = 'SHOT_READY'; }, 2600);
</script>
"""

# ---------- 研报页：只留某张图表（不滚动）
# ⚠️ headless 里 `--screenshot` 拍的是视口，`window.scrollTo` 后的区域常常是空白
#    （合成器没来得及重绘）→ 改成「隐藏其它所有兄弟节点」，让图表自然落到视口里。
_SOLO = """
function isolate(el){
  var node = el;
  while(node && node !== document.body){
    var p = node.parentNode;
    if(p) for(var i = 0; i < p.children.length; i++) if(p.children[i] !== node) p.children[i].style.display = 'none';
    node = p;
  }
}
setTimeout(function(){
  var el = document.querySelector('[data-chart="__KEY__"]');
  if(el){
    var hd = document.querySelector('header.hero'); if(hd) hd.style.display = 'none';
    ['#hero','#verdict','#kpis','#kpiNote','#toc','#foot'].forEach(function(s){
      var n = document.querySelector(s); if(n) n.style.display = 'none';
    });
    isolate(el);
    window.scrollTo(0, 0);
  }
  document.title = 'SHOT_READY';
}, 2600);
"""
RPT_CHART = CSS_KILL + "<script>" + _SOLO.replace('__KEY__', 'chart1') + "</script>"
RPT_CHART2 = CSS_KILL + "<script>" + _SOLO.replace('__KEY__', 'chartForecast') + "</script>"

# ---------- 研报页：数据管理面板（页眉与结论 / KPI 可编辑表） ----------
RPT_PANEL = CSS_KILL + """
<script>
setTimeout(function(){
  Rpt.openDrawer('head');
  document.title = 'SHOT_READY';
}, 2600);
</script>
"""

# ---------- 研报页：图表数据表编辑器 ----------
RPT_GRID = CSS_KILL + """
<script>
setTimeout(function(){
  Rpt.openChart('chart1');
  document.title = 'SHOT_READY';
}, 2600);
</script>
"""

# ---------- 工作台：投资标的列表（名称是研报链接） ----------
WB_CSS = """
<style>
  .page{max-width:2500px !important}
  .main{padding:14px 20px !important}
  *{animation:none !important;transition:none !important}
</style>
"""
WB_TX = ['sh600459', 'sh600456', 'sh601600', 'sz000807', 'sh600547', 'sh601168', 'sz002532']
WB_GRP = {'600459': '贵金属', '600456': '钛材', '601600': '工业金属', '000807': '工业金属',
          '600547': '贵金属', '601168': '工业金属', '002532': '电解铝'}
WB_EX = {
    '600459': {'name': '贵研铂业', 'sub_industry': '其他稀有小金属', 'region': '云南', 'ind_pe': 39.36,
               'total_assets': 252.74, 'net_assets': 90.12, 'price': 18.94, 'chg_pct': -3.86,
               'pe_ttm': 23.43, 'pb': 1.73, 'mkt_cap': 15591000000.0, 'amount': 386000000.0, 'quote_date': '2026-09-11'},
    '600456': {'name': '宝钛股份', 'sub_industry': '其他稀有小金属', 'region': '陕西', 'ind_pe': 39.36,
               'total_assets': 152.31, 'net_assets': 74.60, 'price': 27.35, 'chg_pct': 0.55,
               'pe_ttm': 27.90, 'pb': 1.80, 'mkt_cap': 13080000000.0, 'amount': 212000000.0, 'quote_date': '2026-09-11'},
    '601600': {'name': '中国铝业', 'sub_industry': '铝', 'region': '北京', 'ind_pe': 10.51,
               'total_assets': 2445.77, 'net_assets': 843.45, 'price': 9.44, 'chg_pct': -4.84,
               'pe_ttm': 12.10, 'pb': 1.55, 'mkt_cap': 162000000000.0, 'amount': 1520000000.0, 'quote_date': '2026-09-11'},
    '000807': {'name': '云铝股份', 'sub_industry': '铝', 'region': '云南', 'ind_pe': 10.51,
               'total_assets': 505.15, 'net_assets': 381.62, 'price': 27.29, 'chg_pct': -3.67,
               'pe_ttm': 12.44, 'pb': 2.44, 'mkt_cap': 94970000000.0, 'amount': 1180000000.0, 'quote_date': '2026-09-11'},
    '600547': {'name': '山东黄金', 'sub_industry': '黄金', 'region': '山东', 'ind_pe': 23.53,
               'total_assets': 700.10, 'net_assets': 320.50, 'price': 28.11, 'chg_pct': 1.22,
               'pe_ttm': 20.05, 'pb': 2.75, 'mkt_cap': 127600000000.0, 'amount': 1610000000.0, 'quote_date': '2026-09-11'},
    '601168': {'name': '西部矿业', 'sub_industry': '铅锌', 'region': '青海', 'ind_pe': 16.20,
               'total_assets': 610.44, 'net_assets': 218.90, 'price': 24.10, 'chg_pct': -2.11,
               'pe_ttm': 14.30, 'pb': 2.62, 'mkt_cap': 57430000000.0, 'amount': 640000000.0, 'quote_date': '2026-09-11'},
    '002532': {'name': '天山铝业', 'sub_industry': '铝', 'region': '新疆', 'ind_pe': 10.51,
               'total_assets': 620.10, 'net_assets': 258.30, 'price': 12.86, 'chg_pct': -1.38,
               'pe_ttm': 11.20, 'pb': 2.31, 'mkt_cap': 59800000000.0, 'amount': 430000000.0, 'quote_date': '2026-09-11'},
}

WB_JS = """
<script>
(function(){
  document.documentElement.className = document.documentElement.className.replace('gating','') + ' authed';
  var G = document.getElementById('loginGate'); if(G) G.className = 'gate';
  /* 打桩：只让「研报代码列表」返回 600456，其余请求一律 null（避免真网络暂停虚拟时钟） */
  window.api = function(t){
    if(String(t).indexOf('wb_reports') === 0) return Promise.resolve([{code:'600456'}]);
    return Promise.resolve(null);
  };
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
    document.title = 'SHOT_READY';
  }, 900);
})();
</script>
"""


def inject_report(extra, tag):
    s = open(os.path.join(DEPLOY, 'report.html'), encoding='utf-8').read()
    s = s.replace('backdrop-filter:', 'backdrop-filter-off:')
    i = s.rfind('</body>')                      # ⚠️ 必须 rfind：库里有第二个 </body>
    s = s[:i] + extra + '\n' + s[i:]
    p = os.path.join(OUTDIR, '_shot_rpt_%s.html' % tag)
    open(p, 'w', encoding='utf-8').write(s)
    return p


def inject_wb(maxw=2500, tag='link'):
    s = open(os.path.join(DEPLOY, 'index.html'), encoding='utf-8').read()
    s = s.replace('backdrop-filter:', 'backdrop-filter-off:')
    js = (WB_JS.replace('__TX__', json.dumps(WB_TX))
              .replace('__GRP__', json.dumps(WB_GRP, ensure_ascii=False))
              .replace('__EX__', json.dumps(WB_EX, ensure_ascii=False)))
    css = WB_CSS.replace('2500px', '%dpx' % maxw)
    i = s.rfind('</body>')
    s = s[:i] + css + js + '\n' + s[i:]
    p = os.path.join(OUTDIR, '_shot_wb_%s.html' % tag)
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

SHOTS = [
    (inject_report(RPT_TOP, 'top'), 'v5_report_top.png', 1560, 1360, 30000),
    (inject_report(RPT_CHART, 'chart'), 'v5_report_chart.png', 1560, 620, 30000),
    (inject_report(RPT_CHART2, 'chart2'), 'v5_report_chart2.png', 1560, 780, 30000),
    (inject_report(RPT_PANEL, 'panel'), 'v5_report_panel.png', 1560, 1200, 30000),
    (inject_report(RPT_GRID, 'grid'), 'v5_report_grid.png', 1560, 1250, 30000),
    (inject_wb(2500, 'wide'), 'v5_stock_link.png', 2520, 780, 20000),
    (inject_wb(1600, 'zoom'), 'v5_stock_link_zoom.png', 1640, 620, 20000),
]

for src, png, w, h, budget in SHOTS:
    prof = os.path.join(OUTDIR, '_shot_profile')
    # ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
    #   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
    os.makedirs(prof, exist_ok=True)
    out = os.path.join(OUTDIR, png)
    if os.path.exists(out):
        os.remove(out)
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--user-data-dir=' + prof, '--window-size=%d,%d' % (w, h),
           '--virtual-time-budget=%d' % budget, '--screenshot=' + out,
           'http://127.0.0.1:%d/%s' % (PORT, os.path.basename(src))]
    subprocess.run(cmd, capture_output=True, timeout=240)
    # ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
    #   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
    os.makedirs(prof, exist_ok=True)
    print('%-24s %s' % (png, ('%d KB' % (os.path.getsize(out) // 1024)) if os.path.exists(out) else '失败'))

httpd.shutdown()
for f in os.listdir(OUTDIR):
    if f.startswith('_shot_'):
        try:
            os.remove(os.path.join(OUTDIR, f))
        except Exception:
            pass
print('临时文件已清理')
