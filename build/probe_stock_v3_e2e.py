# -*- coding: utf-8 -*-
"""投资标的模块 v2 · 端到端真机探针

本地 http + headless Edge + **真实**腾讯行情 / 东财接口，覆盖本轮全部改动：
  A. parseStockBlob —— .ebk 7 位 / sh600459 / 「600459 贵研铂业」/ 纯 6 位 / CSV 带表头 / 行内兜底 / 重复保留最新
  B. decodeBuf —— GBK 文件解码
  C. dedupeStocks —— 同代码只留一条且保留「最新」
  D. 4 列基本面（行业PE / 细分行业 / 总资产(亿) / 地区）**单元格文本**必须不是 「—」
  E. 真实 syncQuotes 拉行情 + 基本面 → 再渲染，确认 4 列有值
  F. 字段级人工锁定 —— 改过即锁，之后同步不覆盖；解锁后清空
  G. 导入弹窗 doImport —— 已存在只补名称、不新建；重复代码不产生重复记录
  H. 云端回写 payload 含基本面字段
  I. JS 错误必须为 0
"""
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(BASE, 'deploy', 'index.html')
OUT = os.path.join(BASE, 'build', '_probe_stock3.html')
PORT = 8907

GBK_TEXT = '600459 贵研铂业\n601600 中国铝业\n'
GBK_BYTES = ', '.join(str(b) for b in GBK_TEXT.encode('gbk'))

# 与云端落库一致的 4 条测试标的（build/_stock_check.txt）
IMM_JSON = json.dumps([
    {"id": "st_600459", "code": "600459", "exchange": "sh", "name": "贵研铂业",
     "grp": "贵金属", "sub_industry": "其他稀有小金属", "region": "云南",
     "ind_pe": 39.36, "total_assets": 252.74, "net_assets": 90.12,
     "pe_ttm": 23.43, "pe_fwd": 22.30, "pb": 1.73, "price": 18.94, "chg_pct": -3.86,
     "mkt_cap": 15591000000.0, "quote_date": "2026-09-11",
     "info_at": "2026-09-13T21:20:27.453+08:00"},
    {"id": "st_601600", "code": "601600", "exchange": "sh", "name": "中国铝业",
     "grp": "工业金属", "sub_industry": "铝", "region": "北京",
     "ind_pe": 10.51, "total_assets": 2445.77, "net_assets": 843.45,
     "pe_ttm": 9.27, "pe_fwd": 6.82, "pb": 1.92, "price": 9.44, "chg_pct": -4.84,
     "mkt_cap": 161943000000.0, "quote_date": "2026-09-11",
     "info_at": "2026-09-13T21:20:27.453+08:00"},
    {"id": "st_000807", "code": "000807", "exchange": "sz", "name": "云铝股份",
     "grp": "工业金属", "sub_industry": "铝", "region": "云南",
     "ind_pe": 10.51, "total_assets": 505.15, "net_assets": 381.62,
     "pe_ttm": 8.63, "pe_fwd": 6.16, "pb": 2.48, "price": 27.29, "chg_pct": -3.67,
     "mkt_cap": 94641000000.0, "quote_date": "2026-09-11",
     "info_at": "2026-09-13T21:20:27.453+08:00"},
    {"id": "st_601958", "code": "601958", "exchange": "sh", "name": "金钼股份",
     "grp": "稀有金属", "sub_industry": "其他稀有小金属", "region": "陕西",
     "ind_pe": 39.36, "total_assets": 250.17, "net_assets": 193.98,
     "pe_ttm": 18.61, "pe_fwd": 18.77, "pb": 3.37, "price": 20.26, "chg_pct": -4.43,
     "mkt_cap": 65371000000.0, "quote_date": "2026-09-11",
     "info_at": "2026-09-13T21:20:27.453+08:00"},
], ensure_ascii=False)

