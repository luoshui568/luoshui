# -*- coding: utf-8 -*-
"""投资标的模块 · 端到端真实渲染探针

本地 http + headless Edge + 真实腾讯行情接口：
  注入 6 只标的 → syncQuotes() 真拉行情 → 检查解析结果 / 表格渲染 / 云端回写 payload
结果写进页面隐藏节点，用 --dump-dom 取回。
"""
import os
import re
import json
import time
import shutil
import socket
import subprocess
import http.server
import socketserver
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(BASE, 'deploy', 'index.html')
OUT = os.path.join(BASE, 'build', '_probe_stock.html')
PORT = 8899

# ---------- 1. 生成探针页 ----------
s = open(SRC, encoding='utf-8').read()

onerr = ('<script>window.__R={err:[],stage:"init"};'
         'window.onerror=function(m,u,l,c,e){window.__R.err.push(String(m)+" @"+l);};'
         # ★★ 固定 profile 的**跨轮残留**必须在这里清掉，且要在应用脚本之前：
         #    上一轮探针（尤其门禁那套）会往 localStorage 里留下"真实标的"，
         #    下一轮一进来就已经有数据 →「空态先渲染」这条必然挂，
         #    而且看起来像功能坏了（本轮就遇上了）。
         'try{localStorage.removeItem("wb_strategy_v1");'
         'sessionStorage.removeItem("wb_auth_v1");sessionStorage.clear();}catch(e){}'
         '</script>')
assert '<head>' in s
s = s.replace('<head>', '<head>\n' + onerr, 1)

probe = """
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var TX = ['sh600459','sh601600','sz000807','sh600547','sz000831','sh603993'];

  /* 打桩 api：拦下云端回写，只记录 payload，不发真实请求 */
  var realApi = api;
  window.__R.push = null;
  window.api = function(table, opt){
    window.__R.push = {table:table, method:opt && opt.method, count:(opt && opt.body && opt.body.length) || 0,
                       sample: (opt && opt.body && opt.body[0]) || null};
    return Promise.resolve(null);
  };

  setTimeout(function(){
    try{
      /* 1) 切到投资标的页 */
      App.go('stock');
      window.__R.pageOn = (document.getElementById('pg-stock').className || '').indexOf('on') >= 0;

      /* 2) 注入 6 只测试标的 */
      S.stocks = TX.map(function(t){
        return defaults('stocks', {id:'st_'+t.slice(2), code:t.slice(2), exchange:t.slice(0,2), name:''});
      });
      sortState();
      window.__R.emptyHtml = (document.getElementById('stockWrap').textContent||'').slice(0,40);
      renderStock();
      window.__R.stage = 'injected';

      /* 3) 真实拉取行情 */
      Cloud.state = 'on';
      syncQuotes({silent:true}).then(function(res){
        window.__R.sync = res;
        window.__R.stage = 'synced';

        window.__R.rows = S.stocks.map(function(x){
          return {code:x.code, name:x.name, price:x.price, chg:x.chg_pct, peT:x.pe_ttm,
                  peF:x.pe_fwd, pb:x.pb, div:x.div_yield, cap:x.mkt_cap, ytd:x.chg_ytd,
                  d10:x.chg_10d, d20:x.chg_20d, d60:x.chg_60d, qd:x.quote_date, qt:x.quote_time};
        });

        var wrap = document.getElementById('stockWrap');
        var ths = wrap.querySelectorAll('thead th');
        var tds = wrap.querySelectorAll('tbody tr:first-child td');
        window.__R.ui = {
          th: ths.length,
          thText: [].map.call(ths, function(e){ return e.textContent.replace(/[⇅▼▲]/g,''); }),
          tr: wrap.querySelectorAll('tbody tr').length,
          tdCount: tds.length,
          tds: [].map.call(tds, function(e){ return (e.textContent || '').slice(0,12); }),
          rowHtml: String((wrap.querySelector('tbody tr') || {}).outerHTML || '').slice(0, 620),
          chgCell: tds.length > 2 ? (tds[2].textContent || '') : '(no-td)',
          nameCell: tds.length > 1 ? (tds[1].textContent || '') : '',
          kpi: document.getElementById('stockKpi').textContent.replace(/\\s+/g,' ').slice(0,150),
          sub: document.getElementById('stockSub').textContent.slice(0,140)
        };

        /* 4) 排序切换 */
        App.stockSortBy('mkt_cap');
        window.__R.sortK = UI.stockSort + '/' + UI.stockSortDir;
        var tds2 = document.getElementById('stockWrap').querySelectorAll('tbody tr:first-child td');
        window.__R.sortFirst = tds2.length > 1 ? tds2[1].textContent : '';

        /* 5) 搜索筛选 */
        App.stockKw('600459');
        window.__R.filtered = document.getElementById('stockWrap').querySelectorAll('tbody tr').length;
        App.stockKw('');
        window.__R.restored = document.getElementById('stockWrap').querySelectorAll('tbody tr').length;

        /* 6) ★ 拼音首字母搜索：gyby → 贵研铂业；zgly → 中国铝业
             —— 锚点表由 build.py 注入（见 build/_calib_pinyin.py 标定） */
        function rows(){ return document.getElementById('stockWrap').querySelectorAll('tbody tr'); }
        function first(){ var r = rows(); return r.length ? r[0].textContent : ''; }
        window.__R.pyOk = PY_OK;
        App.stockKw('gyby');
        window.__R.pyN = rows().length;
        window.__R.pyTxt = first();
        App.stockKw('zgly');
        window.__R.pyN2 = rows().length;
        window.__R.pyTxt2 = first();
        App.stockKw('zzzz');          /* 乱输不该命中 */
        window.__R.pyN3 = rows().length;
        App.stockKw('');
        window.__R.pyBack = rows().length;
        /* 汉字原文搜索不能被拼音影响 */
        App.stockKw('贵研');
        window.__R.cnN = rows().length;
        App.stockKw('');

        window.__R.stage = 'done';
        out();
      }).catch(function(e){ window.__R.err.push('sync:' + (e && e.message)); out(); });
    }catch(e){
      window.__R.err.push('throw:' + (e && e.message));
      out();
    }
  }, 700);

  function out(){
    document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(window.__R);
  }
})();
</script>
"""

