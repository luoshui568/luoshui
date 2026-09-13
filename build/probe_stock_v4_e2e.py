# -*- coding: utf-8 -*-
"""投资标的模块 v3 · 端到端真机探针：自定义板块

覆盖本轮改动（全部在真浏览器里跑，数据注入，不依赖外网）：
  A. 板块标签条渲染 —— 全部 / 各自定义板块（带数量）/ 未分组；× 只出现在自定义板块上
  B. 板块名安全性 —— 含引号/尖括号的板块名不会破坏内联 onclick（按下标派发）
  C. 筛选 —— 点板块名只显示该板块；再点一次回到全部；「未分组」只显示无板块的
  D. 导入弹窗的自定义板块 —— 输入框 + datalist + 已有板块快捷标签 + 「已识别 N 个代码」
  E. doImport 归组 —— 新标的归入；已存在但未分组的补归；已有别的板块的不动
  F. 编辑弹窗板块字段 —— 可手填新板块名、保存时去空白
  G. 解散板块 —— 走管理员密码闸门；只清空 grp，标的本身不删；标签条立即刷新
  H. 板块列 —— 表头有「板块」，有板块的标的显示标签、无板块显示 —
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
OUT = os.path.join(BASE, 'build', '_probe_stock4.html')
PORT = 8913

NASTY = '测"试\'板块<x>'

# 注入的股票池：3 个板块 + 1 只未分组 + 1 只名字特异的板块
IMM = [
    {"id": "st_600459", "code": "600459", "exchange": "sh", "name": "贵研铂业",
     "grp": "贵金属", "sub_industry": "其他稀有小金属", "region": "云南",
     "ind_pe": 39.36, "total_assets": 252.74, "net_assets": 90.12, "price": 18.94, "chg_pct": -3.86},
    {"id": "st_600547", "code": "600547", "exchange": "sh", "name": "山东黄金",
     "grp": "贵金属", "sub_industry": "黄金", "region": "山东",
     "ind_pe": 23.53, "total_assets": 700.1, "net_assets": 320.5, "price": 28.11, "chg_pct": 1.22},
    {"id": "st_601600", "code": "601600", "exchange": "sh", "name": "中国铝业",
     "grp": "工业金属", "sub_industry": "铝", "region": "北京",
     "ind_pe": 10.51, "total_assets": 2445.77, "net_assets": 843.45, "price": 9.44, "chg_pct": -4.84},
    {"id": "st_000807", "code": "000807", "exchange": "sz", "name": "云铝股份",
     "grp": "工业金属", "sub_industry": "铝", "region": "云南",
     "ind_pe": 10.51, "total_assets": 505.15, "net_assets": 381.62, "price": 27.29, "chg_pct": -3.67},
    {"id": "st_000831", "code": "000831", "exchange": "sz", "name": "五矿稀土",
     "grp": "", "sub_industry": "稀土", "region": "山西",
     "ind_pe": 46.59, "total_assets": 90.2, "net_assets": 60.1, "price": 31.5, "chg_pct": 2.4},
    {"id": "st_601958", "code": "601958", "exchange": "sh", "name": "金钼股份",
     "grp": NASTY, "sub_industry": "其他稀有小金属", "region": "陕西",
     "ind_pe": 39.36, "total_assets": 250.17, "net_assets": 193.98, "price": 20.26, "chg_pct": -4.43},
]
IMM_JSON = json.dumps(IMM, ensure_ascii=False)

PROBE = r'''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var R = window.__R;
  function out(){ document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R); }
  function txt(id){ var e = document.getElementById(id); return e ? e.textContent.replace(/\s+/g,' ').trim() : ''; }
  function chips(){
    var box = document.getElementById('stockGrps');
    if(!box) return {all:[], named:[], del:0, raw:''};
    var gs = [].map.call(box.querySelectorAll('.stkG .gn'), function(e){
      return {t:e.textContent.replace(/\s+/g,' ').trim(), on:e.parentNode.className.indexOf('on')>=0};
    });
    return {all:gs,
            named:gs.slice(1).map(function(x){ return x.t; }),
            del:box.querySelectorAll('.stkG .gx').length,
            raw:box.innerHTML.slice(0, 400)};
  }
  function tableCodes(){
    var wrap = document.getElementById('stockWrap');
    if(!wrap) return [];
    return [].map.call(wrap.querySelectorAll('tbody tr'), function(tr){
      return tr.querySelectorAll('td')[0].textContent.trim();
    });
  }
  function tableCol(name){
    var wrap = document.getElementById('stockWrap');
    var ths = [].map.call(wrap.querySelectorAll('thead th'), function(e){
      return e.textContent.replace(/[⇅▼▲]/g,'').trim(); });
    var i = ths.indexOf(name), o = {};
    if(i < 0) return o;
    [].forEach.call(wrap.querySelectorAll('tbody tr'), function(tr){
      var td = tr.querySelectorAll('td');
      o[td[0].textContent.trim()] = td[i].textContent.replace(/\s+/g,' ').trim();
    });
    return o;
  }
  function grpOf(code){
    var r = S.stocks.filter(function(x){ return x.code === code; })[0];
    return r ? r.grp : null;
  }

  /* 打桩：任何云端请求都不发出去（updateRow 会入队，flushQueue 调的就是 window.api） */
  window.api = function(){ return Promise.resolve(null); };

  setTimeout(function(){
    try{
      App.go('stock');
      R.pageOn = (document.getElementById('pg-stock').className||'').indexOf('on') >= 0;

      /* ===== A. 标签条渲染 ===== */
      S.stocks = __IMM__.map(function(x){ return defaults('stocks', x); });
      sortState(); renderStock();
      var c1 = chips();
      R.chipAll = c1.all.map(function(x){ return x.t; });
      R.chipDel = c1.del;
      R.gKeys = (UI.stkGKeys || []).slice(0, 6);
      R.gList = stkGroupList();
      R.hintOn = c1.all.length ? c1.all[0].on : null;
      R.subTxt = txt('stockSub');
      /* 板块列 */
      R.cols = [].map.call(document.getElementById('stockWrap').querySelectorAll('thead th'), function(e){
        return e.textContent.replace(/[⇅▼▲]/g,'').trim(); });
      R.grpCells = tableCol('板块');

      /* ===== B. 板块名安全性（含引号/尖括号） ===== */
      var badIdx = UI.stkGKeys.indexOf('__NASTY__');
      R.nastyIdx = badIdx;
      try{
        App.stockGrpPick(badIdx);
        R.nastyPickOk = true;
      }catch(e){ R.nastyPickOk = false; R.err.push('nasty:' + e.message); }
      R.nastyFilterGrp = UI.stockGrp;
      R.nastyRows = tableCodes();
      App.stockGrpPick(0);                        /* 下标 0 = 「全部」，复位 */
      R.afterResetAll = tableCodes().length;

      /* ===== C. 筛选 ===== */
      var gi = UI.stkGKeys.indexOf('贵金属');
      App.stockGrpPick(gi);
      R.pickGrp = UI.stockGrp;
      R.pickRows = tableCodes();
      R.pickOn = chips().all.filter(function(x){ return x.on; }).map(function(x){ return x.t; });
      App.stockGrpPick(gi);                       /* 再点一次 = 取消 */
      R.pickToggleOff = UI.stockGrp;
      R.pickToggleRows = tableCodes().length;
      var ni = UI.stkGKeys.indexOf('__NONE__');
      R.noneIdx = ni;
      App.stockGrpPick(ni);
      R.noneRows = tableCodes();
      R.noneChip = chips().all.filter(function(x){ return x.on; }).map(function(x){ return x.t; });
      App.stockGrpPick(0);

      /* ===== D. 导入弹窗：自定义板块 ===== */
      var realSync = window.syncQuotes, syncCalls = 0;
      window.syncQuotes = function(){ syncCalls++; return Promise.resolve({ok:0}); };
      App.stockImportDlg();
      R.dlgGrpInput = !!document.getElementById('s-grp-new');
      R.dlgDatalist = (document.getElementById('s-grp-new-dl')||{children:[]}).children.length;
      R.dlgQuick = [].map.call((document.getElementById('s-grp-qs')||{querySelectorAll:function(){return [];}})
                     .querySelectorAll('.q'), function(e){ return e.textContent.trim(); });
      var ta = document.getElementById('s-bulk');
      ta.value = '600459 贵研铂业\n601677 明泰铝业\n002532 天山铝业\n000831 五矿稀土\n';
      R.grpOpts = (UI.stkGrpOpts || []).slice();
      var qi = UI.stkGrpOpts.indexOf('贵金属');
      R.quickIdx = qi;
      App.stockGrpFill(qi);                       /* 点快捷标签「贵金属」 */
      R.fillVal = document.getElementById('s-grp-new').value;
      App.stockImportCount();
      R.countTxt = txt('s-count');
      R.countOn = (document.getElementById('s-grp-qs')||{querySelectorAll:function(){return [];}})
                    .querySelectorAll('.q.on').length;
      App.stockGrpFill(qi);                       /* 再点一次取消 */
      R.fillToggle = document.getElementById('s-grp-new').value;

      /* ===== E. doImport 归组 ===== */
      document.getElementById('s-grp-new').value = '稀土永磁';
      App.stockImportCount();
      R.countTxt2 = txt('s-count');
      App.doImport();
      R.imp600459 = grpOf('600459');              /* 已有板块（贵金属）→ 不动 */
      R.imp000831 = grpOf('000831');              /* 未分组 → 补归 */
      R.imp601677 = grpOf('601677');              /* 新标的 → 归入 */
      R.imp002532 = grpOf('002532');
      R.impTotal = S.stocks.length;
      R.impChips = chips().all.map(function(x){ return x.t; });
      R.impSyncCalls = syncCalls;
      R.impModalClosed = (document.getElementById('mask').className||'').indexOf('on') < 0;
      window.syncQuotes = realSync;

      /* ===== F. 编辑弹窗板块字段 ===== */
      App.openStock('st_600459');
      R.editGrpVal = (document.getElementById('s-grp')||{}).value;
      R.editGrpTag = (document.getElementById('s-grp')||{}).tagName;
      R.editDatalist = (document.getElementById('s-grp-dl')||{children:[]}).children.length;
      document.getElementById('s-grp').value = '  紫金系  ';
      App.saveStock('st_600459');
      R.editSaved = grpOf('600459');
      R.editClosed = (document.getElementById('mask').className||'').indexOf('on') < 0;

      /* ===== G. 解散板块（管理员闸门） ===== */
      var realReq = window.requireAdmin, asked = null;
      window.requireAdmin = function(label, cb){ asked = label; cb(''); };
      var before = S.stocks.length;
      var di = UI.stkGKeys.indexOf('工业金属');
      R.delIdx = di;
      App.stockGrpDel(di);
      R.delLabel = asked;
      R.delLeft601600 = grpOf('601600');
      R.delLeft000807 = grpOf('000807');
      R.delRowsKept = S.stocks.length;
      R.delRowCountSame = (S.stocks.length === before);
      R.delChips = chips().all.map(function(x){ return x.t; });
      R.delUiGrp = UI.stockGrp;
      /* 「全部」「未分组」不能删 */
      asked = null;
      App.stockGrpDel(0);
      R.delAllBlocked = (asked === null);
      window.requireAdmin = realReq;

      /* ===== H. 保留标的数量、名称未被破坏 ===== */
      R.finalNames = S.stocks.map(function(x){ return x.code + ':' + x.name + ':' + (x.grp||'—'); });
      R.stage = 'done';
      setTimeout(out, 150);
    }catch(e){
      R.err.push('throw:' + (e && e.message));
      R.stage = 'threw';
      out();
    }
  }, 900);
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

js = (PROBE.replace('__IMM__', IMM_JSON)
           .replace('__NASTY__', json.dumps(NASTY)[1:-1].replace("'", "\\'"))
           .replace('__NONE__', '__none__'))

assert '</body>' in s
s = s.replace('</body>', js + '\n</body>', 1)
open(OUT, 'w', encoding='utf-8').write(s)
print('[1] 探针页已生成：%s（%d 字节）' % (OUT, os.path.getsize(OUT)))

# ---------- 1b. 注入脚本先过语法关（语法错会让探针静默不执行，白跑一趟） ----------
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
_tj = os.path.join(BASE, 'build', '_tmp_probe4.js')
_core = js.split('<script>')[1].split('</script>')[0]
open(_tj, 'w', encoding='utf-8').write(_core)
_c = subprocess.run([NODE, '--check', _tj], capture_output=True, text=True)
os.remove(_tj)
if _c.returncode != 0:
    print('[1b] 注入脚本语法错误：\n' + (_c.stderr or '')[-1200:])
    raise SystemExit(1)
print('[1b] 注入脚本 node --check 通过')


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

prof = os.path.join(BASE, 'build', '_probe_profile4')
shutil.rmtree(prof, ignore_errors=True)
url = 'http://127.0.0.1:%d/_probe_stock4.html' % PORT
cmd = [edge, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
       '--user-data-dir=' + prof, '--virtual-time-budget=20000', '--dump-dom', url]
print('[4] 启动 headless Edge …')
r = subprocess.run(cmd, capture_output=True, timeout=240)
dom = r.stdout.decode('utf-8', 'ignore')
print('    DOM 长度 %d' % len(dom))

# ---------- 4. 结果 ----------
m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S) or re.search(r'PROBE_JSON:(\{.*\})', dom, re.S)

print('\n' + '=' * 76)
print('探针结果 · 投资标的模块 v3（自定义板块）')
print('=' * 76)

if not m:
    open(os.path.join(BASE, 'build', '_probe4_dom.txt'), 'w', encoding='utf-8').write(dom)
    print('[FAIL] 探针没有回传结果，DOM 已存 build/_probe4_dom.txt')
    print(dom[:900])
    httpd.shutdown()
    raise SystemExit(1)

d = json.loads(m.group(1))

# 探针 JSON 是从 dump-dom 的 HTML 文本里抠出来的，文本节点里的 < > & 会被序列化成实体，
# 比对前先还原（否则「测"试'板块<x>」这类名字会假失败）
import html as _h


def un(x):
    if isinstance(x, str):
        return _h.unescape(x)
    if isinstance(x, list):
        return [un(i) for i in x]
    if isinstance(x, dict):
        return dict((k, un(v)) for k, v in x.items())
    return x


for _k in ['chipAll', 'gKeys', 'gList', 'grpCells', 'dlgQuick', 'grpOpts', 'delChips',
           'impChips', 'finalNames', 'countTxt', 'countTxt2', 'nastyFilterGrp',
           'delLabel', 'pickOn', 'noneChip', 'subTxt']:
    if _k in d:
        d[_k] = un(d[_k])

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

# ---- A ----
print('\n── A. 板块标签条 ──')
print('  标签：%s' % d.get('chipAll'))
print('  键序：%s' % d.get('gKeys'))
print('  分组统计：%s' % json.dumps(d.get('gList'), ensure_ascii=False))
chk('标签条含「全部」且数量正确（6）', (d.get('chipAll') or [])[:1] == ['全部6'], d.get('chipAll'))
chk('3 个自定义板块都显示出来（含数量）',
    sorted((d.get('chipAll') or [])[1:4]) == sorted(['贵金属2', '工业金属2', '测"试\'板块<x>1']),
    (d.get('chipAll') or [])[1:4])
chk('「未分组」标签显示未分组标的数（1）', '未分组1' in (d.get('chipAll') or []), d.get('chipAll'))
chk('× 只出现在 3 个自定义板块上（未分组/全部没有 ×）', d.get('chipDel') == 3, d.get('chipDel'))
chk('默认选中「全部」', d.get('hintOn') is True, d.get('hintOn'))
chk('副标题显示自定义板块个数', '3 个自定义板块' in (d.get('subTxt') or ''), d.get('subTxt'))
print('  副标题：%s' % d.get('subTxt'))

# ---- H ----
print('\n── H. 板块列 ──')
print('  表头：%s' % ' | '.join((d.get('cols') or [])[-4:]))
chk('表头有「板块」列', '板块' in (d.get('cols') or []), (d.get('cols') or [])[-5:])
print('  单元格：%s' % json.dumps(d.get('grpCells'), ensure_ascii=False))
chk('有板块的标的显示板块标签（600459 → 贵金属）',
    (d.get('grpCells') or {}).get('600459') == '🏷 贵金属', (d.get('grpCells') or {}).get('600459'))
chk('无板块的标的显示 —', (d.get('grpCells') or {}).get('000831') == '—', (d.get('grpCells') or {}).get('000831'))

# ---- B ----
print('\n── B. 板块名安全性（含引号 / 尖括号） ──')
chk('含 " \' < > 的板块名能拿到下标', isinstance(d.get('nastyIdx'), int) and d.get('nastyIdx') > 0, d.get('nastyIdx'))
chk('点它不抛错（按下标派发，内联 onclick 未被名字破坏）', d.get('nastyPickOk') is True)
chk('且确实筛选到了这个板块', d.get('nastyFilterGrp') == '测"试\'板块<x>', d.get('nastyFilterGrp'))
chk('该板块下只有 601958 一行', (d.get('nastyRows') or []) == ['601958'], d.get('nastyRows'))
chk('复位后 6 行都在', d.get('afterResetAll') == 6, d.get('afterResetAll'))

# ---- C ----
print('\n── C. 按板块筛选 ──')
print('  选中「贵金属」→ %s' % d.get('pickRows'))
chk('点「贵金属」筛选生效', d.get('pickGrp') == '贵金属', d.get('pickGrp'))
chk('只剩该板块 2 只', sorted(d.get('pickRows') or []) == ['600459', '600547'], d.get('pickRows'))
chk('标签高亮切到「贵金属」', (d.get('pickOn') or []) and '贵金属' in (d.get('pickOn') or [''])[0], d.get('pickOn'))
chk('再点一次取消筛选（回到全部）', d.get('pickToggleOff') == '' and d.get('pickToggleRows') == 6,
    '%s / %s' % (d.get('pickToggleOff'), d.get('pickToggleRows')))
print('  点「未分组」→ %s' % d.get('noneRows'))
chk('「未分组」只显示无板块的 1 只', d.get('noneRows') == ['000831'], d.get('noneRows'))
chk('「未分组」标签高亮', (d.get('noneChip') or []) and '未分组' in (d.get('noneChip') or [''])[0], d.get('noneChip'))

# ---- D ----
print('\n── D. 导入弹窗的自定义板块 ──')
chk('弹窗有自定义板块输入框', d.get('dlgGrpInput') is True)
chk('有 datalist 供选已有板块（>=8 常用 + 已有）', (d.get('dlgDatalist') or 0) >= 8, d.get('dlgDatalist'))
print('  快捷标签：%s / 快捷顺序：%s' % (d.get('dlgQuick'), d.get('grpOpts')))
chk('已有板块做成快捷标签', len(d.get('dlgQuick') or []) == 3, d.get('dlgQuick'))
chk('点快捷标签把板块名填进输入框', d.get('fillVal') == '贵金属', repr(d.get('fillVal')))
print('  计数条：%s' % d.get('countTxt'))
chk('底部实时显示「已识别 N 个代码」（4 个）', '已识别' in (d.get('countTxt') or '') and '4' in (d.get('countTxt') or ''), d.get('countTxt'))
chk('填了板块名时显示归入提示', '将全部归入板块' in (d.get('countTxt') or ''), d.get('countTxt'))
chk('快捷标签会高亮当前板块', (d.get('countOn') or 0) == 1, d.get('countOn'))
chk('再点一次快捷标签 = 取消选择', d.get('fillToggle') == '', repr(d.get('fillToggle')))

# ---- E ----
print('\n── E. doImport 归组 ──')
print('  %s' % json.dumps(d.get('finalNames'), ensure_ascii=False))
print('  写入板块「稀土永磁」后的计数条：%s' % d.get('countTxt2'))
chk('新标的 601677 / 002532 归入「稀土永磁」',
    d.get('imp601677') == '稀土永磁' and d.get('imp002532') == '稀土永磁',
    '%s / %s' % (d.get('imp601677'), d.get('imp002532')))
chk('已存在但未分组的 000831 补归入「稀土永磁」', d.get('imp000831') == '稀土永磁', d.get('imp000831'))
chk('已有板块的 600459 不被挪动（仍 贵金属）', d.get('imp600459') == '贵金属', d.get('imp600459'))
chk('总数 6+2=8（已存在的不新建）', d.get('impTotal') == 8, d.get('impTotal'))
print('  导入后标签：%s' % d.get('impChips'))
chk('标签条出现「稀土永磁3」',
    any('稀土永磁' in (t or '') for t in (d.get('impChips') or [])), d.get('impChips'))
chk('导入触发一次同步', d.get('impSyncCalls') == 1, d.get('impSyncCalls'))
chk('导入后弹窗关闭', d.get('impModalClosed') is True)

# ---- F ----
print('\n── F. 编辑弹窗的板块字段 ──')
chk('板块字段是 input（可手填新板块）不是 select', d.get('editGrpTag') == 'INPUT', d.get('editGrpTag'))
chk('回填当前板块', d.get('editGrpVal') == '贵金属', d.get('editGrpVal'))
chk('datalist 有可选板块', (d.get('editDatalist') or 0) >= 8, d.get('editDatalist'))
chk('保存时去掉首尾空白（「  紫金系  」→「紫金系」）', d.get('editSaved') == '紫金系', repr(d.get('editSaved')))
chk('保存后弹窗关闭', d.get('editClosed') is True)

# ---- G ----
print('\n── G. 解散板块 ──')
print('  闸门提示：%s' % d.get('delLabel'))
chk('走管理员密码闸门，提示里写明板块名与标的数',
    '工业金属' in (d.get('delLabel') or '') and '2' in (d.get('delLabel') or ''), d.get('delLabel'))
chk('提示里明确「标的本身不会被删除」', '不会被删除' in (d.get('delLabel') or ''), d.get('delLabel'))
chk('成员被移出板块（grp 清空）',
    d.get('delLeft601600') == '' and d.get('delLeft000807') == '', '%s / %s' % (d.get('delLeft601600'), d.get('delLeft000807')))
chk('标的没有被删除（行数不变）', d.get('delRowCountSame') is True, '%s → %s' % (d.get('delRowsKept'), 'before'))
print('  解散后标签：%s' % d.get('delChips'))
chk('标签条上「工业金属」消失',
    not any('工业金属' in (t or '') for t in (d.get('delChips') or [])), d.get('delChips'))
chk('两只被移出的标的进入「未分组」（未分组2）',
    any(t == '未分组2' for t in (d.get('delChips') or [])), d.get('delChips'))
chk('「全部 / 未分组」不可当板块解散', d.get('delAllBlocked') is True)

print('\n' + '=' * 76)
print('通过 %d 项 · 失败 %d 项' % (ok, fail))
print('=' * 76)

httpd.shutdown()
shutil.rmtree(prof, ignore_errors=True)
try:
    os.remove(OUT)
except Exception:
    pass
print('\n[5] 临时文件已清理')