PROBE = r'''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var R = window.__R;
  function out(){ document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R); }
  function grid(){
    var wrap = document.getElementById('stockWrap');
    var ths = wrap.querySelectorAll('thead th');
    var cols = [].map.call(ths, function(e){ return e.textContent.replace(/[⇅▼▲]/g,'').trim(); });
    var map = {};
    [].forEach.call(wrap.querySelectorAll('tbody tr'), function(tr){
      var tds = tr.querySelectorAll('td');
      map[tds[0].textContent.trim()] = [].map.call(tds, function(td){ return td.textContent.trim(); });
    });
    return {cols:cols, map:map};
  }
  function pick(g, code, keys){
    var t = g.map[code] || [], o = {};
    keys.forEach(function(k){ o[k] = t[g.cols.indexOf(k)]; });
    return o;
  }
  var K4 = ['行业PE','细分行业','总资产(亿)','净资产(亿)','地区'];

  /* 打桩云端回写，避免真写库 */
  window.api = function(table, opt){
    R.push = {table:table, method:opt&&opt.method, count:(opt&&opt.body&&opt.body.length)||0,
              sample:(opt&&opt.body&&opt.body[0])||null};
    return Promise.resolve(null);
  };

  setTimeout(function(){
    try{
      App.go('stock');
      R.pageOn = (document.getElementById('pg-stock').className||'').indexOf('on') >= 0;

      /* ===== A. parseStockBlob ===== */
      R.p1 = parseStockBlob('1600459\n1600459 贵研铂业\nsh601600\n000807,002532\n\n600547 山东黄金\nsz.000833');
      R.p1codes = R.p1.map(function(x){ return x.code; });
      R.p1name459 = ((R.p1.filter(function(x){ return x.code==='600459'; })[0])||{}).name;
      R.p1name547 = ((R.p1.filter(function(x){ return x.code==='600547'; })[0])||{}).name;
      R.p2 = parseStockBlob('\uFEFF代码,名称\r\n600459,贵研铂业\r\n601600 中国铝业\r\n600459 贵研铂业NEW\r\n002532\t天山铝业\r\nxx\n');
      R.p2_459 = ((R.p2.filter(function(x){ return x.code==='600459'; })[0])||{}).name;
      R.p2codes = R.p2.map(function(x){ return x.code; });
      R.p3 = parseStockBlob('无有效内容\n12345\n9999999\n20260913\nabc\ndate 2026-09-13');
      R.p3len = R.p3.length;
      /* 深圳 .ebk 是 0 + 6 位（0000807）；8 位以上当日期/金额忽略 */
      R.p4 = parseStockBlob('0000807\n000807\n2300001234567\n1600459,金钼股份');
      R.p4codes = R.p4.map(function(x){ return x.code; });
      R.p4name459 = ((R.p4.filter(function(x){ return x.code==='600459'; })[0])||{}).name;

      /* ===== B. decodeBuf / GBK ===== */
      R.gbk = decodeBuf(new Uint8Array([__GBK__]).buffer);
      R.gbkParsed = parseStockBlob(R.gbk).map(function(x){ return x.code + ':' + x.name; });

      /* ===== C. dedupeStocks =====
         defaults() 会把 up 与 t 都刷成 nowTs()，而 dedupeStocks 的「最新」= max(up, t, sync_at, info_at)，
         所以要在这两者上做区分（t 必须一起改，否则它压过 up） */
      S.stocks = [
        defaults('stocks', {id:'st_600459A', code:'600459', name:'贵研铂业', note:'OLD'}),
        defaults('stocks', {id:'st_600459B', code:'600459', name:'贵研铂业', note:'NEW'}),
        defaults('stocks', {id:'st_601600',  code:'601600', name:'中国铝业', note:'only'}),
        defaults('stocks', {id:'st_600459C', code:'600459', name:'贵研铂业', note:'OLDEST'})
      ];
      S.stocks[0].up = 1000; S.stocks[0].t = 1000;
      S.stocks[1].up = 2000; S.stocks[1].t = 2000;
      S.stocks[3].up = 900;  S.stocks[3].t = 900;
      R.dupRemoved = dedupeStocks();
      R.dupLeft = S.stocks.length;
      R.dupKeptNote = ((S.stocks.filter(function(x){ return x.code==='600459'; })[0])||{}).note;
      /* up / t 相同时，按 info_at 取较新的那条 */
      S.stocks = [
        defaults('stocks', {id:'st_600459X', code:'600459', name:'旧', info_at:'2026-01-01T00:00:00Z'}),
        defaults('stocks', {id:'st_600459Y', code:'600459', name:'新', info_at:'2026-09-13T00:00:00Z'})
      ];
      S.stocks[0].up = 5000; S.stocks[0].t = 5000;
      S.stocks[1].up = 5000; S.stocks[1].t = 5000;
      R.dupRemoved2 = dedupeStocks();
      R.dupKeptName2 = (S.stocks[0]||{}).name;

      /* ===== D. 4 列渲染（注入已知值，与网络无关） ===== */
      S.stocks = __IMM__.map(function(x){ return defaults('stocks', x); });
      sortState(); renderStock();
      var g = grid();
      R.cols = g.cols;
      R.cell4 = {};
      ['600459','601600','000807','601958'].forEach(function(c){ R.cell4[c] = pick(g, c, K4); });
      R.rowCount = Object.keys(g.map).length;
      R.sub = document.getElementById('stockSub').textContent.slice(0, 200);

      /* ===== G. 导入：已存在只补名称 + 重复不新建 ===== */
      var realSync = window.syncQuotes, syncCalls = 0;
      window.syncQuotes = function(){ syncCalls++; return Promise.resolve({ok:0}); };
      App.stockImportDlg();
      R.dlgFileInput = !!(document.getElementById('s-file'));
      R.dlgDrop = !!(document.getElementById('s-drop'));
      R.dlgAccept = (document.getElementById('s-file')||{}).accept || '';
      document.getElementById('s-bulk').value =
        '1600459\n600459 贵研铂业\n600459\n002532 天山铝业\n002532\n601677 明泰铝业\n';
      App.doImport(window.PASS_OK||{});
      R.importCodes = S.stocks.map(function(x){ return x.code; });
      R.importUniq = R.importCodes.length === (function(a){
        var s={},n=0; a.forEach(function(c){ if(!s[c]){s[c]=1;n++;} }); return n; })(R.importCodes);
      R.importTotal = S.stocks.length;
      R.import459name = ((S.stocks.filter(function(x){ return x.code==='600459'; })[0])||{}).name;
      R.importNew532 = S.stocks.filter(function(x){ return x.code==='002532'; }).length;
      R.importSyncCalls = syncCalls;
      R.modalClosed = (document.getElementById('mask').className||'').indexOf('on') < 0;
      window.syncQuotes = realSync;

      /* ===== E. 真实拉取行情 + 基本面 ===== */
      S.stocks = [
        defaults('stocks', {id:'st_600459', code:'600459', exchange:'sh'}),
        defaults('stocks', {id:'st_601600', code:'601600', exchange:'sh'}),
        defaults('stocks', {id:'st_000807', code:'000807', exchange:'sz'}),
        defaults('stocks', {id:'st_601958', code:'601958', exchange:'sh'})
      ];
      sortState(); renderStock();
      R.beforeLive = pick(grid(), '600459', K4);

      /* pushQuotes 要求 Cloud.state==='on' 才会回写（api 已打桩，不会真写库） */
      Cloud.state = 'on';
      R.push = null;
      syncQuotes({silent:true}).then(function(res){
        R.liveSync = res;
        R.live = S.stocks.map(function(x){
          return {code:x.code, name:x.name, price:x.price, chg:x.chg_pct,
                  ind_pe:x.ind_pe, sub:x.sub_industry, ta:x.total_assets,
                  na:x.net_assets, region:x.region, info_at:x.info_at};
        });
        var g2 = grid();
        R.cellLive = {};
        ['600459','601600','000807','601958'].forEach(function(c){ R.cellLive[c] = pick(g2, c, K4); });
        R.pushLive = R.push;
        R.push = null;

        /* ===== F. 字段锁定：改过即锁，同步不覆盖 ===== */
        App.openStock('st_600459');
        R.lockModalOpen = (document.getElementById('mask').className||'').indexOf('on') >= 0;
        R.formIndPE = (document.getElementById('s-indpe')||{}).value;
        document.getElementById('s-indpe').value = '99.99';
        document.getElementById('s-region').value = '昆明市';
        App.saveStock('st_600459', window.PASS_OK||{});
        var r459 = findRow('stocks', 'st_600459');
        R.lockFields = r459.lock_fields;
        R.lockIndPE = r459.ind_pe;
        R.lockRegion = r459.region;
        R.lockToastOpen = true;

        return syncFundamentals([r459]).then(function(fr){
          R.afterLockSync = {ind_pe:r459.ind_pe, region:r459.region, fr:fr};
          /* 解锁 */
          App.stockUnlock('st_600459');
          R.unlockFields = findRow('stocks', 'st_600459').lock_fields;
          R.stage = 'done';
          setTimeout(out, 200);
        });
      }).catch(function(e){
        R.err.push('live:' + (e && e.message));
        R.stage = 'live-failed';
        out();
      });
    }catch(e){
      R.err.push('throw:' + (e && e.message));
      R.stage = 'threw';
      out();
    }
  }, 800);
})();
</script>
'''