assert '</body>' in s
s = s.replace('</body>', probe + '\n</body>', 1)
open(OUT, 'w', encoding='utf-8').write(s)
print('[1] 探针页已生成：%s（%d 字节）' % (OUT, os.path.getsize(OUT)))


# ---------- 2. 起本地 http ----------
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


os.chdir(os.path.join(BASE, 'build'))
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', PORT), Quiet)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
print('[2] 本地 http 已启动：http://127.0.0.1:%d/' % PORT)


# ---------- 3. 找 Edge ----------
cands = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
edge = None
for c in cands:
    if os.path.exists(c):
        edge = c
        break
if not edge:
    r = subprocess.run(['where', 'msedge'], capture_output=True, text=True)
    edge = (r.stdout or '').strip().split('\n')[0]
assert edge and os.path.exists(edge), '找不到 msedge.exe'
print('[3] Edge：%s' % edge)

prof = os.path.join(BASE, 'build', '_probe_profile')
# ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
#   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
os.makedirs(prof, exist_ok=True)
url = 'http://127.0.0.1:%d/_probe_stock.html' % PORT
cmd = [edge, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
       '--user-data-dir=' + prof, '--virtual-time-budget=25000',
       '--dump-dom', url]
print('[4] 启动 headless Edge …')
r = subprocess.run(cmd, capture_output=True, timeout=180)
dom = r.stdout.decode('utf-8', 'ignore')
print('    DOM 长度 %d' % len(dom))


# ---------- 4. 解析结果 ----------
m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S)
if not m:
    m = re.search(r'PROBE_JSON:(\{.*\})', dom, re.S)

print()
print('=' * 68)
print('探针结果')
print('=' * 68)

if not m:
    print('[FAIL] 探针没有回传结果（页面可能提前中断）')
    open(os.path.join(BASE, 'build', '_probe_dom.txt'), 'w', encoding='utf-8').write(dom)
    print('DOM 已存至 build/_probe_dom.txt，前 600 字：')
    print(dom[:600])
else:
    d = json.loads(m.group(1))
    ok = fail = 0

    def chk(name, cond, extra=''):
        global ok, fail
        if cond:
            ok += 1
            print('  [OK]   ' + name)
        else:
            fail += 1
            print('  [FAIL] ' + name + ('   ' + str(extra) if extra else ''))

    print('\n阶段：%s' % d.get('stage'))
    print('JS 错误：%s' % (d.get('err') or '无'))

    chk('页面切换到投资标的', d.get('pageOn') is True)
    chk('空态先渲染（提示导入）', '还没有投资标的' in (d.get('emptyHtml') or ''), d.get('emptyHtml'))
    chk('syncQuotes 返回成功', (d.get('sync') or {}).get('ok', 0) >= 6, d.get('sync'))

    rows = d.get('rows') or []
    got = [r for r in rows if r.get('name')]
    chk('6 只标的全部取到行情（名称非空）', len(got) == 6, '取到 %d 只' % len(got))
    for r in rows:
        if not r.get('name'):
            print('       缺：%s' % r.get('code'))

    if got:
        r0 = got[0]
        print('\n  样本：%s %s 现价=%s 涨幅=%s PE动=%s PE-TTM=%s PB=%s 股息=%s 市值=%s 年初=%s 10/20/60日=%s/%s/%s 行情日=%s' % (
            r0.get('code'), r0.get('name'), r0.get('price'), r0.get('chg'), r0.get('peF'),
            r0.get('peT'), r0.get('pb'), r0.get('div'), r0.get('cap'), r0.get('ytd'),
            r0.get('d10'), r0.get('d20'), r0.get('d60'), r0.get('qd')))

    need = ['price', 'chg', 'peT', 'peF', 'pb', 'div', 'cap', 'ytd', 'd10', 'd20', 'd60']
    full = [r for r in got if all(r.get(k) is not None for k in need)]
    chk('11 个行情字段全部有值', len(full) == len(got), '完整 %d / 共 %d' % (len(full), len(got)))
    chk('行情日期格式正确', bool(re.match(r'^\d{4}-\d{2}-\d{2}$', str((got[0] if got else {}).get('qd') or ''))),
        (got[0] if got else {}).get('qd'))

    ui = d.get('ui') or {}
    # ★ 列数**别写死**：写过 20，结果上一轮加了「板块」列就变 21 → 必然过期的假失败。
    #   改成「表头与首行单元格数一致 + 至少 20 列 + 关键列都在」。
    th, td = ui.get('th'), ui.get('tdCount')
    thText = ui.get('thText') or []
    chk('表格列数自洽（表头 = 首行单元格）且 ≥20', th == td and (th or 0) >= 20, 'th=%s td=%s' % (th, td))
    chk('关键列齐全（代码/名称/板块/操作）',
        all(any(k in t for t in thText) for k in ['代码', '名称', '板块', '操作']),
        ' | '.join(thText))
    chk('表格 6 行', ui.get('tr') == 6, ui.get('tr'))
    chk('涨幅单元格带 % 与符号', '%' in (ui.get('chgCell') or ''), ui.get('chgCell'))
    chk('KPI 有内容', len(ui.get('kpi') or '') > 20, ui.get('kpi'))
    chk('副标题显示标的数', '6' in (ui.get('sub') or ''), ui.get('sub'))
    print('\n  表头：%s' % ' | '.join(ui.get('thText') or []))
    print('  首行 td（%s 个）：%s' % (ui.get('tdCount'), ' ｜ '.join(ui.get('tds') or [])))
    print('  首行 HTML：%s' % (ui.get('rowHtml') or '')[:520])
    print('  KPI：%s' % ui.get('kpi'))
    print('  副标题：%s' % ui.get('sub'))

    chk('点击表头排序生效', (d.get('sortK') or '').startswith('mkt_cap'), d.get('sortK'))
    chk('搜索筛选生效（600459 → 1 行）', d.get('filtered') == 1, d.get('filtered'))
    chk('清空搜索恢复 6 行', d.get('restored') == 6, d.get('restored'))
    chk('拼音自检 PY_OK（环境支持 zh 排序）', d.get('pyOk') is True, d.get('pyOk'))
    chk('★ 拼音首字母搜 gyby → 1 行且是贵研铂业',
        d.get('pyN') == 1 and '贵研铂业' in (d.get('pyTxt') or ''), d.get('pyTxt'))
    chk('★ 拼音首字母搜 zgly → 1 行且是中国铝业',
        d.get('pyN2') == 1 and '中国铝业' in (d.get('pyTxt2') or ''), d.get('pyTxt2'))
    chk('★ 乱输首字母 zzzz → 0 行（不误命中）', d.get('pyN3') == 0, d.get('pyN3'))
    chk('★ 汉字原文搜索不受拼音影响（贵研 → 1 行）', d.get('cnN') == 1, d.get('cnN'))
    chk('清空搜索恢复 6 行（拼音之后）', d.get('pyBack') == 6, d.get('pyBack'))

    push = d.get('push') or {}
    chk('云端回写走 upsert on_conflict=code', 'wb_stocks?on_conflict=code' == (push.get('table') or ''), push.get('table'))
    chk('回写条数 = 6', push.get('count') == 6, push.get('count'))
    s0 = push.get('sample') or {}
    chk('回写样本字段完整', all(k in s0 for k in ['id', 'code', 'name', 'chg_pct', 'price',
                                                'pe_ttm', 'pe_fwd', 'pb', 'div_yield', 'mkt_cap',
                                                'chg_ytd', 'chg_10d', 'chg_20d', 'chg_60d', 'quote_date']),
        sorted(s0.keys()))
    print('\n  回写样本：%s' % json.dumps(s0, ensure_ascii=False)[:300])

    print('\n' + '=' * 68)
    print('通过 %d 项 · 失败 %d 项' % (ok, fail))
    print('=' * 68)

httpd.shutdown()
# ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
#   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
os.makedirs(prof, exist_ok=True)
try:
    os.remove(OUT)
except Exception:
    pass
print('\n[5] 临时文件已清理')