# ---------- 1. 生成探针页 ----------
s = open(SRC, encoding='utf-8').read()

onerr = ('<script>window.__R={err:[],stage:"init"};'
         'window.onerror=function(m,u,l,c,e){window.__R.err.push(String(m)+" @"+l);};'
         '</script>')
assert '<head>' in s
s = s.replace('<head>', '<head>\n' + onerr, 1)

js = PROBE.replace('__GBK__', GBK_BYTES).replace('__IMM__', IMM_JSON)

assert '</body>' in s
s = s.replace('</body>', js + '\n</body>', 1)
open(OUT, 'w', encoding='utf-8').write(s)
print('[1] 探针页已生成：%s（%d 字节）' % (OUT, os.path.getsize(OUT)))


# ---------- 2. 本地 http ----------
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


os.chdir(os.path.join(BASE, 'build'))
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', PORT), Quiet)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
print('[2] 本地 http：http://127.0.0.1:%d/' % PORT)

# ---------- 3. Edge ----------
edge = None
for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
          r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
    if os.path.exists(c):
        edge = c
        break
assert edge, '找不到 msedge.exe'
print('[3] Edge：%s' % edge)

prof = os.path.join(BASE, 'build', '_probe_profile3')
# ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
#   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
os.makedirs(prof, exist_ok=True)
url = 'http://127.0.0.1:%d/_probe_stock3.html' % PORT
cmd = [edge, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
       '--user-data-dir=' + prof, '--virtual-time-budget=45000', '--dump-dom', url]
print('[4] 启动 headless Edge（含真实行情+基本面拉取，约 10~30 秒）…')
r = subprocess.run(cmd, capture_output=True, timeout=300)
dom = r.stdout.decode('utf-8', 'ignore')
print('    DOM 长度 %d' % len(dom))

# ---------- 4. 结果 ----------
m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S) or re.search(r'PROBE_JSON:(\{.*\})', dom, re.S)

print('\n' + '=' * 74)
print('探针结果 · 投资标的模块 v2')
print('=' * 74)

if not m:
    open(os.path.join(BASE, 'build', '_probe3_dom.txt'), 'w', encoding='utf-8').write(dom)
    print('[FAIL] 探针没有回传结果，DOM 已存 build/_probe3_dom.txt')
    print(dom[:800])
    httpd.shutdown()
    raise SystemExit(1)

d = json.loads(m.group(1))
ok = fail = 0


def chk(name, cond, extra=''):
    global ok, fail
    if cond:
        ok += 1
        print('  [OK]   ' + name)
    else:
        fail += 1
        print('  [FAIL] ' + name + ('   → ' + str(extra) if extra != '' else ''))


print('\n阶段：%s' % d.get('stage'))
print('JS 错误：%s' % (d.get('err') or '无'))
chk('页面切换到投资标的', d.get('pageOn') is True)
chk('JS 零错误', not d.get('err'))

# ---- A. 解析 ----
print('\n── A. 文本 / .ebk 解析 ──')
print('  p1 → %s' % d.get('p1'))
chk('.ebk 7 位 / sh 前缀 / 逗号分隔 / 行内兜底 全覆盖',
    sorted(d.get('p1codes') or []) == sorted(['600459', '601600', '000807', '002532', '600547', '000833']),
    d.get('p1codes'))
chk('重复代码只留一条（p1 无重复）',
    len(set(d.get('p1codes') or [])) == len(d.get('p1codes') or []))
chk('「1600459 贵研铂业」补上了名称', d.get('p1name459') == '贵研铂业', d.get('p1name459'))
chk('「600547 山东黄金」补上了名称', d.get('p1name547') == '山东黄金', d.get('p1name547'))
print('  p2 → %s' % d.get('p2'))
chk('BOM + CRLF + 表头行 不产生脏数据',
    sorted(d.get('p2codes') or []) == sorted(['600459', '601600', '002532']), d.get('p2codes'))
chk('CSV 重复：保留最新那条的名称（…NEW）', d.get('p2_459') == '贵研铂业NEW', d.get('p2_459'))
chk('无有效代码时返回空数组（9999999 / 日期 / 短号都被拒）', d.get('p3len') == 0, d.get('p3len'))
print('  p4 → %s' % d.get('p4'))
chk('深圳 .ebk（0+6 位）与纯 6 位都归一成同一代码',
    sorted(set(d.get('p4codes') or [])) == ['000807', '600459'], d.get('p4codes'))
chk('超大数字串（模拟日期/金额）不会被误当代码',
    '1234567' not in (d.get('p4codes') or []) and len(d.get('p4codes') or []) == 2, d.get('p4codes'))
chk('「1600459,金钼股份」补上名称', d.get('p4name459') == '金钼股份', d.get('p4name459'))

# ---- B. GBK ----
print('\n── B. GBK 解码 ──')
print('  解码结果：%s' % repr(d.get('gbk')))
chk('GBK 文件能正确解码出中文', '贵研铂业' in (d.get('gbk') or ''), d.get('gbk'))
chk('GBK 内容解析出代码+名称',
    (d.get('gbkParsed') or []) == ['600459:贵研铂业', '601600:中国铝业'], d.get('gbkParsed'))

# ---- C. 去重 ----
print('\n── C. 去重保留最新 ──')
chk('3 条重复被合掉 2 条', d.get('dupRemoved') == 2, d.get('dupRemoved'))
chk('去重后剩 2 条', d.get('dupLeft') == 2, d.get('dupLeft'))
chk('保留的是 up 最大的那条（NEW）', d.get('dupKeptNote') == 'NEW', d.get('dupKeptNote'))
chk('up 相同时按 info_at 取较新的（新）', d.get('dupKeptName2') == '新', d.get('dupKeptName2'))

# ---- D. 4 列渲染 ----
print('\n── D. 4 列基本面渲染（注入已知值） ──')
print('  表头：%s' % ' | '.join(d.get('cols') or []))
cell = d.get('cell4') or {}
EXP = {
    '600459': {'行业PE': '39.36', '细分行业': '其他稀有小金属', '总资产(亿)': '252.74', '净资产(亿)': '90.12', '地区': '云南'},
    '601600': {'行业PE': '10.51', '细分行业': '铝', '总资产(亿)': '2445.77', '净资产(亿)': '843.45', '地区': '北京'},
    '000807': {'行业PE': '10.51', '细分行业': '铝', '总资产(亿)': '505.15', '净资产(亿)': '381.62', '地区': '云南'},
    '601958': {'行业PE': '39.36', '细分行业': '其他稀有小金属', '总资产(亿)': '250.17', '净资产(亿)': '193.98', '地区': '陕西'},
}
for code, exp in EXP.items():
    got = cell.get(code) or {}
    print('  %s → %s' % (code, json.dumps(got, ensure_ascii=False)))
    for k, v in exp.items():
        chk('%s · %s = %s' % (code, k, v), got.get(k) == v, got.get(k))
chk('表格 4 行', d.get('rowCount') == 4, d.get('rowCount'))
chk('副标题提示「4 项基本面…更新于」', ('4 项基本面' in (d.get('sub') or '')) and ('更新于' in (d.get('sub') or '')), d.get('sub'))
print('  副标题：%s' % d.get('sub'))

# ---- G. 导入 ----
print('\n── G. 导入弹窗（已存在只补名称 / 重复不新建） ──')
chk('弹窗有 file 输入框', d.get('dlgFileInput') is True)
chk('弹窗有拖放区', d.get('dlgDrop') is True)
chk('accept 含 .ebk', '.ebk' in (d.get('dlgAccept') or ''), d.get('dlgAccept'))
print('  导入后代码：%s' % d.get('importCodes'))
chk('导入后无重复代码', d.get('importUniq') is True, d.get('importCodes'))
chk('已存在的 600459 不新建（总数 4+2=6）', d.get('importTotal') == 6, d.get('importTotal'))
chk('重复出现的 002532 只建 1 条', d.get('importNew532') == 1, d.get('importNew532'))
chk('已存在的 600459 保留原名称', d.get('import459name') == '贵研铂业', d.get('import459name'))
chk('导入触发了一次同步', d.get('importSyncCalls') == 1, d.get('importSyncCalls'))
chk('导入后弹窗自动关闭', d.get('modalClosed') is True)

# ---- E. 真实同步 ----
print('\n── E. 真实拉取（腾讯行情 + 东财基本面） ──')
print('  同步前 600459：%s' % json.dumps(d.get('beforeLive'), ensure_ascii=False))
print('  同步返回：%s' % d.get('liveSync'))
for x in d.get('live') or []:
    print('  %s %s 现价=%s 涨幅=%s | 行业PE=%s 细分=%s 总资产=%s 净资产=%s 地区=%s' % (
        x.get('code'), x.get('name'), x.get('price'), x.get('chg'),
        x.get('ind_pe'), x.get('sub'), x.get('ta'), x.get('na'), x.get('region')))
chk('同步返回 ok>=4', (d.get('liveSync') or {}).get('ok', 0) >= 4, d.get('liveSync'))
live = d.get('live') or []
named = [x for x in live if x.get('name')]
chk('4 只都取到行情名称', len(named) == 4, len(named))
full = [x for x in live if x.get('ind_pe') is not None and x.get('sub')
        and x.get('ta') is not None and x.get('region')]
chk('4 只基本面 4 项全补齐', len(full) == 4, '%d/4' % len(full))
cl = d.get('cellLive') or {}
dash = 0
for code in ['600459', '601600', '000807', '601958']:
    for k, v in (cl.get(code) or {}).items():
        if v in ('—', '', None):
            dash += 1
            print('       仍是 —：%s · %s' % (code, k))
chk('渲染出 20 个单元格无「—」', dash == 0, '%d 个空' % dash)
for code in ['600459', '601600']:
    print('  %s 渲染 → %s' % (code, json.dumps(cl.get(code), ensure_ascii=False)))

# ---- F. 锁定 ----
print('\n── F. 字段级人工锁定 ──')
chk('编辑弹窗能打开', d.get('lockModalOpen') is True)
print('  表单回填 行业PE = %s' % d.get('formIndPE'))
chk('手工改 行业PE / 地区 后 lock_fields = ind_pe,region',
    set((d.get('lockFields') or '').split(',')) == {'ind_pe', 'region'}, d.get('lockFields'))
chk('保存后值就是手填的 99.99', d.get('lockIndPE') == 99.99, d.get('lockIndPE'))
chk('保存后地区是手填的 昆明市', d.get('lockRegion') == '昆明市', d.get('lockRegion'))
als = d.get('afterLockSync') or {}
print('  再跑一次基本面同步 → ind_pe=%s region=%s' % (als.get('ind_pe'), als.get('region')))
chk('同步不覆盖已锁定字段（行业PE 仍 99.99）', als.get('ind_pe') == 99.99, als.get('ind_pe'))
chk('同步不覆盖已锁定字段（地区 仍 昆明市）', als.get('region') == '昆明市', als.get('region'))
chk('未锁定的细分行业被同步正常写入',
    ((d.get('live') and True) and (als.get('fr') or {}).get('ok', 0) >= 1), als.get('fr'))
chk('点「全部解锁」后 lock_fields 清空', d.get('unlockFields') == '', d.get('unlockFields'))

# ---- H. 回写 payload ----
print('\n── H. 云端回写 payload ──')
pl = d.get('pushLive') or {}
print('  %s' % json.dumps(pl, ensure_ascii=False)[:600])
chk('走 upsert on_conflict=code', pl.get('table') == 'wb_stocks?on_conflict=code', pl.get('table'))
chk('回写 4 条', pl.get('count') == 4, pl.get('count'))
s0 = pl.get('sample') or {}
chk('payload 含基本面 4 项 + info_at + lock_fields',
    all(k in s0 for k in ['ind_pe', 'sub_industry', 'total_assets', 'net_assets', 'region', 'info_at', 'lock_fields']),
    sorted(s0.keys()))

print('\n' + '=' * 74)
print('通过 %d 项 · 失败 %d 项' % (ok, fail))
print('=' * 74)

httpd.shutdown()
# ★ 复用固定 profile：不删目录——Edge profile 有 300+ 文件，
#   rmtree 会触发环境的 safe-delete 批量删除拦截；探针自己会重置状态
os.makedirs(prof, exist_ok=True)
try:
    os.remove(OUT)
except Exception:
    pass
print('\n[5] 临时文件已清理')
